"""Orchestrator Module 单元测试：注入 fake 依赖验证闭环编排（Phase 5.1）。"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pokemon_battle_assistant.modules.orchestrator import (
    LoopConfig,
    Orchestrator,
)


class FakeBuilder:
    def __init__(self, valid: bool = True) -> None:
        self.valid = valid
        self.calls: list[tuple[str, str]] = []

    def generate_team(self, requirement: str, format: str = "gen9bssregi"):
        self.calls.append(("generate", requirement))
        return self._result("V0")

    def iterate_team(self, team: dict, report: dict, format: str = "gen9bssregi"):
        self.calls.append(("iterate", str(team.get("name"))))
        return self._result(f"V{int(str(team.get('name'))[1:]) + 1}")

    def _result(self, name: str):
        return SimpleNamespace(
            team={"name": name, "format": "gen9bssregi", "team": []},
            valid=self.valid,
            reasoning=f"reasoning {name}",
            validation_errors=[] if self.valid else ["阵容不合法"],
        )


class FakeLabRunner:
    def __init__(self, win_rates: list[float] | None = None) -> None:
        self.win_rates = list(win_rates or [])
        self.configs = []

    async def run(self, config):
        self.configs.append(config)
        if self.win_rates:
            rate = self.win_rates.pop(0)
        else:
            rate = 0.5
        total = max(1, len(config.opponents)) * max(1, config.battles_per_opponent)
        stats = {
            "total_battles": total,
            "wins": int(total * rate),
            "losses": total - int(total * rate),
            "errors": 0,
            "win_rate": rate,
            "by_opponent": {},
        }
        results = [
            SimpleNamespace(battle_tag=f"bat-{len(self.configs)}-{i}", record_path="", won=True, error=None)
            for i in range(min(2, total))
        ]
        return SimpleNamespace(stats=stats, results=results)


class FakeAnalysisEngine:
    def __init__(self) -> None:
        self.analyzed: list[str] = []

    async def analyze_battle(self, battle_tag: str, depth: str = "full", *, record=None) -> str:
        self.analyzed.append(battle_tag)
        return f"aid-{battle_tag}"

    def get_result(self, analysis_id: str):
        return SimpleNamespace(
            strategy_advice={
                "summary": f"总结 {analysis_id}",
                "team_builder_feedback": [f"反馈 {analysis_id}"],
            },
            opponent_profile={"style": "均衡"},
        )


def make_orchestrator(tmp: str, builder=None, lab=None) -> tuple[Orchestrator, FakeBuilder, FakeLabRunner, FakeAnalysisEngine]:
    builder = builder or FakeBuilder()
    lab = lab or FakeLabRunner()
    engine = FakeAnalysisEngine()
    orch = Orchestrator(
        team_builder=builder,
        lab_runner=lab,
        analysis_engine=engine,
        output_root=Path(tmp),
    )
    return orch, builder, lab, engine


class ClosedLoopTests(unittest.TestCase):
    def test_auto_loop_runs_all_iterations(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch, builder, lab, engine = make_orchestrator(tmp)
            config = LoopConfig(opponents=["rival"], battles_per_opponent=1, output_root=Path(tmp))
            run_id = asyncio.run(orch.start_closed_loop("电系快攻队", max_iterations=3, config=config))

            status = orch.get_status(run_id)
            self.assertEqual(status.state, "completed")
            self.assertEqual(status.current_iteration, 3)
            self.assertEqual(len(builder.calls), 3)
            self.assertEqual(builder.calls[0][0], "generate")
            self.assertEqual(builder.calls[1][0], "iterate")
            self.assertEqual(len(engine.analyzed), 3)  # 每轮 1 个可分析对局 × 3 轮
            self.assertEqual(len(lab.configs), 3)

            history = orch.get_iteration_history(run_id)
            self.assertEqual([record.iteration for record in history], [0, 1, 2])
            self.assertTrue(all(record.valid for record in history))
            self.assertEqual(status.best_iteration, 0)

            run_dir = Path(tmp) / run_id
            self.assertTrue((run_dir / "final_summary.md").is_file())
            for index in range(3):
                iter_dir = run_dir / f"iteration_{index}"
                for name in ("team.json", "lab_report.json", "analysis_report.md", "iteration.json"):
                    self.assertTrue((iter_dir / name).is_file(), f"iteration_{index}/{name}")
                team_data = json.loads((iter_dir / "team.json").read_text(encoding="utf-8"))
                self.assertEqual(team_data["team"]["name"], f"V{index}")

    def test_manual_mode_waits_for_confirm(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch, _, _, _ = make_orchestrator(tmp)
            config = LoopConfig(opponents=["rival"], battles_per_opponent=1, output_root=Path(tmp))
            run_id = asyncio.run(
                orch.start_closed_loop("需求", max_iterations=2, auto_iterate=False, config=config)
            )
            status = orch.get_status(run_id)
            self.assertEqual(status.state, "waiting_confirm")
            self.assertEqual(status.current_iteration, 1)

            async def confirm_twice():
                await orch.confirm_iteration(run_id)
                return orch.get_status(run_id).state

            state = asyncio.run(confirm_twice())
            self.assertEqual(state, "completed")
            self.assertEqual(orch.get_status(run_id).current_iteration, 2)

    def test_confirm_when_not_waiting_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch, _, _, _ = make_orchestrator(tmp)
            config = LoopConfig(opponents=["rival"], battles_per_opponent=1, output_root=Path(tmp))
            run_id = asyncio.run(
                orch.start_closed_loop("需求", max_iterations=1, config=config)
            )
            self.assertEqual(orch.get_status(run_id).state, "completed")
            with self.assertRaises(RuntimeError):
                asyncio.run(orch.confirm_iteration(run_id))

    def test_stop_win_rate_early(self):
        with tempfile.TemporaryDirectory() as tmp:
            lab = FakeLabRunner(win_rates=[1.0, 0.2, 0.2])
            orch, builder, _, _ = make_orchestrator(tmp, lab=lab)
            config = LoopConfig(
                opponents=["rival"],
                battles_per_opponent=1,
                stop_win_rate=0.9,
                output_root=Path(tmp),
            )
            run_id = asyncio.run(orch.start_closed_loop("需求", max_iterations=3, config=config))
            status = orch.get_status(run_id)
            self.assertEqual(status.state, "completed")
            self.assertEqual(status.current_iteration, 1)  # 第 1 轮达标后提前结束
            self.assertEqual(len(builder.calls), 1)

    def test_invalid_team_marks_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch, _, _, _ = make_orchestrator(tmp, builder=FakeBuilder(valid=False))
            config = LoopConfig(opponents=["rival"], battles_per_opponent=1, output_root=Path(tmp))
            run_id = asyncio.run(orch.start_closed_loop("需求", max_iterations=3, config=config))
            status = orch.get_status(run_id)
            self.assertEqual(status.state, "error")
            self.assertIn("合法性校验", status.message)
            history = orch.get_iteration_history(run_id)
            self.assertEqual(len(history), 1)
            self.assertIsNotNone(history[0].error)
            run_dir = Path(tmp) / run_id
            self.assertTrue((run_dir / "final_summary.md").is_file())

    def test_best_iteration_picks_highest_win_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            lab = FakeLabRunner(win_rates=[0.2, 0.8, 0.4])
            orch, _, _, _ = make_orchestrator(tmp, lab=lab)
            config = LoopConfig(opponents=["rival"], battles_per_opponent=1, output_root=Path(tmp))
            run_id = asyncio.run(orch.start_closed_loop("需求", max_iterations=3, config=config))
            status = orch.get_status(run_id)
            self.assertEqual(status.best_iteration, 1)
            self.assertEqual(status.best_win_rate, 0.8)

    def test_unknown_run_raises_key_error(self):
        orch = Orchestrator(output_root="unused")
        with self.assertRaises(KeyError):
            orch.get_status("no-such-run")
        with self.assertRaises(KeyError):
            orch.get_iteration_history("no-such-run")


if __name__ == "__main__":
    unittest.main()
