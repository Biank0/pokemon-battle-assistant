"""伤害估算工具：50 级 BSS 简化伤害公式。

估算口径（ deliberately conservative / transparent ）：
- 等级固定 50（BSS Regulation I）
- 能力值未显式给出时，按 31 IV / 0 EV / 无性格修正的种族值估算
- 不计入道具、特性、天气、场地的伤害修正
- 随机数区间 0.85 ~ 1.00
"""

from __future__ import annotations

import math
from typing import Any

from ..showdown_db import get_move, get_pokemon
from ..type_chart import describe_multiplier, get_type_multiplier, normalize_type

DEFAULT_LEVEL = 50
DEFAULT_MOVE_POWER = 80  # 招式威力未知时的保守估计


def effective_stat(base: float, level: int = DEFAULT_LEVEL) -> int:
    """31 IV / 0 EV / 无性格修正的非 HP 能力值。"""
    return math.floor((2 * base + 31) * level / 100) + 5


def effective_max_hp(base: float, level: int = DEFAULT_LEVEL) -> int:
    """31 IV / 0 EV 的最大 HP。"""
    return math.floor((2 * base + 31) * level / 100) + level + 10


def _species_of(mon: dict[str, Any]) -> str:
    return str(mon.get("species") or mon.get("name") or mon.get("id") or "").strip()


def _lookup_mon(mon: dict[str, Any]) -> dict[str, Any] | None:
    species = _species_of(mon)
    if not species:
        return None
    return get_pokemon(species)


def _stat_value(mon: dict[str, Any], keys: list[str], db_key: str) -> float | None:
    """显式能力值优先，其次按种族值估算。"""
    for key in keys:
        value = mon.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    data = _lookup_mon(mon)
    if data:
        base = (data.get("baseStats") or {}).get(db_key)
        if isinstance(base, (int, float)) and base > 0:
            return float(effective_stat(float(base)))
    return None


def resolve_move(move: dict[str, Any]) -> dict[str, Any]:
    """把 LLM 给的 move dict 补全为 {name, type, base_power, category}。"""
    result = {
        "name": str(move.get("name") or move.get("id") or "").strip(),
        "type": str(move.get("type") or "").strip(),
        "base_power": move.get("base_power", move.get("power", move.get("basePower"))),
        "category": str(move.get("category") or "").strip().lower(),
    }
    if result["name"] and (not result["type"] or result["base_power"] is None or not result["category"]):
        data = get_move(result["name"])
        if data:
            result["type"] = result["type"] or str(data.get("type", ""))
            if result["base_power"] is None:
                result["base_power"] = data.get("basePower")
            if not result["category"]:
                result["category"] = str(data.get("category", "")).lower()
    if result["base_power"] is None:
        result["base_power"] = DEFAULT_MOVE_POWER
        result["power_estimated"] = True
    else:
        result["power_estimated"] = False
    return result


def defender_types_of(defender: dict[str, Any]) -> list[str]:
    """防守方生效属性：已太晶化用太晶属性。"""
    if defender.get("terastallized") and defender.get("tera_type"):
        return [str(defender["tera_type"])]
    if defender.get("types"):
        return [str(t) for t in defender["types"]]
    data = _lookup_mon(defender)
    if data:
        return [str(t) for t in data.get("types", [])]
    return []


def max_hp_of(mon: dict[str, Any]) -> int | None:
    """显式 max_hp 优先，否则按种族值估算。"""
    value = mon.get("max_hp")
    if isinstance(value, (int, float)) and value > 0:
        return int(value)
    data = _lookup_mon(mon)
    if data:
        base = (data.get("baseStats") or {}).get("hp")
        if isinstance(base, (int, float)) and base > 0:
            return effective_max_hp(float(base))
    return None


def estimate_damage(attacker: dict[str, Any], defender: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
    """估算一个招式对目标的伤害区间与击倒概率。"""
    resolved = resolve_move(move)
    category = resolved["category"]
    if category == "status":
        return {
            "ok": False,
            "error": f"{resolved['name']} 是变化招式，不造成直接伤害。",
        }

    if category.startswith("phys"):
        atk = _stat_value(attacker, ["attack", "atk"], "atk")
        dfs = _stat_value(defender, ["defense", "def"], "def")
    else:
        atk = _stat_value(attacker, ["special_attack", "spa", "sp_attack"], "spa")
        dfs = _stat_value(defender, ["special_defense", "spd", "sp_defense"], "spd")
    if atk is None or dfs is None:
        return {
            "ok": False,
            "error": "无法确定攻击/防御能力值：请提供 species 或显式能力值字段。",
            "move": resolved,
        }

    power = float(resolved["base_power"] or 0)
    if power <= 0:
        return {"ok": False, "error": f"招式 {resolved['name']} 威力为 0，无法估算伤害。"}

    level = int(attacker.get("level") or DEFAULT_LEVEL)
    types = defender_types_of(defender)
    multiplier = get_type_multiplier(resolved["type"], types)

    attacker_types = attacker.get("types")
    if not attacker_types:
        data = _lookup_mon(attacker)
        attacker_types = data.get("types", []) if data else []
    stab = bool(attacker_types and resolved["type"] in {normalize_type(t) for t in attacker_types})

    base_damage = math.floor(math.floor(math.floor(2 * level / 5 + 2) * power * atk / dfs) / 50) + 2
    factor = multiplier * (1.5 if stab else 1.0)
    damage_min = max(0, math.floor(base_damage * factor * 0.85))
    damage_max = max(damage_min, math.floor(base_damage * factor))

    max_hp = max_hp_of(defender)
    result: dict[str, Any] = {
        "ok": True,
        "move": resolved,
        "attack_stat_est": round(atk, 1),
        "defense_stat_est": round(dfs, 1),
        "multiplier": multiplier,
        "effectiveness": describe_multiplier(multiplier),
        "stab": stab,
        "damage_range": [damage_min, damage_max],
    }
    if max_hp:
        percent_min = round(100.0 * damage_min / max_hp, 1)
        percent_max = round(100.0 * damage_max / max_hp, 1)
        current_pct = defender.get("hp_percent")
        notes = ["估算基于种族值（31IV/0EV/无性格修正），未计道具/特性/天气修正。"]
        if resolved.get("power_estimated"):
            notes.append(f"招式威力未知，按默认威力 {DEFAULT_MOVE_POWER} 估算。")
        ko_note = ""
        if current_pct is not None:
            current_hp = max_hp * float(current_pct) / 100.0
            if damage_min >= current_hp:
                ko_note = "大概率可以直接击倒当前血量。"
            elif damage_max >= current_hp:
                ko_note = "有概率直接击倒当前血量（依赖随机数）。"
            elif 2 * damage_min >= current_hp:
                ko_note = "约两回合可击倒当前血量。"
            else:
                ko_note = "短期无法击倒，需要强化或换克制位。"
        result.update(
            {
                "defender_max_hp_est": max_hp,
                "damage_percent_range": [percent_min, percent_max],
                "ko_note": ko_note,
                "notes": notes,
            }
        )
    return result
