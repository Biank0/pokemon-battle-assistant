"""Battle phase classification: opening / midgame / endgame / crisis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .observation import BattleObservation

Phase = Literal["opening", "midgame", "endgame", "crisis"]

_PHASE_ZH = {
    "opening": "开局",
    "midgame": "中盘",
    "endgame": "残局",
    "crisis": "危机",
}


def phase_zh(phase: str) -> str:
    return _PHASE_ZH.get(phase, phase)


def _alive_count(team: list) -> int:
    return sum(1 for mon in team if not getattr(mon, "fainted", False))


def classify_phase(observation: BattleObservation) -> Phase:
    """启发式局面分类。

    规则（BSS 单打 6 选 3 场景下按选出后在场队伍规模判断）：
    - crisis：我方存活 <= 1 或我方在场 HP <= 25%
    - endgame：双方存活合计 <= 2（或对手仅剩 1 只）
    - opening：回合 <= 3
    - midgame：其余情况
    """
    my_alive = _alive_count(observation.my_team)
    opp_alive = _alive_count(observation.opponent_team)

    my_active = observation.my_active
    my_hp = my_active.hp_percent if my_active else None

    if my_alive <= 1:
        return "crisis"
    if my_hp is not None and my_hp <= 25:
        return "crisis"
    if opp_alive <= 1:
        return "endgame"
    if my_alive + opp_alive <= 2:
        return "endgame"
    if observation.turn <= 3:
        return "opening"
    return "midgame"
