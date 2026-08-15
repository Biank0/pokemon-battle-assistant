"""AnalysisEngine：分析调度器（回放解析 → 逐回合评估 → 策略建议 → 对手画像 → 落盘）。"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .advisor import StrategyAdvisor
from .profiler import OpponentProfiler
from .replayer import BattleReplayer
from .reviewer import DecisionReviewer

DEFAULT_OUTPUT_ROOT = Path("analysis_outputs")
RECORD_SEARCH_ROOTS: tuple[Path, ...] = (
    Path("battle_outputs"),
    Path("lab_outputs"),
    Path("lab_outputs") / "battles",
)

RATING_BADGE = {"good": "好", "average": "一般", "mistake": "失误"}


def find_record_path(battle_tag: str, roots: Iterable[Path] = RECORD_SEARCH_ROOTS) -> Path:
    """在常见输出目录中查找 {battle_tag}/record.json。"""
    searched: list[str] = []
    for root in roots:
        base = Path(root)
        candidate = base / battle_tag / "record.json"
        if candidate.is_file():
            return candidate
        searched.append(str(base))
    raise FileNotFoundError(f"找不到对战记录 {battle_tag}/record.json（搜索目录：{', '.join(searched)}）")


@dataclass
class AnalysisReport:
    """一次深度分析的完整产物。"""

    analysis_id: str
    battle_tag: str
    created_at: str
    depth: str = "full"
    replay: dict[str, Any] = field(default_factory=dict)
    decision_review: list[dict[str, Any]] = field(default_factory=list)
    strategy_advice: dict[str, Any] = field(default_factory=dict)
    opponent_profile: dict[str, Any] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "analysis-report.v1",
            "analysis_id": self.analysis_id,
            "battle_tag": self.battle_tag,
            "created_at": self.created_at,
            "depth": self.depth,
            "replay": self.replay,
            "decision_review": self.decision_review,
            "strategy_advice": self.strategy_advice,
            "opponent_profile": self.opponent_profile,
            "files": self.files,
        }


class AnalysisEngine:
    """分析调度器：串起 Replayer/Reviewer/Advisor/Profiler 并导出产物。"""

    def __init__(self, llm: Any | None = None, output_root: Path | str = DEFAULT_OUTPUT_ROOT) -> None:
        self.llm = llm
        self.output_root = Path(output_root)
        self._results: dict[str, AnalysisReport] = {}

    async def analyze_battle(
        self,
        battle_tag: str,
        depth: str = "full",
        *,
        record: dict[str, Any] | None = None,
    ) -> str:
        """分析一局对战（record 缺省时按 battle_tag 查找 record.json），返回 analysis_id。"""
        if record is None:
            record = json.loads(find_record_path(battle_tag).read_text(encoding="utf-8"))
        timeline = BattleReplayer().replay(record)
        reviews = DecisionReviewer(llm=self.llm).review(record)
        profile = OpponentProfiler().profile(record)
        advice = StrategyAdvisor(llm=self.llm).advise(record, reviews, profile)

        analysis_id = f"{battle_tag}-{uuid4().hex[:8]}"
        report = AnalysisReport(
            analysis_id=analysis_id,
            battle_tag=battle_tag,
            created_at=datetime.now().isoformat(timespec="seconds"),
            depth=depth,
            replay=timeline.to_dict(),
            decision_review=[review.to_dict() for review in reviews],
            strategy_advice=advice,
            opponent_profile=profile,
        )
        report.files = self._write_outputs(report)
        self._results[analysis_id] = report
        return analysis_id

    def get_result(self, analysis_id: str) -> AnalysisReport:
        """获取分析结果（不存在时抛 KeyError）。"""
        return self._results[analysis_id]

    def list_analyses(self) -> list[dict[str, str]]:
        return [
            {
                "analysis_id": report.analysis_id,
                "battle_tag": report.battle_tag,
                "created_at": report.created_at,
                "depth": report.depth,
            }
            for report in self._results.values()
        ]

    def _write_outputs(self, report: AnalysisReport) -> dict[str, str]:
        out_dir = self.output_root / report.battle_tag
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "decision_review_json": out_dir / "decision_review.json",
            "strategy_advice_json": out_dir / "strategy_advice.json",
            "opponent_profile_json": out_dir / "opponent_profile.json",
            "analysis_report_md": out_dir / "analysis_report.md",
            "analysis_json": out_dir / "analysis.json",
        }
        paths["decision_review_json"].write_text(
            json.dumps(report.decision_review, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        paths["strategy_advice_json"].write_text(
            json.dumps(report.strategy_advice, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        paths["opponent_profile_json"].write_text(
            json.dumps(report.opponent_profile, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        paths["analysis_report_md"].write_text(build_markdown_analysis(report), encoding="utf-8")
        paths["analysis_json"].write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {key: str(path) for key, path in paths.items()}


def build_markdown_analysis(report: AnalysisReport) -> str:
    """生成中文深度分析报告（Markdown）。"""
    advice = report.strategy_advice
    profile = report.opponent_profile
    lines: list[str] = [
        f"# 对战深度分析：{report.battle_tag}",
        "",
        f"- 分析 ID：{report.analysis_id}",
        f"- 生成时间：{report.created_at}",
        f"- 回放摘要：{report.replay.get('summary') or '无'}",
        "",
        "## 逐回合决策评估",
        "",
        "| 回合 | 选择 | 评级 | 点评 | 更优选择 |",
        "| --- | --- | --- | --- | --- |",
    ]
    if report.decision_review:
        for review in report.decision_review:
            badge = RATING_BADGE.get(str(review.get("rating")), str(review.get("rating")))
            alternative = str(review.get("alternative") or "-")
            lines.append(
                f"| {review.get('turn')} | {review.get('order_message')} | {badge} |"
                f" {review.get('comment')} | {alternative} |"
            )
    else:
        lines.append("| - | - | - | 本局没有可评估的 Agent 决策 | - |")

    lines += [
        "",
        "## 策略优化建议",
        "",
        f"- 选出评价：{advice.get('team_selection_assessment')}",
        f"- 首发分析：{advice.get('lead_analysis')}",
        f"- 总结：{advice.get('summary')}",
        "",
        "### 关键回合替代方案",
        "",
        *[f"- {item}" for item in (advice.get("key_turn_alternatives") or [])],
        "",
        "### 针对对手的调整",
        "",
        *[f"- {item}" for item in (advice.get("opponent_adjustments") or [])],
        "",
        "### 回传建队模块的反馈",
        "",
        *[f"- {item}" for item in (advice.get("team_builder_feedback") or [])],
        "",
        "## 对手画像",
        "",
        f"- 风格：{profile.get('style')}（换人率 {profile.get('switch_rate')}，行动数 {profile.get('actions_total')}）",
        f"- 太晶化：{'已使用' if profile.get('tera_used') else '未使用'}",
        f"- 已揭示宝可梦：{'、'.join(profile.get('revealed_pokemon') or []) or '无'}",
        "",
        "### 下次对战建议",
        "",
        *[f"- {tip}" for tip in (profile.get("next_battle_tips") or [])],
        "",
        "## 时间线",
        "",
        *[
            f"- 回合 {event.get('turn')} [{event.get('kind')}] {event.get('player')}：{event.get('detail')}"
            for event in report.replay.get("events") or []
        ],
        "",
    ]
    return "\n".join(lines)
