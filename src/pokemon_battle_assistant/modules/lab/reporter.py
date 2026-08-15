"""LabReporter：summary.json + summary.md 输出。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _win_rate_text(rate: Any) -> str:
    return f"{rate * 100:.1f}%" if isinstance(rate, (int, float)) else "N/A"


def build_markdown(report: dict[str, Any]) -> str:
    stats = report.get("stats", {})
    config = report.get("config", {})
    lines = [
        "# Lab 批量对战报告",
        "",
        f"- 运行时间：{report.get('started_at')} ~ {report.get('finished_at')}",
        f"- 队伍：`{config.get('team')}`  格式：`{config.get('battle_format')}`",
        f"- 总局数：{stats.get('total_battles')}（每对手 {config.get('battles_per_opponent')} 局）",
        f"- 胜率：**{_win_rate_text(stats.get('win_rate'))}**"
        f"（{stats.get('wins')} 胜 / {stats.get('losses')} 负 / {stats.get('errors')} 错误）",
        f"- 平均回合数：{stats.get('avg_turns')}",
        "",
        "## 按对手拆分",
        "",
        "| 对手 | 局数 | 胜 | 负 | 错误 | 胜率 |",
        "|---|---|---|---|---|---|",
    ]
    for opponent, data in (stats.get("by_opponent") or {}).items():
        losses = data["total"] - data["wins"] - data["errors"]
        lines.append(
            f"| {opponent} | {data['total']} | {data['wins']} | {losses} | {data['errors']} | {_win_rate_text(data.get('win_rate'))} |"
        )
    lines += ["", "## 选出统计", "", f"- 首发频次：{stats.get('lead_slot_frequency')}", f"- 入选频次：{stats.get('member_slot_frequency')}", ""]
    return "\n".join(lines)


class LabReporter:
    def write(self, report: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
        output = Path(output_root)
        output.mkdir(parents=True, exist_ok=True)
        json_path = output / "summary.json"
        md_path = output / "summary.md"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(build_markdown(report), encoding="utf-8")
        return json_path, md_path
