"""Tests for the perception layer (observation / tracker / classifier / summary)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from pokemon_battle_assistant.perception import (
    BattleObservation,
    InfoTracker,
    ObservationBuilder,
    build_summary,
    classify_phase,
)
from pokemon_battle_assistant.perception.observation import MoveInfo, PokemonSnapshot


def make_mon(
    species: str,
    hp: int = 100,
    max_hp: int = 100,
    *,
    moves: dict | None = None,
    item=None,
    ability=None,
    fainted=False,
    terastallized=False,
    tera_type=None,
    types=("Normal",),
    status=None,
    level=50,
):
    return SimpleNamespace(
        species=species,
        current_hp=0 if fainted else hp,
        max_hp=max_hp,
        moves=moves or {},
        item=item,
        ability=ability,
        fainted=fainted,
        terastallized=terastallized,
        tera_type=tera_type,
        types=list(types),
        status=status,
        level=level,
    )


def make_move(move_id: str, *, bp=80, move_type="Normal", category="PHYSICAL", priority=0):
    return SimpleNamespace(
        id=move_id,
        type=move_type,
        base_power=bp,
        accuracy=100,
        category=category,
        priority=priority,
        target="normal",
    )


def make_battle(
    *,
    turn=5,
    my_active=None,
    opp_active=None,
    my_team=None,
    opp_team=None,
    moves=None,
    switches=None,
    weather=None,
):
    return SimpleNamespace(
        battle_tag="battle-test-1",
        turn=turn,
        format="gen9bssregi",
        active_pokemon=my_active,
        opponent_active_pokemon=opp_active,
        team={i: mon for i, mon in enumerate(my_team or [])},
        opponent_team={i: mon for i, mon in enumerate(opp_team or [])},
        available_moves=moves or [],
        available_switches={m.species: m for m in (switches or [])},
        weather=weather or {},
        fields={},
        side_conditions={},
        opponent_side_conditions={},
    )


def snapshot(species: str, hp=100.0, *, fainted=False, terastallized=False, status=None):
    return PokemonSnapshot(
        species=species,
        zh_name=species,
        level=50,
        hp_percent=None if fainted else hp,
        status=status,
        types=("Normal",),
        tera_type=None,
        terastallized=terastallized,
        item=None,
        ability=None,
        moves=(),
        fainted=fainted,
    )


def observation(
    *,
    turn=5,
    my_hp=100.0,
    opp_hp=100.0,
    my_alive=3,
    opp_alive=3,
):
    return BattleObservation(
        battle_tag="b1",
        turn=turn,
        format="gen9bssregi",
        game_type="singles",
        my_active=snapshot("Me", my_hp),
        opponent_active=snapshot("Opp", opp_hp),
        my_team=[snapshot(f"M{i}") for i in range(my_alive)],
        opponent_team=[snapshot(f"O{i}") for i in range(opp_alive)],
    )


class TestObservationBuilder(unittest.TestCase):
    def test_build_basic_observation(self):
        battle = make_battle(
            turn=4,
            my_active=make_mon("Gholdengo", moves={"makeitrain": 2}),
            opp_active=make_mon("Dragonite", moves={"extremespeed": 1}, item="Leftovers"),
            my_team=[make_mon("Gholdengo", moves={"makeitrain": 2}), make_mon("Ting-Lu")],
            opp_team=[make_mon("Dragonite", moves={"extremespeed": 1}), make_mon("Chien-Pao")],
            moves=[make_move("makeitrain", move_type="Steel", category="SPECIAL")],
            switches=[make_mon("Ting-Lu", hp=60, max_hp=100)],
            weather={"SUN": 1},
        )

        obs = ObservationBuilder().build(battle)

        self.assertEqual(obs.turn, 4)
        self.assertEqual(obs.game_type, "singles")
        self.assertEqual(obs.my_active.species, "Gholdengo")
        self.assertEqual(obs.opponent_active.species, "Dragonite")
        self.assertEqual(obs.opponent_active.item, "Leftovers")
        self.assertEqual(len(obs.my_team), 2)
        self.assertEqual(len(obs.opponent_team), 2)
        self.assertEqual(obs.available_moves[0].name, "makeitrain")
        self.assertEqual(obs.available_moves[0].base_power, 80)
        self.assertEqual(obs.available_switches[0].species, "Ting-Lu")
        self.assertEqual(obs.weather, ["SUN"])
        self.assertEqual(obs.phase, "midgame")  # turn=4 已过开局，双方 2v2 存活
        self.assertTrue(obs.summary)

    def test_build_embeds_opponent_revealed(self):
        battle = make_battle(
            turn=2,
            my_active=make_mon("A"),
            opp_active=make_mon("B", moves={"icebeam": 1}, ability="Levitate"),
            my_team=[make_mon("A")],
            opp_team=[make_mon("B", moves={"icebeam": 1}, ability="Levitate")],
        )
        tracker = InfoTracker()
        tracker.update(battle)
        revealed = tracker.get(battle.battle_tag).to_dict()

        obs = ObservationBuilder().build(battle, opponent_revealed=revealed)
        self.assertIn("B", obs.opponent_revealed["pokemon"])
        self.assertEqual(obs.opponent_revealed["pokemon"]["B"]["ability"], "Levitate")


class TestInfoTracker(unittest.TestCase):
    def test_update_accumulates_revealed_info(self):
        battle1 = make_battle(
            turn=1,
            my_active=make_mon("A"),
            opp_active=make_mon("Dragonite", moves={"extremespeed": 1}),
            opp_team=[make_mon("Dragonite", moves={"extremespeed": 1})],
        )
        tracker = InfoTracker()
        info = tracker.update(battle1)
        self.assertEqual(info.revealed_count, 1)
        self.assertEqual(info.pokemon["Dragonite"].moves, ["extremespeed"])

        battle2 = make_battle(
            turn=2,
            my_active=make_mon("A"),
            opp_active=make_mon(
                "Dragonite",
                moves={"extremespeed": 1, "earthquake": 2},
                item="Leftovers",
                terastallized=True,
                tera_type="Normal",
            ),
            opp_team=[
                make_mon(
                    "Dragonite",
                    moves={"extremespeed": 1, "earthquake": 2},
                    item="Leftovers",
                    terastallized=True,
                    tera_type="Normal",
                ),
                make_mon("Chien-Pao"),
            ],
        )
        battle2.battle_tag = battle1.battle_tag
        info = tracker.update(battle2)
        self.assertEqual(info.revealed_count, 2)
        record = info.pokemon["Dragonite"]
        self.assertEqual(record.moves, ["extremespeed", "earthquake"])
        self.assertEqual(record.item, "Leftovers")
        self.assertEqual(record.tera_type, "Normal")
        self.assertTrue(info.tera_used)

    def test_separate_battle_tags_are_isolated(self):
        b1 = make_battle(turn=1, my_active=make_mon("A"), opp_active=make_mon("X"), opp_team=[make_mon("X")])
        b2 = make_battle(turn=1, my_active=make_mon("A"), opp_active=make_mon("Y"), opp_team=[make_mon("Y")])
        b2.battle_tag = "battle-test-2"
        tracker = InfoTracker()
        tracker.update(b1)
        tracker.update(b2)
        self.assertEqual(tracker.get(b1.battle_tag).revealed_count, 1)
        self.assertEqual(tracker.get(b2.battle_tag).revealed_count, 1)


class TestClassifier(unittest.TestCase):
    def test_opening(self):
        self.assertEqual(classify_phase(observation(turn=2)), "opening")

    def test_midgame(self):
        self.assertEqual(classify_phase(observation(turn=6, my_alive=3, opp_alive=3)), "midgame")

    def test_endgame_when_opponent_one_alive(self):
        self.assertEqual(classify_phase(observation(turn=6, opp_alive=1)), "endgame")

    def test_crisis_when_low_hp(self):
        self.assertEqual(classify_phase(observation(turn=6, my_hp=20)), "crisis")

    def test_crisis_when_one_alive(self):
        self.assertEqual(classify_phase(observation(turn=6, my_alive=1)), "crisis")


class TestSummary(unittest.TestCase):
    def test_summary_mentions_key_facts(self):
        obs = observation(turn=6)
        text = build_summary(obs, phase="midgame")
        self.assertIn("第6回合", text)
        self.assertIn("中盘", text)
        self.assertIn("存活 3v3", text)

    def test_summary_includes_weather_and_revealed(self):
        from dataclasses import replace

        obs = observation(turn=6)
        obs = replace(obs, weather=["RAIN"], opponent_revealed={"pokemon": {"Dragonite": {"species": "Dragonite"}}})
        text = build_summary(obs)
        self.assertIn("天气:RAIN", text)
        self.assertIn("对方已揭示:Dragonite", text)


class TestMoveInfo(unittest.TestCase):
    def test_move_info_to_dict(self):
        move = MoveInfo(
            name="earthquake",
            zh_name="地震",
            move_type="Ground",
            base_power=100,
            accuracy=100,
            category="PHYSICAL",
            priority=0,
            target="allAdjacent",
        )
        d = move.to_dict()
        self.assertEqual(d["name"], "earthquake")
        self.assertEqual(d["base_power"], 100)


if __name__ == "__main__":
    unittest.main()
