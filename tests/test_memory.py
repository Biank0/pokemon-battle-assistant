"""Tests for the memory layer (short-term / long-term / opponent / manager)."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from pokemon_battle_assistant.memory import (
    EventLog,
    LongTermMemory,
    MemoryManager,
    OpponentModel,
    ShortTermMemory,
)
from pokemon_battle_assistant.perception.observation import BattleObservation, PokemonSnapshot


def snap(species: str, hp=100.0, *, fainted=False, terastallized=False, item=None, status=None):
    return PokemonSnapshot(
        species=species,
        zh_name=species,
        level=50,
        hp_percent=None if fainted else hp,
        status=status,
        types=("Normal",),
        tera_type=None,
        terastallized=terastallized,
        item=item,
        ability=None,
        moves=(),
        fainted=fainted,
    )


def obs(
    *,
    turn=1,
    my="Me",
    my_hp=100.0,
    opp="Opp",
    opp_hp=100.0,
    opp_team=None,
    revealed=None,
    weather=None,
):
    return BattleObservation(
        battle_tag="b1",
        turn=turn,
        format="gen9bssregi",
        game_type="singles",
        my_active=snap(my, my_hp),
        opponent_active=snap(opp, opp_hp),
        my_team=[snap(my), snap("Bench1"), snap("Bench2")],
        opponent_team=opp_team if opp_team is not None else [snap(opp), snap("O1"), snap("O2")],
        opponent_revealed=revealed or {},
        weather=weather or [],
    )


class TestEventLog(unittest.TestCase):
    def test_append_and_query(self):
        log = EventLog()
        log.log(1, "switch", "opponent", "Dragonite 登场")
        log.log(2, "ko", "opponent", "Dragonite 被击倒", species="Dragonite")
        self.assertEqual(len(log), 2)
        self.assertEqual([e.kind for e in log.by_kind("ko")], ["ko"])
        self.assertEqual(log.tail(1)[0].turn, 2)
        d = log.to_dicts()[1]
        self.assertEqual(d["kind_zh"], "击倒")
        self.assertEqual(d["data"]["species"], "Dragonite")


class TestShortTermMemory(unittest.TestCase):
    def test_first_reveal_creates_switch_event(self):
        memory = ShortTermMemory(battle_tag="b1")
        observation = obs(
            turn=1,
            revealed={"pokemon": {"Dragonite": {"species": "Dragonite", "moves": ["Extreme Speed"], "fainted": False}}},
        )
        events = memory.update_from_observation(observation)
        self.assertTrue(any(e.kind == "switch" for e in events))
        self.assertIn("Dragonite", memory.revealed_pokemon)
        self.assertEqual(memory.revealed_pokemon["Dragonite"].moves, ["Extreme Speed"])

    def test_item_and_tera_reveal_events(self):
        memory = ShortTermMemory(battle_tag="b1")
        first = obs(turn=1, revealed={"pokemon": {"Chien-Pao": {"species": "Chien-Pao", "moves": []}}})
        memory.update_from_observation(first)
        second = obs(
            turn=2,
            revealed={
                "pokemon": {
                    "Chien-Pao": {
                        "species": "Chien-Pao",
                        "moves": ["Ice Spinner"],
                        "item": "Focus Sash",
                        "tera_type": "Ghost",
                    }
                }
            },
        )
        events = memory.update_from_observation(second)
        kinds = {e.kind for e in events}
        self.assertIn("item_reveal", kinds)
        self.assertIn("terastallize", kinds)
        self.assertTrue(memory.tera_used)
        record = memory.revealed_pokemon["Chien-Pao"]
        self.assertEqual(record.item, "Focus Sash")
        self.assertEqual(record.tera_type, "Ghost")

    def test_ko_event_and_belief(self):
        memory = ShortTermMemory(battle_tag="b1")
        memory.update_from_observation(obs(turn=1, revealed={"pokemon": {"X": {"species": "X", "moves": []}}}))
        events = memory.update_from_observation(
            obs(turn=3, revealed={"pokemon": {"X": {"species": "X", "moves": [], "fainted": True}}})
        )
        self.assertTrue(any(e.kind == "ko" for e in events))
        self.assertEqual(memory.current_belief.unseen_count, 5)

    def test_hp_and_weather_history(self):
        memory = ShortTermMemory(battle_tag="b1")
        memory.update_from_observation(obs(turn=1, my_hp=90, opp_hp=80, weather=["RAIN"]))
        memory.update_from_observation(obs(turn=2, my_hp=70, opp_hp=80, weather=["RAIN"]))
        self.assertEqual(len(memory.hp_history), 2)
        self.assertEqual(memory.hp_history[1]["my_active"], 70)
        self.assertEqual(memory.weather_history, ["RAIN"])  # 相同天气不重复记录

    def test_record_action(self):
        memory = ShortTermMemory(battle_tag="b1")
        memory.record_action(1, "move earthquake", "move icebeam")
        self.assertEqual(memory.action_history[0].to_dict(), {"turn": 1, "my_order": "move earthquake", "opponent_order": "move icebeam"})


class TestOpponentModel(unittest.TestCase):
    def test_predict_from_action_history(self):
        memory = ShortTermMemory(battle_tag="b1")
        memory.update_from_observation(
            obs(turn=1, revealed={"pokemon": {"Dragonite": {"species": "Dragonite", "moves": ["Extreme Speed", "Earthquake"]}}})
        )
        memory.record_action(1, "move shadowball", "move extremespeed")
        memory.record_action(2, "move shadowball", "move extremespeed")
        memory.record_action(3, "move shadowball", "move earthquake")
        model = OpponentModel(memory)
        prediction = model.predict_next_move(obs(turn=4, opp="Dragonite"))
        self.assertIsNotNone(prediction)
        self.assertEqual(prediction["predicted_move"], "Extreme Speed")

    def test_switch_tendency_and_threats(self):
        memory = ShortTermMemory(battle_tag="b1")
        memory.update_from_observation(
            obs(turn=1, revealed={"pokemon": {"Chien-Pao": {"species": "Chien-Pao", "moves": ["Sucker Punch"], "item": "Focus Sash"}}})
        )
        model = OpponentModel(memory)
        observation = obs(turn=5, my_hp=20, opp="Chien-Pao", opp_hp=25)
        self.assertEqual(model.switch_tendency(observation), "high")
        threats = " ".join(model.assess_threats(observation))
        self.assertIn("Sucker Punch", threats)
        self.assertIn("Focus Sash", threats)
        self.assertIn("血量危险", threats)


class TestLongTermMemory(unittest.TestCase):
    def test_record_and_roundtrip(self):
        long_term = LongTermMemory()
        long_term.record_battle_result(opponent="RivalA", won=True, my_team_key="bss_balance", my_lead="Gholdengo", summary={"turns": 12})
        long_term.record_battle_result(opponent="RivalA", won=False, my_team_key="bss_balance", my_lead="Gholdengo")
        self.assertEqual(long_term.opponent_stats["RivalA"].battles, 2)
        self.assertEqual(long_term.team_winrate["bss_balance"].win_rate, 0.5)
        self.assertEqual(long_term.most_common_lead("bss_balance"), "Gholdengo")

        data = long_term.to_dict()
        restored = LongTermMemory.from_dict(data)
        self.assertEqual(restored.opponent_stats["RivalA"].wins, 1)
        self.assertEqual(restored.most_common_lead("bss_balance"), "Gholdengo")

    def test_battle_history_capped(self):
        long_term = LongTermMemory()
        for i in range(60):
            long_term.record_battle_result(opponent=f"o{i}", won=True)
        self.assertLessEqual(len(long_term.battle_history), 50)

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory" / "long_term.json"
            long_term = LongTermMemory()
            long_term.record_battle_result(opponent="RivalB", won=True, my_team_key="t1")
            long_term.save(path)
            self.assertTrue(path.exists())
            loaded = LongTermMemory.load(path)
            self.assertEqual(loaded.opponent_stats["RivalB"].battles, 1)

    def test_load_corrupt_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            loaded = LongTermMemory.load(path)
            self.assertEqual(loaded.battle_history, [])


class TestMemoryManager(unittest.TestCase):
    def test_full_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "long_term.json"
            manager = MemoryManager(memory_path=path)

            observation = obs(
                turn=1,
                revealed={"pokemon": {"Dragonite": {"species": "Dragonite", "moves": ["Extreme Speed"]}}},
            )
            events = manager.update_after_turn("b1", observation)
            self.assertTrue(events)

            manager.record_action("b1", 1, "move shadowball", "move extremespeed")
            model = manager.get_opponent_model("b1")
            prediction = model.predict_next_move(replace(observation, opponent_active=snap("Dragonite")))
            self.assertEqual(prediction["predicted_move"], "Extreme Speed")

            manager.update_after_battle(
                "b1", won=True, opponent="RivalA", my_team_key="bss_balance", my_lead="Gholdengo"
            )
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["opponent_stats"]["RivalA"]["wins"], 1)

    def test_short_term_isolated_by_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = MemoryManager(memory_path=Path(tmp) / "m.json")
            manager.update_after_turn("b1", obs(turn=1, revealed={"pokemon": {"A": {"species": "A", "moves": []}}}))
            manager.update_after_turn("b2", obs(turn=1, revealed={"pokemon": {"B": {"species": "B", "moves": []}}}))
            self.assertIn("A", manager.get_short_term("b1").revealed_pokemon)
            self.assertIn("B", manager.get_short_term("b2").revealed_pokemon)


if __name__ == "__main__":
    unittest.main()
