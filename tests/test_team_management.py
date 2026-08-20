#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""队伍管理（手工导入/调整/删除）+ 种族值 harness 增强 离线测试。

覆盖：importer 解析（英文名/昵称/性别/EV-IV/错误清单）/
导出串→导入 round-trip（真实 teams.db 队伍过 validator）/
repository CRUD（临时库副本）/ skill 契约含 stat_reason / pool 渲染含种族值总和。
"""
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pokemon_battle_assistant.skills.team_building import skill as skill_pkg
from pokemon_battle_assistant.team_builder import (importer, pool, repository,
                                                   validator)

TEAMS_DB = ROOT / "data" / "teams" / "teams.db"


def _paste_from_dex() -> str:
    """真实 dex 英文名拼一段合法 6 只导出串（BSS Lv50）。"""
    conn = sqlite3.connect(f"file:{ROOT / 'data' / 'dex' / 'dex.db'}?mode=ro", uri=True)
    species = ["charizard", "blastoise", "venusaur", "pikachu", "snorlax", "gengar"]
    blocks = []
    for i, sp in enumerate(species):
        name_en, abilities = conn.execute(
            "SELECT name_en, abilities FROM species WHERE id=?", (sp,)).fetchone()
        ab_en = json.loads(abilities)["0"]
        item_en = conn.execute(
            "SELECT name_en FROM items ORDER BY id LIMIT 1 OFFSET ?", (i,)).fetchone()[0]
        moves = [r[0] for r in conn.execute(
            "SELECT m.name_en FROM learnsets l JOIN moves m ON m.id=l.move_id "
            "WHERE l.species_id=? AND m.base_power > 0 "
            "ORDER BY m.base_power DESC LIMIT 4", (sp,))]
        blocks.append(
            f"{name_en} @ {item_en}\nAbility: {ab_en}\nLevel: 50\n"
            "Tera Type: Fire\nEVs: 252 SpA / 4 SpD / 252 Spe\nTimid Nature\n"
            + "\n".join(f"- {mv}" for mv in moves))
    conn.close()
    return "\n\n".join(blocks)


class ImporterParseTest(unittest.TestCase):
    def test_parse_english_names(self):
        members = importer.parse_paste(_paste_from_dex(), default_level=50)
        self.assertEqual(len(members), 6)
        self.assertEqual(members[0]["species"], "charizard")
        self.assertEqual(members[0]["level"], 50)
        self.assertEqual(members[0]["evs"], {"spa": 252, "spd": 4, "spe": 252})
        self.assertEqual(members[0]["nature"], "timid")
        self.assertEqual(members[0]["tera_type"], "Fire")
        self.assertEqual(len(members[0]["moves"]), 4)
        self.assertTrue(members[0]["item"])

    def test_nickname_and_gender(self):
        paste = (" buddy (Pikachu) (M) @ Light Ball\n"
                 "Ability: Static\nLevel: 50\n- Thunderbolt")
        members = importer.parse_paste(paste, default_level=50)
        self.assertEqual(members[0]["species"], "pikachu")
        self.assertEqual(members[0]["item"], "lightball")

    def test_unknown_species(self):
        with self.assertRaises(importer.ImportParseError) as cm:
            importer.parse_paste("Pikachuuuu @ Leftovers\n- Thunderbolt")
        self.assertIn("不认识的宝可梦", str(cm.exception))

    def test_unknown_move(self):
        with self.assertRaises(importer.ImportParseError) as cm:
            importer.parse_paste("Pikachu @ Light Ball\n- Thunderrrr")
        self.assertIn("不认识的招式", str(cm.exception))

    def test_empty(self):
        with self.assertRaises(importer.ImportParseError):
            importer.parse_paste("   ")


class RoundTripTest(unittest.TestCase):
    """现有队伍的导出串 → 解析 → 过 validator（真实数据零错误）。"""

    def test_export_parse_validate(self):
        conn = sqlite3.connect(f"file:{TEAMS_DB}?mode=ro", uri=True)
        row = conn.execute(
            "SELECT export_text, format FROM teams LIMIT 1").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        skill = skill_pkg.load("v1")
        c = skill.constraints(row[1])
        members = importer.parse_paste(row[0], default_level=c["level"])
        errors = validator.validate(
            {"display_name": "rt", "name_en": "rt", "members": members},
            row[1], skill)
        self.assertEqual(errors, [])


class RepositoryCrudTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tmp_db = Path(self.tmpdir) / "teams.db"
        shutil.copy(TEAMS_DB, self.tmp_db)
        self.patcher = mock.patch.object(repository, "TEAMS_DB", self.tmp_db)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _members(self):
        return importer.parse_paste(_paste_from_dex(), default_level=50)

    def test_manual_lifecycle(self):
        saved = repository.save_manual_team("CRUD 测试队", "gen9bssregi", self._members())
        conn = sqlite3.connect(self.tmp_db)
        t = conn.execute("SELECT source, display_name FROM teams WHERE id=?",
                         (saved["id"],)).fetchone()
        self.assertEqual(t, ("manual", "CRUD 测试队"))
        n = conn.execute("SELECT COUNT(*), COUNT(stat_reason) FROM team_members "
                         "WHERE team_id=?", (saved["id"],)).fetchone()
        self.assertEqual(n, (6, 0))  # 手工导入无 stat_reason

        ok = repository.update_team(saved["name"], display_name="改名后的队伍")
        self.assertTrue(ok)
        self.assertEqual(conn.execute("SELECT display_name FROM teams WHERE id=?",
                                      (saved["id"],)).fetchone()[0], "改名后的队伍")

        new_members = self._members()[:6]
        ok = repository.update_team(saved["name"], members=new_members)
        self.assertTrue(ok)
        self.assertIn("charizard", conn.execute(
            "SELECT export_text FROM teams WHERE id=?", (saved["id"],)).fetchone()[0])

        self.assertTrue(repository.delete_team(saved["name"]))
        self.assertIsNone(conn.execute("SELECT 1 FROM teams WHERE id=?",
                                       (saved["id"],)).fetchone())
        self.assertFalse(repository.delete_team(saved["name"]))
        conn.close()


class SkillStatContractTest(unittest.TestCase):
    def test_contract_requires_stat_reason(self):
        sk = skill_pkg.load("v1")
        self.assertIn("stat_reason", sk.team_contract_md)
        self.assertIn("种族值阅读", sk.method_md)

    def test_pool_render_shows_stats_and_bst(self):
        blueprint = {"slots": [{"role_zh": "测试位", "types": [], "stat_min": {},
                                "stat_focus": [], "notes": ""}]}
        pools = [[{"species": "charizard", "name_zh": "喷火龙", "types": "火/飞行",
                   "stats": {"hp": 78, "atk": 84, "def": 78,
                             "spa": 109, "spd": 85, "spe": 100},
                   "bst": 534, "abilities": ["blaze"], "top_moves": []}]]
        text = pool.render_pools(blueprint, pools)
        self.assertIn("78/84/78/109/85/100", text)
        self.assertIn("总和 534", text)


if __name__ == "__main__":
    unittest.main()
