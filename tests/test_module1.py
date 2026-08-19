#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模块一（AI 建队）离线测试——FakeHarness 固定响应，不花 token。

覆盖：skill 加载 / planner 规范化 / pool 筛选 / validator 五闸门 /
repository 写入契约 / pipeline 修复循环（FakeHarness + 临时库）。
"""
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pokemon_battle_assistant.skills.team_building import skill as skill_pkg
from pokemon_battle_assistant.team_builder import (builder, planner, pool,
                                                   repository, validator)
from pokemon_battle_assistant.team_builder.pipeline import generate_team

DEX_DB = ROOT / "data" / "dex" / "dex.db"


def dex_conn():
    conn = sqlite3.connect(f"file:{DEX_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------- fixtures
def valid_team_from_dex(format_id="gen9bssregi") -> dict:
    """从真实 dex 构造一支保证合法的队伍（物种/特性/招式全查库取）。"""
    conn = dex_conn()
    species = ["charizard", "blastoise", "venusaur", "pikachu", "snorlax", "gengar"]
    items = [r[0] for r in conn.execute("SELECT id FROM items ORDER BY id LIMIT 6")]
    members = []
    for i, sp in enumerate(species):
        row = conn.execute("SELECT abilities FROM species WHERE id=?", (sp,)).fetchone()
        abilities = [planner.slugify(a)
                     for a in json.loads(row["abilities"]).values() if a]
        moves = [r[0] for r in conn.execute(
            "SELECT m.id FROM learnsets l JOIN moves m ON m.id=l.move_id "
            "WHERE l.species_id=? AND m.base_power > 0 "
            "ORDER BY m.base_power DESC LIMIT 4", (sp,))]
        members.append({
            "slot_role": f"测试位{i+1}", "species": sp,
            "ability": abilities[0], "item": items[i], "nature": "timid",
            "tera_type": "Fire", "level": 50 if format_id != "gen9ou" else 100,
            "moves": moves,
            "evs": {"hp": 0, "atk": 0, "def": 0, "spa": 252, "spd": 4, "spe": 252},
            "ivs": {"hp": 31, "atk": 31, "def": 31, "spa": 31, "spd": 31, "spe": 31},
        })
    conn.close()
    return {"name_en": "offline_test_team", "display_name": "离线测试队",
            "strategy_notes": "测试", "members": members}


class FakeHarness:
    """按序返回固定响应的假 harness（不联网）。"""
    model = "fake-model"

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls = []

        class _S:
            def summary(self):
                return "fake stats"

        self.stats = _S()

    def chat(self, messages, *, json_mode=False, temperature=0.7):
        self.calls.append(messages)
        if not self.responses:
            raise AssertionError("FakeHarness 响应队列已空")
        return self.responses.pop(0)


# ---------------------------------------------------------------- skill
class TestSkill(unittest.TestCase):
    def setUp(self):
        self.skill = skill_pkg.load("v1")

    def test_constraints_three_formats(self):
        for fid, lvl, dup in (("gen9bssregi", 50, False), ("gen9vgc2026regi", 50, False),
                              ("gen9ou", 100, True)):
            c = self.skill.constraints(fid)
            self.assertEqual(c["level"], lvl)
            self.assertEqual(c["allow_dup_items"], dup)

    def test_unknown_format_raises(self):
        with self.assertRaises(KeyError):
            self.skill.constraints("gen8anythinggoes")

    def test_prompt_contains_knowledge(self):
        bp = self.skill.blueprint_prompt("gen9bssregi", "晴天队")
        self.assertIn("角色位", bp[0]["content"])
        self.assertIn("等级：50", bp[0]["content"])
        b = self.skill.builder_prompt("gen9bssregi", {"strategy": "x", "slots": []}, "池")
        self.assertIn("建队方法论", b[0]["content"])
        self.assertIn("输出格式", b[0]["content"])
        r = self.skill.repair_prompt("gen9bssregi", {}, "池", "{}", ["槽位1：错误"])
        self.assertIn("错误清单", r[-1]["content"])


# ---------------------------------------------------------------- planner
class TestPlanner(unittest.TestCase):
    def test_parse_llm_json_with_fences(self):
        text = "好的，这是蓝图：\n```json\n{\"strategy\": \"s\", \"slots\": []}\n```\n完毕"
        self.assertEqual(planner.parse_llm_json(text)["strategy"], "s")

    def test_plan_normalizes(self):
        bp_json = json.dumps({
            "strategy": "晴天下压制",
            "slots": [
                {"role_zh": "日照手", "types": ["fire", "NotAType"], "stat_min": {"spe": 90, "bad": 999},
                 "stat_focus": ["spa", "spe", "hp"], "notes": "n"},
                {"role_zh": "输出", "types": [], "stat_min": {}, "stat_focus": []},
                {"role_zh": "自由位", "types": [], "stat_min": {}},
            ]}, ensure_ascii=False)
        h = FakeHarness([bp_json])
        bp = planner.plan(h, skill_pkg.load("v1"), "晴天队", "gen9bssregi")
        self.assertEqual(len(bp["slots"]), 3)
        self.assertEqual(bp["slots"][0]["types"], ["Fire"])       # 非法属性剔除+标准化
        self.assertEqual(bp["slots"][0]["stat_min"], {"spe": 90})  # 非法键剔除
        self.assertEqual(bp["slots"][0]["stat_focus"], ["spa", "spe"])  # 最多2项

    def test_plan_rejects_bad_slot_count(self):
        h = FakeHarness([json.dumps({"strategy": "s", "slots": [{"role_zh": "a"}]})])
        with self.assertRaises(ValueError):
            planner.plan(h, skill_pkg.load("v1"), "x", "gen9bssregi")


# ---------------------------------------------------------------- pool
class TestPool(unittest.TestCase):
    def test_pool_fire_fast_includes_ninetales(self):
        conn = pool._connect()
        try:
            slot = {"role_zh": "日照启动手", "types": ["Fire"], "abilities_preferred": [],
                    "stat_min": {"spe": 90}, "stat_focus": ["spe"], "notes": ""}
            p = pool.build_pool(conn, slot)
            ids = [x["species"] for x in p]
            self.assertIn("charizard", ids)
            self.assertFalse(any("mega" in i or "gmax" in i for i in ids))  # 特殊形态已排除
            cz = next(x for x in p if x["species"] == "charizard")
            self.assertIn("blaze", cz["abilities"])      # 特性渲染为 slug
            self.assertTrue(cz["top_moves"])            # 代表招非空
            self.assertLessEqual(len(p), pool.POOL_LIMIT)
        finally:
            conn.close()

    def test_pool_relaxes_on_empty(self):
        conn = pool._connect()
        try:
            slot = {"role_zh": "矛盾位", "types": ["Ice"],
                    "stat_min": {"spe": 130, "atk": 130},  # 极苛刻 → 自动放宽
                    "abilities_preferred": [], "stat_focus": [], "notes": ""}
            p = pool.build_pool(conn, slot)
            self.assertGreaterEqual(len(p), pool.MIN_KEEP)
        finally:
            conn.close()

    def test_render_pools(self):
        blueprint = {"strategy": "s", "slots": [
            {"role_zh": "火速攻", "types": ["Fire"], "stat_min": {"spe": 100},
             "stat_focus": ["spe"], "notes": ""}]}
        _, text = pool.build_pools(blueprint)
        self.assertIn("角色位1：火速攻", text)
        self.assertIn("速≥100", text)


# ---------------------------------------------------------------- validator
class TestValidator(unittest.TestCase):
    def setUp(self):
        self.skill = skill_pkg.load("v1")

    def test_valid_team_passes(self):
        errors = validator.validate(valid_team_from_dex(), "gen9bssregi", self.skill)
        self.assertEqual(errors, [], f"合法队伍不应有错误: {errors}")

    def test_gate_learnability(self):  # 闸门4：喷火龙学不会蘑菇孢子
        team = valid_team_from_dex()
        team["members"][0]["moves"][0] = "spore"
        errors = validator.validate(team, "gen9bssregi", self.skill)
        self.assertTrue(any("学不会" in e for e in errors))

    def test_gate_learnability_form_fallback(self):  # 闸门4：形态→基础形态回退
        conn = dex_conn()
        team = valid_team_from_dex()
        # 土地云灵兽形态：learnsets 挂在基础形态 landorus 名下
        row = conn.execute("SELECT base_species FROM species WHERE id='landorustherian'").fetchone()
        self.assertEqual(row[0], "landorus")
        team["members"][0]["species"] = "landorustherian"
        ab = list(json.loads(conn.execute(
            "SELECT abilities FROM species WHERE id='landorustherian'").fetchone()[0]).values())
        team["members"][0]["ability"] = planner.slugify(ab[0])
        team["members"][0]["moves"] = [r[0] for r in conn.execute(
            "SELECT m.id FROM learnsets l JOIN moves m ON m.id=l.move_id "
            "WHERE l.species_id='landorus' AND m.base_power > 0 "
            "ORDER BY m.base_power DESC LIMIT 4")]
        conn.close()
        errors = validator.validate(team, "gen9bssregi", self.skill)
        self.assertFalse(any("学不会" in e for e in errors),
                         f"形态回退应放行: {[e for e in errors if '学不会' in e]}")

    def test_gate_existence(self):  # 闸门2
        team = valid_team_from_dex()
        team["members"][0]["moves"][0] = "notamove123"
        team["members"][1]["species"] = "notapokemon"
        errors = validator.validate(team, "gen9bssregi", self.skill)
        self.assertTrue(any("不在招式库" in e for e in errors))
        self.assertTrue(any("不在图鉴" in e for e in errors))

    def test_gate_ability_ownership(self):  # 闸门3：特性不属于该物种
        team = valid_team_from_dex()
        team["members"][0]["ability"] = "intimidate"
        errors = validator.validate(team, "gen9bssregi", self.skill)
        self.assertTrue(any("没有特性" in e for e in errors))

    def test_gate_dup_items_bss(self):  # 闸门5：BSS 道具重复
        team = valid_team_from_dex()
        team["members"][1]["item"] = team["members"][0]["item"]
        errors = validator.validate(team, "gen9bssregi", self.skill)
        self.assertTrue(any("道具重复" in e for e in errors))

    def test_gate_dup_items_ou_allowed(self):
        team = valid_team_from_dex("gen9ou")
        team["members"][1]["item"] = team["members"][0]["item"]
        errors = validator.validate(team, "gen9ou", self.skill)
        self.assertFalse(any("道具重复" in e for e in errors))

    def test_gate_level_and_count(self):
        team = valid_team_from_dex()
        team["members"][0]["level"] = 100
        team["members"].pop()
        errors = validator.validate(team, "gen9bssregi", self.skill)
        self.assertTrue(any("等级" in e for e in errors))
        self.assertTrue(any("成员数" in e for e in errors))

    def test_gate_ev_bounds(self):
        team = valid_team_from_dex()
        team["members"][0]["evs"] = {"hp": 300, "atk": 0, "def": 0, "spa": 252, "spd": 0, "spe": 252}
        errors = validator.validate(team, "gen9bssregi", self.skill)
        self.assertTrue(any("EV 非法" in e for e in errors))
        team["members"][0]["evs"] = {"hp": 252, "atk": 252, "def": 100, "spa": 0, "spd": 0, "spe": 252}
        errors = validator.validate(team, "gen9bssregi", self.skill)
        self.assertTrue(any("EV 总和" in e for e in errors))


# ---------------------------------------------------------------- repository
class TestRepository(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "teams.db"
        shutil.copy(ROOT / "data" / "teams" / "teams.db", self.db)
        self._orig = repository.TEAMS_DB
        repository.TEAMS_DB = self.db

    def tearDown(self):
        repository.TEAMS_DB = self._orig
        self.tmp.cleanup()

    def test_save_and_conflict_suffix(self):
        team = valid_team_from_dex()
        r1 = repository.save_team(team, format_id="gen9bssregi", requirement="r",
                                  skill_version="v1", model="m")
        r2 = repository.save_team(valid_team_from_dex(), format_id="gen9bssregi",
                                  requirement="r", skill_version="v1", model="m")
        self.assertEqual(r1["name"], "offline_test_team")
        self.assertEqual(r2["name"], "offline_test_team-2")  # 冲突自动后缀，不覆盖

        conn = sqlite3.connect(self.db)
        row = conn.execute("SELECT source,requirement_prompt,skill_version,model,"
                           "display_name,export_text FROM teams WHERE name=?", (r1["name"],)).fetchone()
        self.assertEqual(row[0], "ai")                       # 溯源五件套
        self.assertEqual(row[2], "v1")
        self.assertIn("Level: 50", row[5])                   # export_text 规则
        self.assertIn("EVs:", row[5])
        n = conn.execute("SELECT COUNT(*) FROM team_members WHERE team_id=?",
                         (r1["id"],)).fetchone()[0]
        self.assertEqual(n, 6)
        conn.close()


# ---------------------------------------------------------------- pipeline
class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "teams.db"
        shutil.copy(ROOT / "data" / "teams" / "teams.db", self.db)
        self._orig = repository.TEAMS_DB
        repository.TEAMS_DB = self.db
        import pokemon_battle_assistant.team_builder.pipeline as pl
        self._pp = pl._p
        pl._p = lambda msg: None

    def tearDown(self):
        repository.TEAMS_DB = self._orig
        import pokemon_battle_assistant.team_builder.pipeline as pl
        pl._p = self._pp
        self.tmp.cleanup()

    def test_repair_loop_then_saved(self):
        good = valid_team_from_dex()
        bad = json.loads(json.dumps(good))
        bad["members"][0]["moves"][0] = "spore"              # 第一轮非法 → 触发修复
        bp = {"strategy": "测试主线", "slots": [
            {"role_zh": "位A", "types": ["Fire"], "stat_min": {"spe": 90}, "stat_focus": ["spe"]},
            {"role_zh": "位B", "types": [], "stat_min": {}, "stat_focus": []},
            {"role_zh": "位C", "types": [], "stat_min": {}, "stat_focus": []}]}
        h = FakeHarness([json.dumps(bp, ensure_ascii=False),
                         json.dumps(bad, ensure_ascii=False),
                         json.dumps(good, ensure_ascii=False)])
        res = generate_team("离线测试需求", format_id="gen9bssregi", harness=h)
        self.assertEqual(res.attempts, 2)                    # build + 1 次 repair
        self.assertEqual(res.name, "offline_test_team")
        conn = sqlite3.connect(self.db)
        n = conn.execute("SELECT COUNT(*) FROM teams WHERE name=?", (res.name,)).fetchone()[0]
        self.assertEqual(n, 1)
        conn.close()

    def test_fail_after_three_repairs(self):
        bad = valid_team_from_dex()
        bad["members"][0]["moves"][0] = "spore"
        bp = {"strategy": "s", "slots": [{"role_zh": "a", "types": [], "stat_min": {}}] * 3}
        h = FakeHarness([json.dumps(bp)] + [json.dumps(bad)] * 4)  # build+3 repair 全失败
        from pokemon_battle_assistant.team_builder.pipeline import TeamBuildError
        with self.assertRaises(TeamBuildError):
            generate_team("x", format_id="gen9bssregi", harness=h)


if __name__ == "__main__":
    unittest.main()
