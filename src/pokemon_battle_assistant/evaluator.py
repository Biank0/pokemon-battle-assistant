"""Heuristic action evaluator for the MVP.

This module deliberately uses transparent scoring rules.  The score is not an
official damage calculation; it is a first-pass coaching heuristic that can be
improved over time.
"""

from __future__ import annotations

from .models import Action, ActionEvaluation, BattleState
from .type_chart import describe_multiplier, get_type_multiplier, normalize_type

PIVOT_TAGS = {"pivot", "u-turn", "volt-switch", "flip-turn"}
PRIORITY_TAGS = {"priority", "sucker-punch", "quick-attack"}
SETUP_TAGS = {"setup", "boost"}


def evaluate_battle(state: BattleState) -> list[ActionEvaluation]:
    """Evaluate and sort all available actions from best to worst."""

    evaluations = [evaluate_action(action, state) for action in state.available_actions]
    return sorted(evaluations, key=lambda item: item.score, reverse=True)


def evaluate_action(action: Action, state: BattleState) -> ActionEvaluation:
    """Score one candidate action."""

    if action.kind == "switch":
        return _evaluate_switch(action, state)
    return _evaluate_move(action, state)


def _evaluate_move(action: Action, state: BattleState) -> ActionEvaluation:
    score = 0
    reasons: list[str] = []
    risks: list[str] = []
    tags: list[str] = []

    move_type = normalize_type(action.move_type)
    multiplier = get_type_multiplier(move_type, state.opponent_active.types)
    effectiveness = describe_multiplier(multiplier)

    if multiplier == 0:
        score -= 80
        reasons.append(f"{move_type} 属性招式对目标{effectiveness}，不建议直接使用。")
        risks.append("该招式可能完全无法造成伤害。")
    elif multiplier >= 4:
        score += 55
        reasons.append(f"{move_type} 属性招式对目标是{effectiveness}，即时收益极高。")
    elif multiplier >= 2:
        score += 35
        reasons.append(f"{move_type} 属性招式对目标{effectiveness}，可以主动压低对方血量。")
    elif multiplier == 1:
        score += 12
        reasons.append(f"{move_type} 属性招式对目标为{effectiveness}，属于稳定但不爆炸的选择。")
    elif multiplier <= 0.25:
        score -= 35
        reasons.append(f"{move_type} 属性招式被目标{effectiveness}，伤害收益很低。")
        risks.append("如果对方留场，该操作可能亏节奏。")
    else:
        score -= 18
        reasons.append(f"{move_type} 属性招式对目标{effectiveness}，伤害收益偏低。")

    if move_type in {normalize_type(t) for t in state.my_active.types}:
        score += 12
        reasons.append("该招式拥有本系加成，基础收益更可靠。")

    if action.power is not None:
        if action.power >= 100:
            score += 10
            reasons.append("招式威力较高，适合直接制造血量压力。")
        elif action.power <= 50 and action.power > 0:
            score -= 4
            risks.append("招式威力偏低，可能无法形成足够压制。")

    lowered_tags = {tag.lower() for tag in action.tags}
    if lowered_tags & PIVOT_TAGS:
        score += 14
        tags.append("stable")
        reasons.append("该操作可以保持轮转主动权，适合应对对方换人。")
    if lowered_tags & PRIORITY_TAGS:
        score += 8
        tags.append("aggressive")
        reasons.append("先制类操作可以处理残血目标，但通常依赖对方行动。")
        risks.append("如果对方不满足先制招式的触发条件，收益可能下降。")
    if lowered_tags & SETUP_TAGS:
        score += 6
        tags.append("aggressive")
        reasons.append("强化类操作有机会扩大优势。")
        risks.append("如果对方本回合强攻或逼退，强化可能付出血量代价。")

    if state.opponent_active.hp_percent <= 35 and multiplier >= 1:
        score += 18
        tags.append("ko-pressure")
        reasons.append("对方血量较低，该操作有机会推进击杀线。")
    elif state.opponent_active.hp_percent <= 60 and multiplier >= 2:
        score += 12
        tags.append("ko-pressure")
        reasons.append("对方血量已经被压低，克制招式有明显收割潜力。")

    if multiplier >= 2:
        risks.append("如果对方换入抗性位或免疫位，该回合收益会下降。")
    elif multiplier < 1:
        risks.append("该招式面对当前目标不够理想，除非你在读对方换人。")

    confidence = "high" if move_type != "Unknown" else "low"
    if action.power is None:
        confidence = "medium" if confidence == "high" else confidence
        risks.append("当前没有完整伤害数据，评分主要基于属性克制和启发式规则。")

    return ActionEvaluation(
        action=action,
        score=score,
        confidence=confidence,
        reasons=_dedupe(reasons),
        risks=_dedupe(risks),
        tags=_dedupe(tags),
    )


def _evaluate_switch(action: Action, state: BattleState) -> ActionEvaluation:
    score = 8
    reasons = ["换人可以保留当前宝可梦资源，并重新调整对位。"]
    risks = ["换人本身通常会让出本回合主动权，需要确认后排能安全吃下对方行动。"]
    tags = ["stable"]

    if state.my_active.hp_percent <= 35:
        score += 16
        reasons.append("当前宝可梦血量较低，换人有助于保存残局资源。")

    if action.target:
        reasons.append(f"目标换入位：{action.target}。")

    return ActionEvaluation(
        action=action,
        score=score,
        confidence="medium",
        reasons=reasons,
        risks=risks,
        tags=tags,
    )


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
