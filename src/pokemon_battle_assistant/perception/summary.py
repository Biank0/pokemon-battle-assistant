"""Chinese one-line battle summary for LLM prompts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .classifier import phase_zh

if TYPE_CHECKING:
    from .observation import BattleObservation


def _hp_text(mon) -> str:
    if mon is None or mon.hp_percent is None:
        return "HP未知"
    return f"HP{mon.hp_percent:.0f}%"


def _label(mon) -> str:
    if mon is None:
        return "未知"
    name = mon.zh_name or mon.species
    status = f"（{mon.status}）" if mon.status else ""
    tera = "，已太晶" if mon.terastallized else ""
    return f"{name}{tera}{status}"


def build_summary(observation: BattleObservation, *, phase: str | None = None) -> str:
    """生成中文一句话局面摘要，供 LLM prompt 与终端展示使用。"""
    phase = phase or observation.phase
    parts: list[str] = []

    parts.append(f"第{observation.turn}回合（{phase_zh(phase)}）")
    if observation.game_type == "doubles":
        parts.append("双打")
    parts.append(
        f"我方{_label(observation.my_active)}{_hp_text(observation.my_active)}"
        f" 对阵 对方{_label(observation.opponent_active)}{_hp_text(observation.opponent_active)}"
    )

    my_alive = sum(1 for m in observation.my_team if not m.fainted)
    opp_alive = sum(1 for m in observation.opponent_team if not m.fainted)
    if observation.my_team or observation.opponent_team:
        parts.append(f"存活 {my_alive}v{opp_alive}")

    if observation.weather:
        parts.append("天气:" + "/".join(observation.weather))
    if observation.fields:
        parts.append("场地:" + "/".join(observation.fields))
    if observation.opponent_side_conditions:
        parts.append("对方场地:" + "/".join(observation.opponent_side_conditions))

    revealed = observation.opponent_revealed
    if revealed:
        revealed_species = [
            rec.get("species", key) for key, rec in revealed.get("pokemon", {}).items()  # type: ignore[union-attr]
        ]
        if revealed_species:
            parts.append("对方已揭示:" + "、".join(str(s) for s in revealed_species))

    return "，".join(parts) + "。"
