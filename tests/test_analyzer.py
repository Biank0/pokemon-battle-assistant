"""模块三（分析 bot）离线单测：validator 闸门 / distiller 蒸馏 / repository 存取。

不调 LLM、不起服务。LLM 链路由 tests/manual/smoke_analyze.py 覆盖。
"""
import json
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokemon_battle_assistant.battle_analyzer import distiller, repository, validator

ROOT = Path(__file__).resolve().parents[1]


def _fixture_distilled():
    return {
        "session_meta": {
            "session_id": "s1", "team_a": "小边的王牌", "team_b": "BSS 平衡轴",
            "format": "gen9bssregi", "rounds": 3, "score": "1-2",
            "team_a_wins": 1, "team_b_wins": 2, "team_a_win_rate": 33.3,
            "avg_turns": 6.0, "min_turns": 5, "max_turns": 7,
        },
        "pokemon_profiles": [
            {"side": "a", "species_zh": "波荡水", "appearance": 3, "appearance_rate": "100%",
             "switched_in": 3, "switched_out": 1,
             "moves_used": [{"move_zh": "流星群", "count": 6}]},
            {"side": "b", "species_zh": "快龙", "appearance": 2, "appearance_rate": "67%",
             "switched_in": 2, "switched_out": 0,
             "moves_used": [{"move_zh": "地震", "count": 4}]},
        ],
        "matchup_matrix": [{"attacker_zh": "波荡水", "defender_zh": "快龙", "attacks": 5}],
        "sample_timelines": [
            {"round_no": 1, "winner": "a", "end_turn": 7, "battle_id": "b1",
             "actions": [{"turn": 1, "side": "a", "action": "波荡水 使用 流星群 → 快龙"},
                         {"turn": 2, "side": "b", "action": "快龙 使用 地震 → 波荡水"}]},
        ],
    }


def _valid_report(d):
    return {
        "title": "测试复盘", "headline": "晴轴运转顺畅", "rating": "B",
        "win_loss_read": "样本 3 轮，仅供参考。",
        "pokemon_performance": [
            {"species_zh": "波荡水", "side": "a", "role": "特攻输出", "appearance": 3,
             "moves_used": [{"move_zh": "流星群", "count": 6}], "verdict": "核心输出。",
             "issues": []},
        ],
        "matchups": [{"attacker_zh": "波荡水", "defender_zh": "快龙", "read": "互有往来"}],
        "threats": [{"from_zh": "快龙", "why": "地震反复命中", "counter": "换飞行系"}],
        "highlights": [{"round_no": 1, "turn": 1, "side": "a", "what": "首发对位"}],
        "recommendations": [
            {"priority": "高", "target": "波荡水", "change": "换招", "reason": "降速"},
            {"priority": "中", "target": "首发选择", "change": "改换联防起手", "reason": "首发被克制"},
        ],
    }


class ValidatorTest(unittest.TestCase):
    def setUp(self):
        self.d = _fixture_distilled()

    def test_valid_report_passes(self):
        errs = validator.validate_report(_valid_report(self.d), self.d)
        self.assertEqual(errs, [], f"合法报告不应报错: {errs}")

    def test_hallucinated_species(self):
        r = _valid_report(self.d)
        r["pokemon_performance"][0]["species_zh"] = "梦幻"
        errs = validator.validate_report(r, self.d)
        self.assertTrue(any("不在出场档案" in e for e in errs))

    def test_hallucinated_move(self):
        r = _valid_report(self.d)
        r["pokemon_performance"][0]["moves_used"] = [{"move_zh": "破坏光线", "count": 1}]
        errs = validator.validate_report(r, self.d)
        self.assertTrue(any("未使用过招式" in e for e in errs))

    def test_wrong_side(self):
        r = _valid_report(self.d)
        r["pokemon_performance"][0]["side"] = "b"  # 波荡水是 a 方
        errs = validator.validate_report(r, self.d)
        self.assertTrue(any("属于" in e for e in errs))

    def test_bad_rating(self):
        r = _valid_report(self.d)
        r["rating"] = "SSS"
        errs = validator.validate_report(r, self.d)
        self.assertTrue(any("rating 非法" in e for e in errs))

    def test_highlight_wrong_turn(self):
        r = _valid_report(self.d)
        r["highlights"][0]["turn"] = 99
        errs = validator.validate_report(r, self.d)
        self.assertTrue(any("采样时间线" in e for e in errs))

    def test_bad_priority(self):
        r = _valid_report(self.d)
        r["recommendations"][0]["priority"] = "紧急"
        errs = validator.validate_report(r, self.d)
        self.assertTrue(any("priority" in e for e in errs))


class DistillerRealDbTest(unittest.TestCase):
    """对真实 battles.db 的最近 completed 会话做蒸馏（有数据则测，无则跳过）。"""

    def test_distill_latest_session(self):
        conn = sqlite3.connect(f"file:{ROOT / 'data/battles/battles.db'}?mode=ro", uri=True)
        sid = conn.execute(
            "SELECT id FROM battle_sessions WHERE status='completed' "
            "ORDER BY started_at DESC LIMIT 1").fetchone()
        conn.close()
        if not sid:
            self.skipTest("battles.db 无 completed 会话（先跑一次实验室）")
        d = distiller.distill_session(sid[0])
        sm = d["session_meta"]
        self.assertIn("score", sm)
        self.assertTrue(d["pokemon_profiles"], "档案不应为空")
        for p in d["pokemon_profiles"]:
            self.assertIn("appearance_rate", p)
        self.assertTrue(d["sample_timelines"])
        # 文本可序列化（喂 LLM 的最终形态）
        text = distiller.to_prompt_text(d)
        self.assertLess(len(text), 60_000, "蒸馏文本超预算")


class RepositoryRoundTripTest(unittest.TestCase):
    """save → list/get → 清理（真实 analysis.db，测后删干净）。"""

    def test_round_trip(self):
        d = _fixture_distilled()
        r = _valid_report(d)
        aid = repository.save(r, d, d["session_meta"], "test-model", "v1")
        try:
            listed = repository.list_analyses()
            hit = [x for x in listed if x["id"] == aid]
            self.assertEqual(len(hit), 1)
            self.assertEqual(hit[0]["rating"], "B")
            doc = repository.get_doc(aid)
            self.assertEqual(doc["report"]["headline"], "晴轴运转顺畅")
            self.assertTrue(doc["highlight_links"], "高光跳转行应写入")
            hl = doc["highlight_links"][0]
            self.assertEqual(hl["battle_id"], "b1")  # round_no 1 → 采样场次 b1
            md = (ROOT / "data/analysis/docs" / f"{aid}.md").read_text(encoding="utf-8")
            self.assertIn("## 改进建议", md)
        finally:
            conn = sqlite3.connect(ROOT / "data/analysis/analysis.db")
            conn.execute("DELETE FROM analysis_highlights WHERE analysis_id=?", (aid,))
            conn.execute("DELETE FROM analyses WHERE id=?", (aid,))
            conn.commit()
            conn.close()
            for suf in (".json", ".md"):
                (ROOT / "data/analysis/docs" / f"{aid}{suf}").unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
