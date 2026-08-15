"""速度线比较工具：判断先手。

速度来源优先级：显式 speed 字段 > 种族值估算（31IV/0EV/无性格）。
麻痹（PAR）速度减半。
"""

from __future__ import annotations

from typing import Any

from ..showdown_db import get_pokemon
from .damage_calculator import effective_stat


def speed_of(mon: dict[str, Any]) -> float | None:
    """取一只宝可梦的生效速度。"""
    value = mon.get("speed") or mon.get("spe")
    if isinstance(value, (int, float)) and value > 0:
        speed = float(value)
    else:
        species = str(mon.get("species") or mon.get("name") or "").strip()
        data = get_pokemon(species) if species else None
        if not data:
            return None
        base = (data.get("baseStats") or {}).get("spe")
        if not isinstance(base, (int, float)) or base <= 0:
            return None
        speed = float(effective_stat(float(base)))
    if str(mon.get("status") or "").upper() == "PAR":
        speed = max(1.0, speed / 2)
    return round(speed, 1)


def compare_speed(my_pokemon: dict[str, Any], opponent_pokemon: dict[str, Any]) -> dict[str, Any]:
    """比较我方与对方在场宝可梦的速度线，判断谁先手。"""
    my_speed = speed_of(my_pokemon)
    opp_speed = speed_of(opponent_pokemon)
    if my_speed is None or opp_speed is None:
        return {
            "ok": False,
            "error": "无法确定速度：请提供 species 或显式 speed 字段。",
            "my_speed": my_speed,
            "opponent_speed": opp_speed,
        }

    faster = my_speed > opp_speed
    tie = my_speed == opp_speed
    margin = round(abs(my_speed - opp_speed), 1)
    caveats = []
    if not my_pokemon.get("speed") and not my_pokemon.get("spe"):
        caveats.append("我方速度按种族值估算，未计个体/努力/性格/道具修正。")
    if not opponent_pokemon.get("speed") and not opponent_pokemon.get("spe"):
        caveats.append("对方速度按种族值估算；对方可能携带讲究围巾（约1.5倍）或吃过强化。")
    if tie:
        caveats.append("同速时出手顺序随机（各50%）。")

    if tie:
        first = "同速，随机先手"
    elif faster:
        first = "我方先手"
    else:
        first = "对方先手"

    return {
        "ok": True,
        "my_speed": my_speed,
        "opponent_speed": opp_speed,
        "faster": faster,
        "margin": margin,
        "first_move": first,
        "caveats": caveats,
    }
