from __future__ import annotations

import unittest

from pokemon_battle_assistant.action_space import chosen_action_from_message, legal_actions_from_snapshot
from pokemon_battle_assistant.environment import BattleRunConfig, build_step_records, control_kind, infer_battle_kind


class ActionSpaceTest(unittest.TestCase):
    def test_legal_actions_prefer_raw_order_messages(self) -> None:
        snapshot = {
            "available_moves": [{"id": "thunderbolt", "name": "Thunderbolt"}],
            "legal_order_messages": ["/choose move thunderbolt", "/choose switch Pikachu"],
        }

        actions = legal_actions_from_snapshot(snapshot)

        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]["kind"], "order")
        self.assertEqual(actions[0]["command"], "/choose move thunderbolt")

    def test_legal_actions_keep_double_battle_order_messages(self) -> None:
        snapshot = {
            "game_type": "doubles",
            "legal_order_messages": ["/choose move heatwave -1, move protect"],
        }

        actions = legal_actions_from_snapshot(snapshot)

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["kind"], "order")
        self.assertEqual(actions[0]["command"], "/choose move heatwave -1, move protect")

    def test_legal_actions_fallback_to_moves_and_switches(self) -> None:
        snapshot = {
            "available_moves": [{"id": "thunderbolt", "name": "Thunderbolt"}],
            "available_switches": [{"species": "Pikachu"}],
        }

        actions = legal_actions_from_snapshot(snapshot)

        self.assertEqual([a["kind"] for a in actions], ["move", "switch"])
        self.assertEqual(actions[0]["action_id"], "move:thunderbolt")
        self.assertEqual(actions[1]["action_id"], "switch:Pikachu")

    def test_chosen_action_from_message(self) -> None:
        action = chosen_action_from_message("/choose move thunderbolt")
        self.assertIsNotNone(action)
        self.assertEqual(action["kind"], "move")
        self.assertEqual(action["command"], "/choose move thunderbolt")


class EnvironmentRecordTest(unittest.TestCase):
    def test_config_serializes_path_and_metadata(self) -> None:
        config = BattleRunConfig(battle_format="gen9ou", player_1_control="manual", metadata={"entrypoint": "unit-test"})
        data = config.to_dict()

        self.assertEqual(data["battle_format"], "gen9ou")
        self.assertEqual(data["output_root"], "battle_outputs")
        self.assertEqual(data["metadata"]["entrypoint"], "unit-test")
        self.assertEqual(data["player_1_control"], "manual")

    def test_battle_kind_and_control_labels(self) -> None:
        self.assertEqual(infer_battle_kind("gen9ou"), "singles")
        self.assertEqual(infer_battle_kind("gen9randomdoublesbattle"), "doubles")
        self.assertIn("用户手动", control_kind("manual"))

    def test_build_step_records_adds_legal_and_chosen_actions(self) -> None:
        record = {
            "battle": {"finished": True},
            "player_1_observations": [
                {
                    "battle_tag": "battle-test-1",
                    "format": "gen9ou",
                    "turn": 1,
                    "legal_order_messages": ["/choose move thunderbolt"],
                    "chosen_order_message": "/choose move thunderbolt",
                }
            ],
            "player_2_observations": [],
        }

        steps = build_step_records(record)

        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["legal_actions"][0]["command"], "/choose move thunderbolt")
        self.assertEqual(steps[0]["chosen_action"]["kind"], "move")
        self.assertIsNone(steps[0]["done"])
        self.assertTrue(steps[0]["info"]["episode_finished"])


if __name__ == "__main__":
    unittest.main()
