"""对战规划器：team preview 选出规划 + 回合策略文本生成。

纯启发式（不调 LLM），为 LLM 决策提供结构化的策略要点。
"""

from __future__ import annotations

from typing import Any

from ..perception.observation import BattleObservation
from ..showdown_db import get_move, get_pokemon
from ..type_chart import get_type_multiplier, normalize_type


def _as_dicts(items: Any) -> list[dict[str, Any]]:
    return [item.to_dict() if hasattr(item, "to_dict") else dict(item) for item in items or []]


def _types_of(mon: dict[str, Any]) -> list[str]:
    types = [str(t) for t in mon.get("types") or []]
    if types:
        return types
    data = get_pokemon(str(mon.get("species") or ""))
    return [str(t) for t in (data or {}).get("types", [])]


def plan_team_preview(observation: BattleObservation, memory: Any = None, team_size: int = 3) -> str:
    """基于属性克制给出选出策略文本。"""
    my_team = _as_dicts(observation.my_team)
    opp_team = _as_dicts(observation.opponent_team)
    if not my_team:
        return "未拿到我方队表，建议按默认顺序选出。"
    if not opp_team:
        return "未拿到对方队表，建议选择打击面覆盖最广的组合。"

    scores: list[tuple[float, int, str]] = []
    for idx, mon in enumerate(my_team, 1):
        best = 0.0
        for move_name in [str(m) for m in (mon.get("moves") or [])][:8]:
            move = get_move(move_name)
            if not move or not move.get("basePower"):
                continue
            attack_type = normalize_type(str(move.get("type", "")))
            if attack_type == "Unknown":
                continue
            total = sum(get_type_multiplier(attack_type, _types_of(opp)) for opp in opp_team)
            best = max(best, total / max(1, len(opp_team)))
        name = str(mon.get("zh_name") or mon.get("species") or f"#{idx}")
        scores.append((best, idx, name))

    scores.sort(key=lambda item: (-item[0], item[1]))
    names = [f"{name}(#{idx})" for _, idx, name in scores[:team_size]]
    weakest = scores[-1][2] if scores else "未知"
    return (
        f"按打击面估算，我方对对方全队压制力最强的 {team_size} 只是：{'、'.join(names)}；"
        f"压制力最弱的是 {weakest}，除非有特殊战术否则不建议选出。首发建议对位稳健的一只。"
    )


def plan_turn(observation: BattleObservation, memory: Any = None) -> str:
    """基于局面生成回合策略要点。"""
    obs = observation.to_dict()
    parts: list[str] = []
    phase = obs.get("phase") or "midgame"
    mine = obs.get("my_active")
    opp = obs.get("opponent_active")

    if phase == "opening":
        parts.append("开局阶段：优先建立对位优势，避免过早暴露全部配置。")
    elif phase == "endgame":
        parts.append("残局阶段：精确计算击倒线，速度线决定收尾顺序。")
    elif phase == "crisis":
        parts.append("危机局面：优先保住关键资源，必要时换入抗性位。")
    else:
        parts.append("中期博弈：围绕属性克制和速度线积累优势。")

    if isinstance(mine, dict) and isinstance(opp, dict):
        my_types = [str(t) for t in mine.get("types") or []]
        opp_types = [str(t) for t in opp.get("types") or []]

        worst: tuple[float, str] = (1.0, "")
        for move_name in [str(m) for m in opp.get("moves") or []]:
            move = get_move(move_name)
            if not move or not move.get("basePower"):
                continue
            mult = get_type_multiplier(str(move.get("type", "")), my_types)
            if mult > worst[0]:
                worst = (mult, str(move.get("name")))
        if worst[0] >= 2 and worst[1]:
            parts.append(f"警告：对方已揭示的 {worst[1]} 对我方在场宝可梦克制（x{worst[0]:g}），警惕先手重创。")

        best: tuple[float, str] = (0.0, "")
        move_list = [m for m in (obs.get("available_moves") or []) if isinstance(m, dict)]
        for move in move_list:
            power = move.get("base_power") or 0
            if not power:
                continue
            mult = get_type_multiplier(str(move.get("type") or ""), opp_types)
            score = power * mult
            if score > best[0]:
                best = (score, str(move.get("zh_name") or move.get("name")))
        if best[1]:
            parts.append(f"我方对当前对方宝可梦最有效的招式是 {best[1]}。")

    hp = (mine or {}).get("hp_percent") if isinstance(mine, dict) else None
    if hp is not None and hp <= 30:
        parts.append(f"我方在场仅剩 {hp}% HP，评估是否换人保留资源。")
    opp_hp = (opp or {}).get("hp_percent") if isinstance(opp, dict) else None
    if opp_hp is not None and opp_hp <= 25:
        parts.append(f"对方在场仅剩 {opp_hp}% HP，先手方大概率可以收割。")

    if memory is not None:
        try:
            summary = memory.get_opponent_model(observation.battle_tag).summary(observation)
            tendency = summary.get("switch_tendency")
            if tendency and tendency != "unknown":
                parts.append(f"对手模型：换人倾向={tendency}。")
            predict = summary.get("predicted_next_move")
            if predict:
                parts.append(f"对手模型预测：{predict}。")
        except Exception:
            pass
    return "".join(parts)
