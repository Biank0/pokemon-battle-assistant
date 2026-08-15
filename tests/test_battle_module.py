"""Battle Module（Phase 3.3）单元测试：mock Agent 验证 RecordingAgentPlayer 流程与导出。"""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pokemon_battle_assistant.modules.battle.exporter import build_agent_record, export_agent_battle
from pokemon_battle_assistant.perception.observation import BattleObservation


@dataclass(frozen=True)
class FakeTurnDecision:
    order_message: str
    reasoning: str = "测试决策"
    tool_calls_log: list[dict[str, Any]] = field(default_factory=list)
    fallback: bool = False


@dataclass(frozen=True)
class FakePreviewDecision:
    slots: list[int]
    order_message: str
    reasoning: str = "测试选出"
    tool_calls_log: list[dict[str, Any]] = field(default_factory=list)
    fallback: bool = False


class FakeAgent:
    """固定输出的假 BattleAgent。"""

    def __init__(self, order_message: str = "/choose move earthquake") -> None:
        self.order_message = order_message
        self.turn_calls: list[int] = []
        self.preview_calls = 0

    def decide_team_preview(self, observation: BattleObservation, memory: Any = None) -> FakePreviewDecision:
        self.preview_calls += 1
        return FakePreviewDecision(slots=[1, 2, 3], order_message="/team 123")

    def decide_turn(self, observation: BattleObservation, memory: Any = None) -> FakeTurnDecision:
        self.turn_calls.append(observation.turn)
        return FakeTurnDecision(order_message=self.order_message)


class FakeMemory:
    """轻量假记忆管理器（绕过 MemoryManager 的文件落盘）。"""

    def __init__(self) -> None:
        self.updates = 0
        self.after_turns = 0
        self.actions: list[tuple[int, str]] = []
        self._tracker = SimpleNamespace(
            update=lambda battle: SimpleNamespace(
                to_dict=lambda: {"battle_tag": "battle-x", "pokemon": {}, "tera_used": False, "revealed_count": 0}
            )
        )

    def update(self, battle: Any) -> Any:
        self.updates += 1
        return self._tracker.update(battle)

    def update_after_turn(self, battle_tag: str, observation: Any) -> list[Any]:
        self.after_turns += 1
        return []

    def record_action(self, battle_tag: str, turn: int, my_order: str | None, opponent_order: str | None = None) -> None:
        self.actions.append((turn, str(my_order)))

    def get_opponent_model(self, battle_tag: str) -> Any:
        return SimpleNamespace(summary=lambda obs: {})


def make_fake_battle() -> SimpleNamespace:
    def mon(species: str) -> SimpleNamespace:
        return SimpleNamespace(
            species=species,
            level=50,
            current_hp=100,
            max_hp=100,
            status=None,
            types=("Normal",),
            tera_type=None,
            terastallized=False,
            item=None,
            ability=None,
            moves={},
            fainted=False,
        )

    class FakeOrder:
        def __init__(self, message: str) -> None:
            self.message = message

    battle = SimpleNamespace(
        battle_tag="battle-gen9bssregi-test",
        turn=2,
        format="gen9bssregi",
        player_username="player_1",
        opponent_username="player_2",
        active_pokemon=mon("Garchomp"),
        opponent_active_pokemon=mon("Tyranitar"),
        team={0: mon("Garchomp"), 1: mon("Dragonite"), 2: mon("Rotom-Wash")},
        opponent_team={0: mon("Tyranitar"), 1: mon("Gholdengo"), 2: mon("Amoonguss")},
        available_moves=[],
        available_switches={},
        weather={},
        fields={},
        side_conditions={},
        opponent_side_conditions={},
    )
    return battle, FakeOrder


