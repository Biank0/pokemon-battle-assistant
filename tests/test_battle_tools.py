"""对战工具（Phase 3.1）单元测试：type_analyzer / damage_calculator / speed_comparator / threat_assessment / ability_lookup / battle_registry。"""

from __future__ import annotations

import unittest

from pokemon_battle_assistant.perception.observation import (
    BattleObservation,
    MoveInfo,
    PokemonSnapshot,
)
from pokemon_battle_assistant.tools.ability_lookup import lookup_ability
from pokemon_battle_assistant.tools.battle_registry import (
    ToolContext,
    battle_tool_specs,
    run_battle_tool,
)
from pokemon_battle_assistant.tools.damage_calculator import estimate_damage
from pokemon_battle_assistant.tools.speed_comparator import compare_speed
from pokemon_battle_assistant.tools.threat_assessment import assess_threat
from pokemon_battle_assistant.tools.type_analyzer import analyze_type, defender_weakness_profile


class TestTypeAnalyzer(unittest.TestCase):
    def test_super_effective(self):
        result = analyze_type("Electric", ["Water"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["multiplier"], 2.0)
        self.assertEqual(result["effectiveness"], "效果拔群")

    def test_double_weakness(self):
        result = analyze_type("Ground", ["Electric", "Poison"])
        self.assertEqual(result["multiplier"], 4.0)

    def test_immune(self):
        result = analyze_type("Ground", ["Flying"])
        self.assertEqual(result["multiplier"], 0.0)
        self.assertEqual(result["effectiveness"], "无效")

    def test_resisted(self):
        result = analyze_type("Fire", ["Fire", "Water"])
        self.assertEqual(result["multiplier"], 0.25)

    def test_unknown_type(self):
        result = analyze_type("Fairy Dust", ["Water"])
        self.assertFalse(result["ok"])

    def test_weakness_profile(self):
        profile = defender_weakness_profile(["Dragon", "Flying"])
        self.assertTrue(profile["ok"])
        self.assertIn("Ice", profile["weaknesses"])
        self.assertIn("Ground", profile["immunities"])
        self.assertEqual(profile["matchups"]["Ice"]["multiplier"], 4.0)


class TestDamageCalculator(unittest.TestCase):
    def test_basic_physical(self):
        result = estimate_damage(
            {"species": "garchomp", "types": ["Dragon", "Ground"]},
            {"species": "tyranitar", "types": ["Rock", "Dark"], "hp_percent": 100},
            {"name": "earthquake"},
        )
        self.assertTrue(result["ok"], result)
        low, high = result["damage_range"]
        self.assertGreaterEqual(low, 1)
        self.assertGreaterEqual(high, low)
        pmin, pmax = result["damage_percent_range"]
        self.assertGreaterEqual(pmin, 0)
        self.assertLessEqual(pmax, 300)
        # 地震打岩石+恶是 2 倍克制 + 本系，伤害应该显著
        self.assertGreaterEqual(pmax, 40)

    def test_stab_flag(self):
        result = estimate_damage(
            {"species": "garchomp", "types": ["Dragon", "Ground"]},
            {"species": "tyranitar", "types": ["Rock", "Dark"]},
            {"name": "earthquake"},
        )
        self.assertTrue(result["stab"])

    def test_status_move_rejected(self):
        result = estimate_damage(
            {"species": "garchomp"},
            {"species": "tyranitar"},
            {"name": "swordsdance"},
        )
        self.assertFalse(result["ok"])

    def test_missing_species(self):
        result = estimate_damage(
            {"types": ["Water"]},
            {"types": ["Fire"]},
            {"name": "surf"},
        )
        self.assertFalse(result["ok"])

    def test_explicit_stats_override(self):
        result = estimate_damage(
            {"species": "garchomp", "attack": 200},
            {"species": "chansey", "defense": 50, "max_hp": 350},
            {"name": "earthquake", "type": "Ground", "base_power": 100, "category": "physical"},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["defender_max_hp_est"], 350)


class TestSpeedComparator(unittest.TestCase):
    def test_faster_by_species(self):
        result = compare_speed({"species": "garchomp"}, {"species": "tyranitar"})
        self.assertTrue(result["ok"])
        self.assertTrue(result["faster"])
        self.assertEqual(result["first_move"], "我方先手")

    def test_paralysis_halves(self):
        base = compare_speed({"species": "garchomp"}, {"species": "garchomp"})
        par = compare_speed({"species": "garchomp", "status": "PAR"}, {"species": "garchomp"})
        self.assertAlmostEqual(base["my_speed"], par["my_speed"] * 2, delta=1.0)

    def test_unknown_species(self):
        result = compare_speed({"species": "???notamon"}, {"species": "garchomp"})
        self.assertFalse(result["ok"])


class TestThreatAssessment(unittest.TestCase):
    def _observation(self) -> BattleObservation:
        mine = PokemonSnapshot(
            species="Tyranitar",
            zh_name="班基拉斯",
            level=50,
            hp_percent=80.0,
            status=None,
            types=("Rock", "Dark"),
            tera_type=None,
            terastallized=False,
            item=None,
            ability=None,
            moves=(" Crunch",),
            fainted=False,
        )
        opp = PokemonSnapshot(
            species="Garchomp",
            zh_name="烈咬陆鲨",
            level=50,
            hp_percent=60.0,
            status=None,
            types=("Dragon", "Ground"),
            tera_type=None,
            terastallized=False,
            item=None,
            ability=None,
            moves=("earthquake",),
            fainted=False,
        )
        moves = [
            MoveInfo(
                name="icebeam",
                zh_name="冰冻光束",
                move_type="Ice",
                base_power=90,
                accuracy=100,
                category="Special",
                priority=0,
                target="normal",
            )
        ]
        return BattleObservation(
            battle_tag="battle-test",
            turn=3,
            format="gen9bssregi",
            game_type="singles",
            my_active=mine,
            opponent_active=opp,
            available_moves=moves,
        )

    def test_assess(self):
        result = assess_threat(self._observation())
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["my_active"], "Tyranitar")
        self.assertEqual(result["opponent_active"], "Garchomp")
        self.assertIn(result["threat_level"], {"high", "medium", "low"})
        self.assertTrue(result["threats"], "应至少评估对方已揭示招式")
        self.assertTrue(result["advice"], "应至少给出一条建议")

    def test_no_active(self):
        obs = BattleObservation(
            battle_tag="b", turn=1, format="gen9bssregi", game_type="singles",
            my_active=None, opponent_active=None,
        )
        result = assess_threat(obs)
        self.assertFalse(result["ok"])


