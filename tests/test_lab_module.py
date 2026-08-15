"""Lab Module（Phase 4.1）单元测试：mock 对战函数验证调度、统计与报告。"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from pokemon_battle_assistant.modules.lab.config import BatchConfig
from pokemon_battle_assistant.modules.lab.reporter import LabReporter, build_markdown
from pokemon_battle_assistant.modules.lab.runner import BattleTaskResult, LabRunner
from pokemon_battle_assistant.modules.lab.stats import StatsCollector


def fake_battle_outcomes(script: dict[str, str]) -> object:
    """返回按 opponent 决定胜负的假 run_battle。"""

    async def run_battle(task, config):
        outcome = script.get(task.opponent, "win")
        if outcome == "error":
            return BattleTaskResult(task_id=task.task_id, opponent=task.opponent, error="连接失败")
        return BattleTaskResult(
            task_id=task.task_id,
            opponent=task.opponent,
            won=outcome == "win",
            turns=12,
            battle_tag=f"battle-{task.task_id}",
            selected_slots=[1, 3, 5],
        )

    return run_battle


class TestBatchConfig(unittest.TestCase):
    def test_total_and_tasks(self):
        config = BatchConfig(team="t", opponents=["a", "b"], battles_per_opponent=3)
        self.assertEqual(config.total_battles(), 6)
        tasks = config.battle_tasks()
        self.assertEqual(len(tasks), 6)
        self.assertEqual(tasks[0].opponent, "a")
        self.assertEqual(tasks[0].battle_index, 1)
        self.assertEqual(tasks[-1].opponent, "b")
        self.assertEqual(tasks[-1].battle_index, 3)


class TestLabRunner(unittest.TestCase):
    def test_run_three_battles(self):
        config = BatchConfig(team="t", opponents=["a"], battles_per_opponent=3, concurrency=2)
        runner = LabRunner(run_battle=fake_battle_outcomes({"a": "win"}))
        report = asyncio.run(runner.run(config))
        self.assertEqual(len(report.results), 3)
        self.assertEqual(report.stats["total_battles"], 3)
        self.assertEqual(report.stats["wins"], 3)
        self.assertEqual(report.stats["win_rate"], 1.0)
        self.assertEqual(report.stats["avg_turns"], 12.0)
        self.assertEqual(report.config["total_battles"], 3)

    def test_mixed_and_errors(self):
        calls: list[str] = []

        async def run_battle(task, config):
            calls.append(task.task_id)
            if task.opponent == "bad":
                return BattleTaskResult(task_id=task.task_id, opponent=task.opponent, error="boom")
            return BattleTaskResult(
                task_id=task.task_id,
                opponent=task.opponent,
                won=task.battle_index == 1,
                turns=8,
                selected_slots=[2, 1, 4],
            )

        config = BatchConfig(team="t", opponents=["good", "bad"], battles_per_opponent=2, concurrency=1)
        report = asyncio.run(LabRunner(run_battle=run_battle).run(config))
        self.assertEqual(len(report.results), 4)
        stats = report.stats
        self.assertEqual(stats["total_battles"], 4)
        self.assertEqual(stats["errors"], 2)
        self.assertEqual(stats["wins"], 1)
        self.assertEqual(stats["losses"], 1)
        # 错误局不计入 win_rate 分母
        self.assertEqual(stats["win_rate"], 0.5)
        self.assertEqual(stats["by_opponent"]["bad"]["errors"], 2)
        self.assertEqual(len(calls), 4)


class TestStatsCollector(unittest.TestCase):
    def test_slot_frequency(self):
        stats = StatsCollector()
        stats.add("a", won=True, turns=10, selected_slots=[1, 2, 3])
        stats.add("a", won=False, turns=20, selected_slots=[1, 4, 3])
        summary = stats.summary()
        self.assertEqual(summary["lead_slot_frequency"], {"1": 2})
        self.assertEqual(summary["member_slot_frequency"]["1"], 2)
        self.assertEqual(summary["member_slot_frequency"]["3"], 2)
        self.assertEqual(summary["win_rate"], 0.5)


class TestReporter(unittest.TestCase):
    def test_write_summary(self):
        config = BatchConfig(team="t", opponents=["a"], battles_per_opponent=2)
        runner = LabRunner(run_battle=fake_battle_outcomes({"a": "win"}))
        report = asyncio.run(runner.run(config))
        with tempfile.TemporaryDirectory() as tmp:
            json_path, md_path = LabReporter().write(report.to_dict(), Path(tmp))
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema_version"], "lab-report.v1")
            self.assertEqual(len(loaded["results"]), 2)
            md = md_path.read_text(encoding="utf-8")
            self.assertIn("Lab 批量对战报告", md)
            self.assertIn("| a |", md)

    def test_markdown_win_rate_text(self):
        md = build_markdown({"stats": {"win_rate": 0.75, "by_opponent": {}, "lead_slot_frequency": {}, "member_slot_frequency": {}}})
        self.assertIn("75.0%", md)


if __name__ == "__main__":
    unittest.main()
