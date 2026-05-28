from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pokemon_battle_assistant.cli import load_battle_state
from pokemon_battle_assistant.evaluator import evaluate_battle
from pokemon_battle_assistant.type_chart import describe_multiplier, get_type_multiplier
from pokemon_battle_assistant.translation import translate_ability, translate_item, translate_move, translate_pokemon


class TranslationTest(unittest.TestCase):
    def test_local_chinese_name_table(self) -> None:
        self.assertEqual(translate_pokemon("wochien"), "古简蜗")
        self.assertEqual(translate_move("knockoff"), "拍落")
        self.assertEqual(translate_item("leftovers"), "吃剩的东西")
        self.assertEqual(translate_ability("intimidate"), "威吓")

    def test_showdown_form_fallback(self) -> None:
        self.assertEqual(translate_pokemon("basculegionf"), "幽尾玄鱼（雌性）")
        self.assertEqual(translate_pokemon("taurospaldeablaze"), "肯泰罗（帕底亚火炽种）")


class TypeChartTest(unittest.TestCase):
    def test_combined_type_multiplier(self) -> None:
        self.assertEqual(get_type_multiplier("Grass", ["Water", "Fighting"]), 2.0)
        self.assertEqual(get_type_multiplier("Electric", ["Water", "Flying"]), 4.0)
        self.assertEqual(get_type_multiplier("Ground", ["Flying"]), 0.0)

    def test_chinese_multiplier_description(self) -> None:
        self.assertEqual(describe_multiplier(4.0), "四倍克制")
        self.assertEqual(describe_multiplier(2.0), "效果拔群")
        self.assertEqual(describe_multiplier(0.0), "无效")


class MvpEvaluatorTest(unittest.TestCase):
    def test_simple_battle_prefers_stab_super_effective_move(self) -> None:
        state = load_battle_state(Path("examples/simple_battle.json"))
        evaluations = evaluate_battle(state)

        self.assertGreater(len(evaluations), 0)
        best = evaluations[0]
        self.assertEqual(best.action.name, "Flower Trick")
        self.assertEqual(best.confidence, "high")
        self.assertIn("ko-pressure", best.tags)

    def test_loader_accepts_minimal_json(self) -> None:
        payload = {
            "rule_set": "unit_test_demo",
            "my_active": {"name": "Pikachu", "types": ["Electric"], "hp_percent": 80},
            "opponent_active": {"name": "Gyarados", "types": ["Water", "Flying"], "hp_percent": 100},
            "available_actions": [
                {"kind": "move", "name": "Thunderbolt", "move_type": "Electric", "power": 90}
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "battle.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            state = load_battle_state(path)

        evaluations = evaluate_battle(state)
        self.assertEqual(state.rule_set, "unit_test_demo")
        self.assertEqual(evaluations[0].score, 67)
        self.assertIn("四倍克制", " ".join(evaluations[0].reasons))


if __name__ == "__main__":
    unittest.main()
