"""建队工具单元测试。"""

import json
import unittest
from pathlib import Path

from pokemon_battle_assistant.tools import (
    TEAM_BUILDER_TOOLS,
    run_tool,
    team_builder_tool_specs,
)
from pokemon_battle_assistant.tools.coverage_analyzer import analyze_coverage
from pokemon_battle_assistant.tools.meta_analyzer import analyze_meta
from pokemon_battle_assistant.tools.synergy_checker import check_synergy
from pokemon_battle_assistant.tools.team_validator import validate_team

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BSS_BALANCE = PROJECT_ROOT / "data" / "teams" / "lab" / "bss_balance.json"

DRAGON_TEAM = [
    {"species": "Garchomp", "moves": ["Earthquake"]},
    {"species": "Dragonite", "moves": ["Earthquake"]},
    {"species": "Salamence", "moves": ["Earthquake"]},
    {"species": "Dragapult", "moves": ["Earthquake"]},
    {"species": "Baxcalibur", "moves": ["Earthquake"]},
    {"species": "Roaring Moon", "moves": ["Earthquake"]},
]


def load_balance() -> dict:
    return json.loads(BSS_BALANCE.read_text(encoding="utf-8"))


class TestMetaAnalyzer(unittest.TestCase):
    def test_returns_top_pokemon_and_samples(self):
        result = analyze_meta("gen9bssregi")
        self.assertTrue(result["ok"])
        self.assertEqual(result["format"], "gen9bssregi")
        self.assertGreater(len(result["top_pokemon"]), 5)
        first = result["top_pokemon"][0]
        self.assertIn("species", first)
        self.assertIn("types", first)
        self.assertIsInstance(first["bst"], int)
        self.assertTrue(result["sample_teams"])


class TestSynergyChecker(unittest.TestCase):
    def test_shared_ice_weakness_detected(self):
        result = check_synergy(DRAGON_TEAM)
        self.assertTrue(result["ok"])
        shared = {w["type"]: w for w in result["shared_weaknesses"]}
        self.assertIn("Ice", shared)
        self.assertGreaterEqual(shared["Ice"]["count"], 3)
        self.assertTrue(result["suggestions"])

    def test_resistances_reported(self):
        result = check_synergy(DRAGON_TEAM)
        self.assertTrue(any(r["type"] == "Fire" for r in result["resistances"]))
        self.assertTrue(result["summary"])


class TestCoverageAnalyzer(unittest.TestCase):
    def test_ground_coverage(self):
        team = [
            {"species": "Garchomp", "moves": ["Earthquake", "Protect"]},
            {"species": "Dragonite", "moves": ["Earthquake"]},
        ]
        result = analyze_coverage(team)
        self.assertTrue(result["ok"])
        self.assertEqual(result["move_types"], ["Ground"])
        self.assertIn("Ground", result["stab_types"])
        self.assertIn("Electric", result["super_effective"])
        self.assertIn("Flying", result["resisted_or_immune"])

    def test_unknown_move_reported(self):
        result = analyze_coverage([{"species": "Garchomp", "moves": ["TotallyNotAMove"]}])
        self.assertEqual(result["move_types"], [])
        self.assertIn("TotallyNotAMove", result["unknown_moves"])


class TestTeamValidator(unittest.TestCase):
    def test_valid_bss_team_passes_local(self):
        result = validate_team(load_balance(), run_showdown=False)
        self.assertTrue(result["valid"], result["errors"])

    def test_invalid_move_fails(self):
        bad = load_balance()
        bad["team"][0]["moves"] = ["Make It Rain", "TotallyNotAMove"]
        result = validate_team(bad, run_showdown=False)
        self.assertFalse(result["valid"])
        self.assertTrue(result["errors"])

    def test_rejects_bad_shape(self):
        result = validate_team({"pokemon": []})
        self.assertFalse(result["valid"])


class TestToolRegistry(unittest.TestCase):
    def test_specs_openai_shape(self):
        specs = team_builder_tool_specs()
        self.assertEqual(len(specs), 4)
        for spec in specs:
            self.assertEqual(spec["type"], "function")
            self.assertIn("name", spec["function"])
            self.assertIn("parameters", spec["function"])
        names = {s["function"]["name"] for s in specs}
        self.assertEqual(names, set(TEAM_BUILDER_TOOLS))

    def test_run_tool_unknown(self):
        result = run_tool("nope", {})
        self.assertFalse(result["ok"])

    def test_run_tool_dispatch(self):
        result = run_tool("synergy_checker", {"team": DRAGON_TEAM})
        self.assertTrue(result["ok"])
        self.assertIn("Ice", [w["type"] for w in result["shared_weaknesses"]])

    def test_run_tool_bad_arguments(self):
        result = run_tool("synergy_checker", {"team": "not-a-list"})
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
