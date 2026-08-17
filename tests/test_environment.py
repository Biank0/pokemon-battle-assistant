from __future__ import annotations

import unittest

from pokemon_battle_assistant.action_space import chosen_action_from_message, legal_actions_from_snapshot
from pokemon_battle_assistant.environment import (
    BattleRunConfig,
    build_step_records,
    control_kind,
    infer_battle_kind,
)
from pokemon_battle_assistant.pba_cli import resolve_trainer_path
from pokemon_battle_assistant.showdown_formats import get_format_info
from pokemon_battle_assistant.team_selection import parse_selection, validate_selected_slots


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

    def test_chosen_double_order_stays_atomic_order(self) -> None:
        action = chosen_action_from_message("/choose move heatwave -1, move protect")
        self.assertIsNotNone(action)
        self.assertEqual(action["kind"], "order")
        self.assertEqual(action["command"], "/choose move heatwave -1, move protect")


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


class FriendlyCliTest(unittest.TestCase):
    def test_resolve_trainer_path_accepts_team_name_and_json_file_name(self) -> None:
        self.assertTrue(resolve_trainer_path("xiaobian").as_posix().endswith("data/teams/lab/xiaobian.json"))
        self.assertTrue(resolve_trainer_path("xiaobian.json").as_posix().endswith("data/teams/lab/xiaobian.json"))


class TeamSelectionTest(unittest.TestCase):
    def test_parse_fixed_selection(self) -> None:
        config = parse_selection("1,2,3,4")

        self.assertEqual(config.mode, "fixed")
        self.assertEqual(config.fixed_order, (1, 2, 3, 4))

    def test_validate_selected_slots_rejects_duplicates(self) -> None:
        with self.assertRaises(ValueError):
            validate_selected_slots([1, 1, 2, 3], required_count=4, team_size=6)

    def test_vgc_format_info_has_pick_four(self) -> None:
        info = get_format_info("gen9vgc2026regi")

        self.assertEqual(info.game_type, "doubles")
        self.assertEqual(info.picked_team_size, 4)


if __name__ == "__main__":
    unittest.main()


class TrainerValidationTest(unittest.TestCase):
    def test_validate_xiaobian_template(self) -> None:
        from pokemon_battle_assistant.validators import validate_trainer_template

        result = validate_trainer_template("data/teams/lab/xiaobian.json")

        self.assertTrue(result.ok, result.to_dict())

    def test_validate_rejects_chinese_move_name(self) -> None:
        import json
        import tempfile
        from pathlib import Path

        from pokemon_battle_assistant.validators import validate_trainer_template

        payload = {
            "name": "bad",
            "format": "gen9ou",
            "team": [{"species": "Pikachu", "moves": ["十万伏特"]}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = validate_trainer_template(path)

        self.assertFalse(result.ok)
        self.assertTrue(any("中文" in error for error in result.errors))

    def test_validate_rejects_wrong_ability_for_species(self) -> None:
        import json
        import tempfile
        from pathlib import Path

        from pokemon_battle_assistant.validators import validate_trainer_template

        payload = {
            "name": "bad",
            "format": "gen9ou",
            "team": [{"species": "Pikachu", "ability": "Intimidate", "moves": ["Thunderbolt"]}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = validate_trainer_template(path)

        self.assertFalse(result.ok)
        self.assertTrue(any("不能使用特性" in error for error in result.errors))

    def test_showdown_validator_rejects_unlearnable_move(self) -> None:
        from pokemon_battle_assistant.showdown_validator import find_showdown_path, validate_showdown_team

        if find_showdown_path() is None:
            self.skipTest("local pokemon-showdown checkout not found")

        result = validate_showdown_team(
            "Pikachu\nAbility: Static\nEVs: 252 Atk / 4 SpD / 252 Spe\n- Spore\n",
            "gen9ou",
        )

        self.assertTrue(result.checked)
        self.assertFalse(result.ok)
        self.assertTrue(any("can't learn Spore" in error for error in result.errors))


class EnvCheckTest(unittest.TestCase):
    def test_env_check_result_serializes(self) -> None:
        from pokemon_battle_assistant.env_check import EnvCheckResult

        result = EnvCheckResult()
        result.add("unit", True, "ok")

        self.assertTrue(result.ok)
        self.assertEqual(result.to_dict()["items"][0]["name"], "unit")