class TestRecordingAgentPlayer(unittest.TestCase):
    def _player(self, agent: FakeAgent):
        from pokemon_battle_assistant.battle_recorder import RecordingAgentPlayer
        from pokemon_battle_assistant.perception.observation import ObservationBuilder

        battle, _ = make_fake_battle()
        del battle
        return RecordingAgentPlayer(
            label="player_1",
            battle_format="gen9bssregi",
            agent=agent,
            memory=FakeMemory(),
            builder=ObservationBuilder(),
        )

    def test_choose_move_flow(self):
        agent = FakeAgent()
        player = self._player(agent)
        battle, _ = make_fake_battle()

        # 手动注入 legal orders（绕过 poke-env legal_orders）
        import pokemon_battle_assistant.battle_recorder as br

        orders = [SimpleNamespace(message="/choose move earthquake"), SimpleNamespace(message="/choose switch garchomp")]
        original = br.legal_orders
        br.legal_orders = lambda b: orders
        try:
            order = player.choose_move(battle)
        finally:
            br.legal_orders = original

        self.assertEqual(order.message, "/choose move earthquake")
        self.assertEqual(agent.turn_calls, [2])
        self.assertEqual(len(player.observations["battle-gen9bssregi-test"]), 1)
        snapshot = player.observations["battle-gen9bssregi-test"][0]
        self.assertEqual(snapshot["chosen_order_message"], "/choose move earthquake")
        self.assertEqual(snapshot["agent_reasoning"], "测试决策")
        decisions = player.agent_decisions["battle-gen9bssregi-test"]
        self.assertEqual(decisions[0]["decision_type"], "turn")
        self.assertEqual(decisions[0]["order_message"], "/choose move earthquake")
        self.assertEqual(player.memory.actions, [(2, "/choose move earthquake")])

    def test_choose_move_falls_back_to_first_order(self):
        agent = FakeAgent(order_message="/choose move surf")  # 非法动作
        player = self._player(agent)
        battle, _ = make_fake_battle()

        import pokemon_battle_assistant.battle_recorder as br

        orders = [SimpleNamespace(message="/choose move earthquake")]
        original = br.legal_orders
        br.legal_orders = lambda b: orders
        try:
            order = player.choose_move(battle)
        finally:
            br.legal_orders = original
        self.assertEqual(order.message, "/choose move earthquake")

    def test_teampreview(self):
        agent = FakeAgent()
        player = self._player(agent)
        battle, _ = make_fake_battle()
        command = player.teampreview(battle)
        self.assertEqual(command, "/team 123")
        record = player.team_selections["battle-gen9bssregi-test"]
        self.assertEqual(record["mode"], "agent")
        self.assertEqual(record["selected_slots"], [1, 2, 3])
        self.assertEqual(player.agent_decisions["battle-gen9bssregi-test"][0]["decision_type"], "team_preview")


class TestExporter(unittest.TestCase):
    def test_build_and_export(self):
        from pokemon_battle_assistant.battle_recorder import battle_summary

        class FakeBattle:
            battle_tag = "battle-gen9bssregi-export"
            format = "gen9bssregi"
            won = True
            turns = 5
            rating = 1000
            rating_delta = 10

            def save_replay(self, path: Any) -> str:
                Path(path).write_text("<html>replay</html>", encoding="utf-8")
                return str(path)

        class FakeSummary:
            pass

        import pokemon_battle_assistant.battle_recorder as br

        original = br.battle_summary
        br.battle_summary = lambda battle: {
            "battle_tag": battle.battle_tag,
            "format": battle.format,
            "gen": 9,
            "won": battle.won,
            "lost": not battle.won,
            "finished": True,
            "turns": battle.turns,
            "player_username": "player_1",
            "opponent_username": "player_2",
            "players": ["player_1", "player_2"],
            "team": [],
            "opponent_team": [],
            "raw_replay_events": [],
        }
        try:
            agent_player = SimpleNamespace(
                observations={"battle-gen9bssregi-export": []},
                team_selections={"battle-gen9bssregi-export": {"mode": "agent"}},
                agent_decisions={
                    "battle-gen9bssregi-export": [
                        {"turn": 1, "decision_type": "turn", "order_message": "/choose move 1", "reasoning": "r", "fallback": False}
                    ]
                },
            )
            opponent_player = SimpleNamespace(observations={}, team_selections={})
            record = build_agent_record(
                battle=FakeBattle(),
                agent_player=agent_player,
                opponent_player=opponent_player,
                battle_format="gen9bssregi",
                player_source="test",
                opponent_source="test",
                agent_backend="openai",
                agent_model="fake",
            )
            self.assertEqual(record["schema_version"], "agent-battle.v1")
            self.assertEqual(len(record["agent_decisions"]), 1)
            self.assertIn("steps", record)

            with tempfile.TemporaryDirectory() as tmp:
                result = export_agent_battle(record, battle=FakeBattle(), output_root=Path(tmp))
                self.assertTrue(result.record_path.exists())
                self.assertTrue(result.report_path.exists())
                self.assertTrue(result.steps_path.exists())
                loaded = json.loads(result.record_path.read_text(encoding="utf-8"))
                self.assertEqual(loaded["agent_decisions"][0]["order_message"], "/choose move 1")
                self.assertEqual(loaded["agent"]["model"], "fake")
        finally:
            br.battle_summary = original
        _ = (battle_summary, FakeSummary)


if __name__ == "__main__":
    unittest.main()