class TestAbilityLookup(unittest.TestCase):
    def test_lookup_species(self):
        result = lookup_ability("garchomp")
        self.assertTrue(result["ok"])
        names = [a["ability"] for a in result["abilities"]]
        self.assertIn("Rough Skin", names)

    def test_lookup_with_item(self):
        result = lookup_ability("garchomp", item="Choice Scarf")
        self.assertTrue(result["ok"])
        self.assertTrue(result["item"]["note"])

    def test_unknown_species(self):
        result = lookup_ability("???notamon")
        self.assertFalse(result["ok"])


class TestBattleRegistry(unittest.TestCase):
    def test_specs_cover_all_tools(self):
        specs = battle_tool_specs()
        names = {s["function"]["name"] for s in specs}
        self.assertEqual(
            names,
            {"type_analyzer", "weakness_profile", "damage_calculator", "speed_comparator", "threat_assessment", "ability_lookup"},
        )

    def test_run_unknown_tool(self):
        result = run_battle_tool("nope", {})
        self.assertFalse(result["ok"])

    def test_run_with_context_defaults(self):
        ctx = ToolContext(observation=None)
        result = run_battle_tool("damage_calculator", {"move": {"name": "surf"}}, ctx)
        self.assertFalse(result["ok"])  # 无上下文且无参数，应失败但不抛异常

    def test_type_analyzer_falls_back_to_context(self):
        from pokemon_battle_assistant.perception.observation import PokemonSnapshot

        opp = PokemonSnapshot(
            species="Garchomp",
            zh_name="烈咬陆鲨",
            level=50,
            hp_percent=100.0,
            status=None,
            types=("Dragon", "Ground"),
            tera_type=None,
            terastallized=False,
            item=None,
            ability=None,
            moves=(),
            fainted=False,
        )
        obs = BattleObservation(
            battle_tag="b",
            turn=1,
            format="gen9bssregi",
            game_type="singles",
            my_active=None,
            opponent_active=opp,
        )
        result = run_battle_tool("type_analyzer", {"move_type": "Ice"}, ToolContext(observation=obs))
        self.assertTrue(result["ok"])
        self.assertEqual(result["multiplier"], 4.0)

    def test_tool_exception_is_caught(self):
        # damage_calculator 传非 dict move 触发参数校验错误，而非异常
        result = run_battle_tool("damage_calculator", {"move": "not-a-dict"}, ToolContext())
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
