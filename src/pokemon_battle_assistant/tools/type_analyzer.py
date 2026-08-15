"""属性克制查询工具：复用 type_chart.py。

给 LLM 的两个能力：
- ``analyze_type``：某个攻击属性对一个防守属性组合的倍率
- ``defender_weakness_profile``：一个防守属性组合面对全部 18 属性的倍率表（找弱点和抗性）
"""

from __future__ import annotations

from ..type_chart import TYPE_CHART, describe_multiplier, get_type_multiplier, normalize_type


def analyze_type(move_type: str, defender_types: list[str]) -> dict:
    """查询一个攻击属性对防守方属性组合的克制倍率。"""
    attack = normalize_type(move_type)
    defenders = [normalize_type(t) for t in defender_types]
    if attack == "Unknown" or attack not in TYPE_CHART:
        return {"ok": False, "error": f"无法识别的攻击属性：{move_type!r}"}
    multiplier = get_type_multiplier(attack, defenders)
    return {
        "ok": True,
        "move_type": attack,
        "defender_types": defenders,
        "multiplier": multiplier,
        "effectiveness": describe_multiplier(multiplier),
        "note": "倍率>=2 效果拔群；<=0.5 被抵抗；0 无效。" if multiplier != 1 else "正常伤害倍率。",
    }


def defender_weakness_profile(defender_types: list[str]) -> dict:
    """查询一个防守属性组合面对全部攻击属性的倍率表。"""
    defenders = [normalize_type(t) for t in defender_types]
    matchups: dict[str, dict] = {}
    for attack in TYPE_CHART:
        multiplier = get_type_multiplier(attack, defenders)
        if multiplier == 1:
            continue
        matchups[attack] = {
            "multiplier": multiplier,
            "effectiveness": describe_multiplier(multiplier),
        }
    weaknesses = sorted(
        (a for a, m in matchups.items() if m["multiplier"] > 1),
        key=lambda a: -matchups[a]["multiplier"],
    )
    resistances = sorted(
        (a for a, m in matchups.items() if 0 < m["multiplier"] < 1),
        key=lambda a: matchups[a]["multiplier"],
    )
    immunities = [a for a, m in matchups.items() if m["multiplier"] == 0]
    return {
        "ok": True,
        "defender_types": defenders,
        "weaknesses": weaknesses,
        "resistances": resistances,
        "immunities": immunities,
        "matchups": matchups,
    }
