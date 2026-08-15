"""synergy_checker 工具：检查队伍成员之间的属性互补性。"""

from __future__ import annotations

from typing import Any

from pokemon_battle_assistant.showdown_db import get_pokemon
from pokemon_battle_assistant.type_chart import get_type_multiplier

from .zh import ALL_TYPES, TYPE_ZH, type_zh


def _member_types(mon: Any) -> list[str]:
    if not isinstance(mon, dict):
        return []
    entry = get_pokemon(str(mon.get("species", "")))
    if entry and isinstance(entry.get("types"), list):
        return [str(t) for t in entry["types"]]
    return []


def check_synergy(team: list[dict]) -> dict[str, Any]:
    """检查队伍防守面：共享弱点、集体抵抗与无人抵抗的属性。"""
    members: list[dict[str, Any]] = []
    unknown: list[str] = []
    for index, mon in enumerate(team):
        species = str(mon.get("species", "")) if isinstance(mon, dict) else ""
        types = _member_types(mon)
        if species and not types:
            unknown.append(species)
        members.append({"index": index, "species": species, "types": types})

    weak_map: dict[str, list[str]] = {}
    resist_map: dict[str, list[str]] = {}
    for attack in ALL_TYPES:
        for member in members:
            multiplier = get_type_multiplier(attack, member["types"])
            if multiplier >= 2:
                weak_map.setdefault(attack, []).append(member["species"])
            elif multiplier < 1:
                resist_map.setdefault(attack, []).append(member["species"])

    shared_weaknesses: list[dict[str, Any]] = [
        {"type": t, "type_zh": type_zh(t), "count": len(v), "vulnerable": v}
        for t, v in sorted(weak_map.items())
        if len(v) >= 3
    ]
    resistances: list[dict[str, Any]] = [
        {"type": t, "type_zh": type_zh(t), "count": len(v)}
        for t, v in sorted(resist_map.items())
        if len(v) >= 2
    ]
    no_resist = [t for t in ALL_TYPES if t not in resist_map]

    suggestions: list[str] = []
    for weak in shared_weaknesses:
        resist_types = [t for t in ALL_TYPES if get_type_multiplier(weak["type"], [t]) < 1]
        if resist_types:
            suggestions.append(
                f"队伍有 {weak['count']} 只被{weak['type_zh']}系克制，"
                f"建议补充 {'/'.join(type_zh(t) for t in resist_types)} 属性的成员。"
            )

    lines: list[str] = []
    if shared_weaknesses:
        lines.append("共享弱点：" + "、".join(w["type_zh"] for w in shared_weaknesses))
    else:
        lines.append("没有 3 只及以上成员共享的弱点，防守面健康。")
    if no_resist:
        lines.append("没有任何成员抵抗的属性：" + "、".join(TYPE_ZH[t] for t in no_resist))

    return {
        "ok": True,
        "team_size": len(members),
        "shared_weaknesses": shared_weaknesses,
        "resistances": resistances,
        "no_resist_types": no_resist,
        "unknown_species": unknown,
        "suggestions": suggestions,
        "summary": "；".join(lines),
    }
