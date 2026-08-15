"""coverage_analyzer 工具：分析队伍的打击面与属性覆盖。"""

from __future__ import annotations

from typing import Any

from pokemon_battle_assistant.showdown_db import get_move, get_pokemon
from pokemon_battle_assistant.type_chart import get_type_multiplier

from .zh import ALL_TYPES, type_zh


def _attacking_move_types(team: list[dict]) -> tuple[list[str], list[str]]:
    move_types: list[str] = []
    unknown_moves: list[str] = []
    seen: set[str] = set()
    for mon in team:
        if not isinstance(mon, dict):
            continue
        for move in mon.get("moves", []) or []:
            entry = get_move(str(move))
            if entry is None:
                unknown_moves.append(str(move))
                continue
            if entry.get("category") == "Status":
                continue
            move_type = str(entry.get("type", ""))
            if move_type and move_type not in seen:
                seen.add(move_type)
                move_types.append(move_type)
    return move_types, unknown_moves


def analyze_coverage(team: list[dict]) -> dict[str, Any]:
    """统计全队攻击招式对 18 属性的最佳倍率与覆盖情况。"""
    move_types, unknown_moves = _attacking_move_types(team)
    best: dict[str, float] = {
        defend: max(
            (get_type_multiplier(attack, [defend]) for attack in move_types),
            default=0.0,
        )
        for defend in ALL_TYPES
    }
    super_effective = [t for t in ALL_TYPES if best[t] >= 2]
    neutral_only = [t for t in ALL_TYPES if best[t] == 1]
    resisted = [t for t in ALL_TYPES if best[t] < 1]

    stab_types: list[str] = []
    for mon in team:
        if not isinstance(mon, dict):
            continue
        entry = get_pokemon(str(mon.get("species", "")))
        if not entry:
            continue
        for t in entry.get("types", []):
            if t in move_types and t not in stab_types:
                stab_types.append(str(t))

    coverage_ratio = round(len(super_effective) / len(ALL_TYPES), 3)
    suggestions: list[str] = []
    if resisted:
        suggestions.append(
            "以下属性打不穿（全队招式被抵抗或免疫）："
            + "、".join(type_zh(t) for t in resisted)
            + "，建议补充对应打击面。"
        )
    if coverage_ratio < 0.3:
        suggestions.append("克制覆盖率偏低，优先补足热门属性的克制招式。")

    return {
        "ok": True,
        "team_size": len(team),
        "move_types": move_types,
        "stab_types": stab_types,
        "super_effective": super_effective,
        "neutral_only": neutral_only,
        "resisted_or_immune": resisted,
        "coverage_ratio": coverage_ratio,
        "unknown_moves": unknown_moves,
        "suggestions": suggestions,
        "summary": (
            f"攻击属性 {len(move_types)} 种，克制 {len(super_effective)}/18 属性，"
            f"打不穿 {len(resisted)} 属性。"
        ),
    }
