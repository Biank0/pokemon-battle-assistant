"""Analysis Module 单元测试：mock LLM 验证报告结构（Phase 4.2）。"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pokemon_battle_assistant.modules.analysis.advisor import StrategyAdvisor
from pokemon_battle_assistant.modules.analysis.engine import AnalysisEngine, find_record_path
from pokemon_battle_assistant.modules.analysis.profiler import OpponentProfiler
from pokemon_battle_assistant.modules.analysis.replayer import BattleReplayer
from pokemon_battle_assistant.modules.analysis.reviewer import DecisionReviewer


class FakeLLM:
    """返回固定内容的假 LLM（duck-type chat 接口）。"""

    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    def chat(self, messages, **kwargs):  # noqa: ARG002
        self.calls += 1
        return SimpleNamespace(content=self.content)


def make_mon(species, hp=1.0, fainted=False, item=None, ability=None):
    return {
        "species": species,
        "base_species": species,
        "types": [],
        "hp_fraction": hp,
        "status": "濒死" if fainted else None,
        "item": item,
        "ability": ability,
        "stats": {},
        "moves": [],
        "fainted": fainted,
        "active": False,
    }


def make_obs(turn, team, opp_team, chosen, active=None, opp_active=None, switches=None):
    return {
        "observer": "player_1",
        "battle_tag": "battle-test",
        "turn": turn,
        "format": "gen9bssregi",
        "active_pokemon": active,
        "opponent_active_pokemon": opp_active,
        "team": team,
        "opponent_team": opp_team,
        "available_moves": [],
        "available_switches": switches if switches is not None else [],
        "legal_order_messages": ["move thunderbolt", "switch snorlax"],
        "chosen_order_message": chosen,
        "weather": [],
        "fields": [],
        "side_conditions": [],
        "opponent_side_conditions": [],
    }


def make_p2_obs(turn, team, opp_team, chosen):
    return {
        "observer": "player_2",
        "battle_tag": "battle-test",
        "turn": turn,
        "format": "gen9bssregi",
        "team": team,
        "opponent_team": opp_team,
        "chosen_order_message": chosen,
        "legal_order_messages": [],
        "available_switches": [],
    }


def make_record():
    pikachu = make_mon("pikachu")
    charizard = make_mon("charizard")
    snorlax = make_mon("snorlax")
    lapras = make_mon("lapras", item="leftovers", ability="shellarmor")
    gyarados = make_mon("gyarados")

    p1_team_t1 = [dict(pikachu), dict(charizard), dict(snorlax)]
    p1_team_t2 = [dict(pikachu, hp_fraction=0.1), dict(charizard, hp_fraction=0.0, fainted=True), dict(snorlax)]
    p1_team_t3 = [dict(pikachu, hp_fraction=0.1), dict(charizard, hp_fraction=0.0, fainted=True), dict(snorlax)]

    opp_team_t1 = [dict(lapras), dict(gyarados)]
    opp_team_t2 = [dict(lapras, hp_fraction=0.0, fainted=True), dict(gyarados)]

    observations_p1 = [
        make_obs(
            1,
            p1_team_t1,
            opp_team_t1,
            "move thunderbolt",
            active=dict(pikachu, active=True),
            opp_active=dict(lapras, active=True),
        ),
        make_obs(
            2,
            p1_team_t2,
            opp_team_t2,
            "move quickattack",
            active=dict(pikachu, hp_fraction=0.1, active=True),
            opp_active=dict(gyarados, active=True),
            switches=[dict(snorlax)],
        ),
        make_obs(
            3,
            p1_team_t3,
            opp_team_t2,
            "switch snorlax",
            active=dict(pikachu, hp_fraction=0.1, active=True),
            opp_active=dict(gyarados, active=True),
            switches=[dict(snorlax)],
        ),
    ]
    observations_p2 = [
        make_p2_obs(1, [dict(lapras), dict(gyarados)], [dict(pikachu)], "move icebeam"),
        make_p2_obs(2, [dict(lapras), dict(gyarados)], [dict(pikachu)], "switch gyarados"),
        make_p2_obs(3, [dict(lapras), dict(gyarados)], [dict(pikachu)], "move surf"),
    ]

    decisions = [
        {
            "turn": 0,
            "decision_type": "team_preview",
            "order_message": "team 1,2,3",
            "reasoning": "按对位选出",
            "tool_calls": [],
            "fallback": False,
            "model": "test",
            "backend": "openai",
            "elapsed_ms": 10,
        },
        {
            "turn": 1,
            "decision_type": "turn",
            "order_message": "move thunderbolt",
            "reasoning": "电系打水系优势",
            "tool_calls": [],
            "fallback": False,
            "model": "test",
            "backend": "openai",
            "elapsed_ms": 12,
        },
        {
            "turn": 2,
            "decision_type": "turn",
            "order_message": "move quickattack",
            "reasoning": "想抢先手击倒",
            "tool_calls": [],
            "fallback": False,
            "model": "test",
            "backend": "openai",
            "elapsed_ms": 15,
        },
        {
            "turn": 3,
            "decision_type": "turn",
            "order_message": "switch snorlax",
            "reasoning": "保存皮卡丘",
            "tool_calls": [],
            "fallback": True,
            "model": "test",
            "backend": "openai",
            "elapsed_ms": 5,
        },
    ]

    return {
        "schema_version": "agent-battle.v1",
        "battle_format": "gen9bssregi",
        "player_source": "me",
        "opponent_source": "rival",
        "battle": {
            "battle_tag": "battle-test",
            "format": "gen9bssregi",
            "gen": 9,
            "turns": 3,
            "finished": True,
            "won": True,
            "lost": False,
            "player_username": "me",
            "opponent_username": "rival",
            "players": ["me", "rival"],
            "team": p1_team_t3,
            "opponent_team": opp_team_t2,
            "raw_replay_events": [],
        },
        "player_1_observations": observations_p1,
        "player_2_observations": observations_p2,
        "team_preview": {
            "player_1": {
                "player": "player_1",
                "battle_tag": "battle-test",
                "selected_slots": [1, 2, 3],
                "command": "team 1,2,3",
            },
            "player_2": None,
        },
        "agent_decisions": decisions,
        "steps": [],
    }


class BattleReplayerTests(unittest.TestCase):
    def test_extracts_key_events(self):
        timeline = BattleReplayer().replay(make_record())
        kinds = [(event.kind, event.player) for event in timeline.events]
        self.assertIn(("knockout", "player_1"), kinds)  # 我方喷火龙倒下
        self.assertIn(("knockout", "player_2"), kinds)  # 对手拉普拉斯倒下
        self.assertIn(("switch", "player_1"), kinds)
        self.assertIn(("switch", "player_2"), kinds)
        self.assertIn(("team_preview", "player_1"), kinds)
        self.assertIn(2, timeline.key_turns)
        self.assertIn(3, timeline.key_turns)
        self.assertTrue(timeline.summary)


class DecisionReviewerTests(unittest.TestCase):
    def test_rule_fallback_ratings(self):
        reviews = DecisionReviewer().review(make_record())
        by_turn = {review.turn: review for review in reviews}
        self.assertEqual(set(by_turn), {1, 2, 3})  # team_preview 决策被跳过
        self.assertEqual(by_turn[1].rating, "good")
        self.assertEqual(by_turn[2].rating, "mistake")  # 残血硬拼且有换人选项
        self.assertEqual(by_turn[3].rating, "average")  # 回退决策
        self.assertTrue(all(review.source == "rule" for review in reviews))

    def test_llm_review_used_when_available(self):
        llm = FakeLLM('{"rating": "average", "comment": "教练点评", "alternative": "换人更好"}')
        reviews = DecisionReviewer(llm=llm).review(make_record())
        self.assertEqual(llm.calls, 3)
        self.assertTrue(all(review.source == "llm" for review in reviews))
        self.assertEqual(reviews[0].comment, "教练点评")

    def test_llm_invalid_json_falls_back_to_rules(self):
        reviews = DecisionReviewer(llm=FakeLLM("这不是 JSON")).review(make_record())
        self.assertTrue(all(review.source == "rule" for review in reviews))


class OpponentProfilerTests(unittest.TestCase):
    def test_profile_structure(self):
        profile = OpponentProfiler().profile(make_record())
        self.assertEqual(profile["actions_total"], 3)
        self.assertEqual(profile["switch_count"], 1)
        self.assertAlmostEqual(profile["switch_rate"], 0.333)
        self.assertEqual(profile["style"], "均衡")
        self.assertIn("lapras", profile["revealed_pokemon"])
        self.assertIn("gyarados", profile["revealed_pokemon"])
        self.assertIn("leftovers", profile["revealed_items"])
        self.assertIn("shellarmor", profile["revealed_abilities"])
        self.assertTrue(profile["next_battle_tips"])


class StrategyAdvisorTests(unittest.TestCase):
    def test_rule_advice_structure(self):
        record = make_record()
        reviews = DecisionReviewer().review(record)
        advice = StrategyAdvisor().advise(record, reviews, {"style": "均衡", "next_battle_tips": ["保持对位"]})
        for key in (
            "team_selection_assessment",
            "lead_analysis",
            "key_turn_alternatives",
            "opponent_adjustments",
            "team_builder_feedback",
            "summary",
        ):
            self.assertIn(key, advice)
        self.assertIsInstance(advice["team_builder_feedback"], list)
        self.assertTrue(advice["key_turn_alternatives"])

    def test_llm_advice_overrides_rules(self):
        payload = json.dumps(
            {
                "team_selection_assessment": "LLM 选出点评",
                "lead_analysis": "LLM 首发分析",
                "key_turn_alternatives": ["回合 2：换上卡比兽"],
                "opponent_adjustments": ["准备电系反制"],
                "team_builder_feedback": ["加入地面系成员"],
                "summary": "LLM 总结",
            },
            ensure_ascii=False,
        )
        record = make_record()
        reviews = DecisionReviewer().review(record)
        advice = StrategyAdvisor(llm=FakeLLM(payload)).advise(record, reviews, {})
        self.assertEqual(advice["summary"], "LLM 总结")
        self.assertEqual(advice["team_builder_feedback"], ["加入地面系成员"])


class AnalysisEngineTests(unittest.TestCase):
    def test_end_to_end_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = AnalysisEngine(output_root=Path(tmp))
            analysis_id = asyncio.run(engine.analyze_battle("battle-test", record=make_record()))
            report = engine.get_result(analysis_id)
            self.assertEqual(report.battle_tag, "battle-test")
            self.assertEqual(len(report.decision_review), 3)

            out_dir = Path(tmp) / "battle-test"
            for name in (
                "decision_review.json",
                "strategy_advice.json",
                "opponent_profile.json",
                "analysis_report.md",
                "analysis.json",
            ):
                self.assertTrue((out_dir / name).is_file(), name)

            review_data = json.loads((out_dir / "decision_review.json").read_text(encoding="utf-8"))
            self.assertEqual(len(review_data), 3)
            markdown = (out_dir / "analysis_report.md").read_text(encoding="utf-8")
            self.assertIn("对战深度分析", markdown)
            self.assertIn("对手画像", markdown)
            self.assertEqual(engine.list_analyses()[0]["analysis_id"], analysis_id)

    def test_get_result_unknown_id_raises(self):
        engine = AnalysisEngine(output_root="unused")
        with self.assertRaises(KeyError):
            engine.get_result("no-such-id")

    def test_find_record_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_dir = root / "battle_outputs" / "bat-xyz"
            record_dir.mkdir(parents=True)
            (record_dir / "record.json").write_text("{}", encoding="utf-8")
            found = find_record_path("bat-xyz", roots=[root / "battle_outputs"])
            self.assertEqual(found, record_dir / "record.json")
            with self.assertRaises(FileNotFoundError):
                find_record_path("missing", roots=[root / "battle_outputs"])


if __name__ == "__main__":
    unittest.main()
