"""Orchestrator：闭环流程调度（建队 → Lab 跑量 → Analysis 复盘 → 迭代优化）。

所有重依赖（TeamBuilderAgent / LabRunner / AnalysisEngine）都支持注入，
测试时可传 fake 对象，生产环境缺省延迟创建真实实现。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..lab.config import BatchConfig
from ..team_builder.result import team_hash
from .record import DEFAULT_OUTPUT_ROOT, IterationRecord, LoopConfig, OrchestratorStatus


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _result_field(item: Any, name: str) -> str:
    if isinstance(item, dict):
        return str(item.get(name) or "")
    return str(getattr(item, name, "") or "")


def _result_has_error(item: Any) -> bool:
    if isinstance(item, dict):
        return bool(item.get("error"))
    return bool(getattr(item, "error", None))


@dataclass
class _RunState:
    """单个闭环 run 的内部状态。"""

    run_id: str
    requirement: str
    config: LoopConfig
    status: OrchestratorStatus
    run_dir: Path
    records: list[IterationRecord] = field(default_factory=list)
    last_team: dict[str, Any] | None = None
    last_report: dict[str, Any] | None = None


class Orchestrator:
    """闭环流程调度器。"""

    def __init__(
        self,
        llm: Any | None = None,
        *,
        team_builder: Any | None = None,
        lab_runner: Any | None = None,
        analysis_engine: Any | None = None,
        output_root: Path | str = DEFAULT_OUTPUT_ROOT,
    ) -> None:
        self.llm = llm
        self._team_builder = team_builder
        self._lab_runner = lab_runner
        self._analysis_engine = analysis_engine
        self.output_root = Path(output_root)
        self._runs: dict[str, _RunState] = {}

    # ---- 对外接口 -------------------------------------------------------

    async def start_closed_loop(
        self,
        requirement: str,
        max_iterations: int = 3,
        auto_iterate: bool = True,
        *,
        config: LoopConfig | None = None,
    ) -> str:
        """启动闭环流程（建队 → Lab → Analysis → 迭代），返回 run_id。"""
        loop_config = config or LoopConfig()
        run_id = f"run-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}"
        run_dir = Path(loop_config.output_root) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        status = OrchestratorStatus(
            run_id=run_id,
            requirement=requirement,
            state="running",
            max_iterations=max(0, max_iterations),
            auto_iterate=auto_iterate,
            message="闭环流程启动",
            started_at=_now(),
        )
        state = _RunState(
            run_id=run_id,
            requirement=requirement,
            config=loop_config,
            status=status,
            run_dir=run_dir,
        )
        self._runs[run_id] = state

        if status.max_iterations <= 0:
            status.state = "completed"
            status.message = "迭代轮数为 0，直接结束"
            self._finish(state)
            return run_id

        await self._run_iteration(state)

        if status.state != "error" and not self._reached_target(state):
            if auto_iterate:
                while status.current_iteration < status.max_iterations and status.state != "error":
                    if self._reached_target(state):
                        status.message += "；达到目标胜率，提前结束"
                        break
                    await self._run_iteration(state)
                if status.state != "error":
                    status.state = "completed"
            else:
                status.state = "waiting_confirm"
                status.message = f"第 1 轮完成，等待确认后继续（{status.current_iteration}/{status.max_iterations}）"

        if status.state == "error":
            self._finish(state)
            return run_id
        if self._reached_target(state) and status.state not in ("completed",):
            status.state = "completed"
        self._finish(state)
        return run_id

    async def confirm_iteration(self, run_id: str) -> str:
        """手动模式下，用户确认后继续下一轮迭代，返回最新状态。"""
        state = self._runs[run_id]
        status = state.status
        if status.state != "waiting_confirm":
            raise RuntimeError(f"当前状态是 {status.state}，不需要确认（仅 waiting_confirm 可确认）")
        status.state = "running"
        await self._run_iteration(state)
        if status.state == "error":
            self._finish(state)
            return status.state
        if status.current_iteration >= status.max_iterations or self._reached_target(state):
            status.state = "completed"
            self._finish(state)
        else:
            status.state = "waiting_confirm"
            status.message = (
                f"第 {status.current_iteration} 轮完成，等待确认后继续"
                f"（{status.current_iteration}/{status.max_iterations}）"
            )
        return status.state

    def get_status(self, run_id: str) -> OrchestratorStatus:
        """查询闭环进度（不存在时抛 KeyError）。"""
        return self._runs[run_id].status

    def get_iteration_history(self, run_id: str) -> list[IterationRecord]:
        """获取所有轮次的记录，方便对比。"""
        return list(self._runs[run_id].records)

    # ---- 单轮执行 -------------------------------------------------------

    async def _run_iteration(self, state: _RunState) -> None:
        status = state.status
        index = status.current_iteration
        status.state = "running"
        status.message = f"第 {index + 1} 轮：{'初始建队' if index == 0 else '迭代建队'}中"

        record = IterationRecord(iteration=index, created_at=_now())
        builder = self._ensure_team_builder()
        try:
            if index == 0 or state.last_team is None:
                build = builder.generate_team(state.requirement, format=state.config.battle_format)
            else:
                build = builder.iterate_team(
                    state.last_team,
                    state.last_report or {},
                    format=state.config.battle_format,
                )
        except Exception as exc:  # noqa: BLE001
            record.error = f"建队失败：{exc}"
            state.records.append(record)
            self._mark_error(state, record.error)
            return

        team = dict(getattr(build, "team", {}) or {})
        record.team = team
        record.team_hash = team_hash(team)
        record.valid = bool(getattr(build, "valid", False))
        if not record.valid:
            errors = list(getattr(build, "validation_errors", []) or [])
            record.error = "建队结果未通过合法性校验：" + ("; ".join(errors) or "未知错误")
            state.records.append(record)
            self._mark_error(state, record.error)
            return

        iter_dir = state.run_dir / f"iteration_{index}"
        iter_dir.mkdir(parents=True, exist_ok=True)
        record.output_dir = str(iter_dir)
        team_path = iter_dir / "team.json"
        team_path.write_text(
            json.dumps(
                {
                    "team": team,
                    "team_hash": record.team_hash,
                    "iteration": index,
                    "reasoning": str(getattr(build, "reasoning", "") or ""),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        # ---- Lab 批量对战 ----
        status.message = f"第 {index + 1} 轮：Lab 批量对战中"
        lab_config = BatchConfig(
            team=str(team_path),
            opponents=list(state.config.opponents),
            battles_per_opponent=state.config.battles_per_opponent,
            battle_format=state.config.battle_format,
            concurrency=state.config.concurrency,
            backend=state.config.backend,
            model=state.config.model,
            output_root=iter_dir / "lab",
        )
        try:
            lab_report = await self._ensure_lab_runner().run(lab_config)
        except Exception as exc:  # noqa: BLE001
            record.error = f"Lab 批量对战失败：{exc}"
            state.records.append(record)
            self._mark_error(state, record.error)
            return

        stats = dict(getattr(lab_report, "stats", {}) or {})
        record.win_rate = stats.get("win_rate")
        record.wins = int(stats.get("wins", 0) or 0)
        record.total_battles = int(stats.get("total_battles", 0) or 0)
        try:
            lab_payload: dict[str, Any] = dict(lab_report.to_dict())
        except AttributeError:
            lab_payload = {"stats": stats}
        (iter_dir / "lab_report.json").write_text(
            json.dumps(lab_payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        # ---- Analysis 深度复盘 ----
        status.message = f"第 {index + 1} 轮：Analysis 深度复盘中"
        analysis_ids: list[str] = []
        advice_list: list[dict[str, Any]] = []
        profile_list: list[dict[str, Any]] = []
        results = list(getattr(lab_report, "results", []) or [])
        targets = [
            item
            for item in results
            if _result_field(item, "battle_tag") and not _result_has_error(item)
        ][: max(0, state.config.analysis_battles_limit)]
        engine = self._ensure_analysis_engine()
        analysis_errors: list[str] = []
        for item in targets:
            battle_tag = _result_field(item, "battle_tag")
            record_path = _result_field(item, "record_path")
            record_dict: dict[str, Any] | None = None
            if record_path and Path(record_path).is_file():
                try:
                    record_dict = json.loads(Path(record_path).read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    record_dict = None
            try:
                analysis_id = await engine.analyze_battle(battle_tag, record=record_dict)
            except Exception as exc:  # noqa: BLE001
                analysis_errors.append(f"{battle_tag}: {exc}")
                continue
            analysis_ids.append(analysis_id)
            try:
                result = engine.get_result(analysis_id)
                advice_list.append(dict(getattr(result, "strategy_advice", {}) or {}))
                profile_list.append(dict(getattr(result, "opponent_profile", {}) or {}))
            except Exception as exc:  # noqa: BLE001
                analysis_errors.append(f"{battle_tag}: {exc}")

        record.analysis_ids = analysis_ids
        summaries = [str(a.get("summary") or "") for a in advice_list if a.get("summary")]
        record.advice_summary = "；".join(filter(None, summaries))
        feedback: list[str] = []
        for advice in advice_list:
            for item in advice.get("team_builder_feedback") or []:
                text = str(item)
                if text and text not in feedback:
                    feedback.append(text)
        record.team_builder_feedback = feedback

        analysis_lines = [
            f"# 第 {index + 1} 轮深度分析",
            "",
            f"- 对局数：{record.total_battles}，胜率：{record.win_rate}",
            f"- 分析对局：{len(analysis_ids)} 局",
            f"- 建议摘要：{record.advice_summary or '无'}",
            "",
            "## 各局分析摘要",
            "",
        ]
        for battle_tag, analysis_id, advice in zip(
            [_result_field(item, "battle_tag") for item in targets], analysis_ids, advice_list, strict=False
        ):
            analysis_lines.append(f"- {battle_tag}（{analysis_id}）：{advice.get('summary') or '无摘要'}")
        if analysis_errors:
            analysis_lines.append("")
            analysis_lines.append("## 分析失败的对局")
            analysis_lines.extend(f"- {line}" for line in analysis_errors)
        analysis_lines.append("")
        (iter_dir / "analysis_report.md").write_text("\n".join(analysis_lines), encoding="utf-8")

        state.last_team = team
        state.last_report = {
            "requirement": state.requirement,
            "iteration": index,
            "lab_stats": stats,
            "analyses": advice_list,
            "opponent_profiles": profile_list,
            "team_builder_feedback": feedback,
        }
        (iter_dir / "iteration.json").write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        state.records.append(record)
        status.current_iteration = index + 1
        status.message = f"第 {index + 1} 轮完成：胜率 {record.win_rate}（{record.wins}/{record.total_battles}）"

    # ---- 收尾与工具 -----------------------------------------------------

    def _mark_error(self, state: _RunState, message: str) -> None:
        state.status.state = "error"
        state.status.message = message
        state.status.finished_at = _now()
        self._write_final_summary(state)

    def _reached_target(self, state: _RunState) -> bool:
        target = state.config.stop_win_rate
        if target is None or not state.records:
            return False
        last = state.records[-1]
        rate = last.win_rate
        return rate is not None and float(rate) >= float(target)

    def _finish(self, state: _RunState) -> None:
        status = state.status
        if not status.finished_at:
            status.finished_at = _now()
        valid_records = [record for record in state.records if record.valid and record.win_rate is not None]
        if valid_records:
            best = max(valid_records, key=lambda record: float(record.win_rate or 0.0))
            status.best_iteration = best.iteration
            status.best_win_rate = best.win_rate
        self._write_final_summary(state)

    def _write_final_summary(self, state: _RunState) -> None:
        status = state.status
        lines = [
            f"# 闭环流程总结：{state.run_id}",
            "",
            f"- 需求：{state.requirement}",
            f"- 状态：{status.state}（{status.current_iteration}/{status.max_iterations} 轮）",
            f"- 开始：{status.started_at}  结束：{status.finished_at or '进行中'}",
            "",
            "## 轮次对比",
            "",
            "| 轮次 | 胜率 | 胜/总 | 摘要 |",
            "| --- | --- | --- | --- |",
        ]
        for record in state.records:
            rate = record.win_rate if record.win_rate is not None else "-"
            lines.append(
                f"| {record.iteration + 1} | {rate} | {record.wins}/{record.total_battles} |"
                f" {record.error or record.advice_summary or '-'} |"
            )
        if status.best_iteration is not None:
            lines += [
                "",
                f"## 推荐队伍：第 {status.best_iteration + 1} 轮（胜率 {status.best_win_rate}）",
            ]
            for record in state.records:
                if record.iteration == status.best_iteration and record.team_builder_feedback:
                    lines.append("")
                    lines.append("回传建队模块的反馈：")
                    lines.extend(f"- {item}" for item in record.team_builder_feedback)
        lines.append("")
        (state.run_dir / "final_summary.md").write_text("\n".join(lines), encoding="utf-8")

    def _ensure_team_builder(self) -> Any:
        if self._team_builder is None:
            from ..team_builder.agent import TeamBuilderAgent

            self._team_builder = TeamBuilderAgent(llm=self.llm)
        return self._team_builder

    def _ensure_lab_runner(self) -> Any:
        if self._lab_runner is None:
            from ..lab.runner import LabRunner

            self._lab_runner = LabRunner()
        return self._lab_runner

    def _ensure_analysis_engine(self) -> Any:
        if self._analysis_engine is None:
            from ..analysis.engine import AnalysisEngine

            self._analysis_engine = AnalysisEngine(llm=self.llm)
        return self._analysis_engine
