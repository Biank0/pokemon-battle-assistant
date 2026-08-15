"""威胁评估工具：评估对方在场宝可梦对我方的威胁与反制空间。

输入是 ``BattleObservation``（由 ToolContext 提供，LLM 无需传参）。
评估口径：
- 对方已揭示招式对我方在场宝可梦的伤害估算（未揭示的招式不计入）
- 我方可用招式对对方的最佳反制估算
- threat_level: high / medium / low
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..showdown_db import get_move
from ..type_chart import get_type_multiplier, normalize_type
from .damage_calculator import DEFAULT_MOVE_POWER, estimate_damage

if TYPE_CHECKING:
    pass


def _as_dict(mon: Any) -> dict[str, Any] | None:
    if mon is None:
        return None
    if hasattr(mon, "to_dict"):
        return mon.to_dict()
    if isinstance(mon, dict):
        return mon
    return None


def _move_dict(move: Any) -> dict[str, Any]:
    if hasattr(move, "to_dict"):
        d = move.to_dict()
        return {
            "name": d.get("name"),
            "type": d.get("type"),
            "base_power": d.get("base_power"),
            "category": d.get("category"),
        }
    if isinstance(move, dict):
        return move
    return {"name": str(move)}


def _threat_of(move: dict[str, Any], opponent: dict[str, Any], mine: dict[str, Any]) -> dict[str, Any]:
    """对方一个招式对我方的威胁摘要。"""
    result = estimate_damage(opponent, mine, move)
    if result.get("ok"):
        return {
            "move": result["move"]["name"],
            "damage_percent_range": result.get("damage_percent_range"),
            "multiplier": result.get("multiplier"),
            "ko_note": result.get("ko_note", ""),
        }
    # 无法完整估算时退化为属性倍率评估
    move_type = normalize_type(str(move.get("type") or ""))
    if not move_type or move_type == "Unknown":
        data = get_move(str(move.get("name") or ""))
        move_type = normalize_type(str((data or {}).get("type", "")))
    multiplier = (
        get_type_multiplier(move_type, [str(t) for t in (mine.get("types") or [])])
        if move_type and move_type != "Unknown"
        else 1.0
    )
    return {
        "move": move.get("name"),
        "damage_percent_range": None,
        "multiplier": multiplier,
        "ko_note": "威力未知，仅按属性倍率评估。",
    }


def assess_threat(observation: Any) -> dict[str, Any]:
    """评估当前局面的威胁与反制。observation 为 BattleObservation 或其 dict。"""
    if hasattr(observation, "to_dict"):
        obs = observation.to_dict()
    elif isinstance(observation, dict):
        obs = observation
    else:
        return {"ok": False, "error": "threat_assessment 需要当前局面（observation）作为上下文。"}

    mine = _as_dict(obs.get("my_active"))
    opponent = _as_dict(obs.get("opponent_active"))
    if not mine or not opponent:
        return {"ok": False, "error": "当前没有双方在场宝可梦信息，无法评估威胁。"}

    revealed = obs.get("opponent_revealed") or {}
    opp_species = opponent.get("species")
    revealed_moves = list((revealed.get(str(opp_species)) or {}).get("moves") or [])
    opp_moves: list[dict[str, Any]] = [
        m if isinstance(m, dict) else {"name": str(m)} for m in opponent.get("moves") or []
    ]
    known_move_names = {str(m.get("name")) for m in opp_moves}
    for name in revealed_moves:
        if name not in known_move_names:
            opp_moves.append({"name": name})

    threats = sorted(
        (_threat_of(move, opponent, mine) for move in opp_moves),
        key=lambda t: -(t.get("damage_percent_range") or [0, 0])[1] if t.get("damage_percent_range") else -(t.get("multiplier") or 0),
    )
    top = threats[0] if threats else None
    top_pct = (top.get("damage_percent_range") or [0, 0])[1] if top else 0.0
    if top_pct >= 70 or (top and (top.get("multiplier") or 0) >= 2 and top_pct >= 50):
        level = "high"
    elif top_pct >= 35 or (top and (top.get("multiplier") or 0) >= 2):
        level = "medium"
    else:
        level = "low"

    my_best = None
    for move in obs.get("available_moves") or []:
        result = estimate_damage(mine, opponent, _move_dict(move))
        if result.get("ok"):
            pct = (result.get("damage_percent_range") or [0, 0])[1]
            if my_best is None or pct > my_best[1]:
                my_best = (result["move"]["name"], pct, result.get("ko_note", ""))

    opp_hp = opponent.get("hp_percent")
    advice = []
    if level == "high":
        advice.append("对方当前宝可梦对我方威胁很大，优先考虑换入抗性位或先手压制。")
    if opp_hp is not None and opp_hp <= 35 and my_best:
        advice.append(f"对方血量仅 {opp_hp}%，{my_best[0]} 有机会直接收割。")
    if my_best:
        advice.append(f"我方最佳反制是 {my_best[0]}（估算伤害约 {my_best[1]}%）。")
    if not opp_moves:
        advice.append("对方尚未揭示招式，威胁评估基于种族值，信息不足时先稳住节奏。")

    return {
        "ok": True,
        "turn": obs.get("turn"),
        "my_active": mine.get("species"),
        "opponent_active": opponent.get("species"),
        "opponent_revealed_moves": [str(m.get("name")) for m in opp_moves],
        "threats": threats,
        "threat_level": level,
        "top_threat": top,
        "my_best_counter": (
            {"move": my_best[0], "damage_percent": my_best[1], "ko_note": my_best[2]} if my_best else None
        ),
        "advice": advice,
        "note": f"威胁伤害按 50 级种族值估算，未知威力按 {DEFAULT_MOVE_POWER} 计。",
    }
