"""Turn action evaluations into readable Chinese coaching output."""

from __future__ import annotations

from .models import ActionEvaluation, BattleState


def format_analysis(state: BattleState, evaluations: list[ActionEvaluation], top_n: int = 3) -> str:
    """Format the battle analysis result for CLI users."""

    if not evaluations:
        return "没有可评估的行动。请在输入 JSON 中提供 available_actions。"

    best = evaluations[0]
    lines: list[str] = []
    lines.append("# 宝可梦对战局面分析")
    lines.append("")
    lines.append(f"规则环境：{state.rule_set}")
    lines.append(
        f"我方在场：{state.my_active.name} ({'/'.join(state.my_active.types)}, HP {state.my_active.hp_percent}%)"
    )
    lines.append(
        f"对方在场：{state.opponent_active.name} ({'/'.join(state.opponent_active.types)}, HP {state.opponent_active.hp_percent}%)"
    )
    if state.notes:
        lines.append(f"备注：{state.notes}")
    lines.append("")

    lines.append(f"推荐操作：{_action_label(best)}")
    lines.append(f"评分：{best.score}")
    lines.append(f"置信度：{_confidence_label(best.confidence)}")
    lines.append("")
    lines.append("推荐理由：")
    for reason in best.reasons:
        lines.append(f"- {reason}")
    lines.append("")
    lines.append("主要风险：")
    for risk in best.risks or ["当前没有明显额外风险，但仍需要根据对方配置和玩家习惯调整判断。"]:
        lines.append(f"- {risk}")
    lines.append("")

    lines.append("候选操作排序：")
    for index, evaluation in enumerate(evaluations[:top_n], start=1):
        lines.append(f"{index}. {_action_label(evaluation)}：{evaluation.score} 分，{_confidence_label(evaluation.confidence)}")
    lines.append("")

    stable = next((item for item in evaluations if "stable" in item.tags), None)
    aggressive = next((item for item in evaluations if "aggressive" in item.tags), None)
    if stable or aggressive:
        lines.append("风格建议：")
        if stable:
            lines.append(f"- 稳定解：{_action_label(stable)}")
        if aggressive:
            lines.append(f"- 激进解：{_action_label(aggressive)}")

    return "\n".join(lines)


def _action_label(evaluation: ActionEvaluation) -> str:
    action = evaluation.action
    if action.kind == "switch":
        return f"换入 {action.target or action.name}"
    if action.move_type:
        return f"{action.name}（{action.move_type}）"
    return action.name


def _confidence_label(confidence: str) -> str:
    return {
        "low": "低",
        "medium": "中",
        "high": "高",
    }.get(confidence, confidence)
