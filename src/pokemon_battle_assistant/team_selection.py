"""Team preview selection policies for bring-6-pick-N formats."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Literal

SelectionMode = Literal["auto", "manual", "random", "fixed"]


@dataclass(frozen=True)
class TeamSelectionConfig:
    mode: SelectionMode = "auto"
    fixed_order: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, "fixed_order": list(self.fixed_order)}


@dataclass
class TeamSelectionRecord:
    player: str
    battle_tag: str
    format: str | None
    game_type: str
    mode: str
    required_count: int
    selected_slots: list[int]
    command: str
    team_preview: list[dict[str, Any]] = field(default_factory=list)
    opponent_preview: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "player": self.player,
            "battle_tag": self.battle_tag,
            "format": self.format,
            "game_type": self.game_type,
            "mode": self.mode,
            "required_count": self.required_count,
            "selected_slots": self.selected_slots,
            "command": self.command,
            "team_preview": self.team_preview,
            "opponent_preview": self.opponent_preview,
        }


def parse_selection(value: str | None) -> TeamSelectionConfig:
    """Parse CLI --select value."""
    if value is None or value == "" or value == "auto":
        return TeamSelectionConfig("auto")
    text = value.strip().lower()
    if text in {"manual", "random"}:
        return TeamSelectionConfig(text)  # type: ignore[arg-type]
    parts = [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]
    if not parts or not all(part.isdigit() for part in parts):
        raise ValueError("--select 只能是 auto/manual/random，或编号列表，例如 1,2,3,4。")
    return TeamSelectionConfig("fixed", tuple(int(part) for part in parts))


def validate_selected_slots(slots: list[int] | tuple[int, ...], *, required_count: int, team_size: int) -> list[int]:
    result = list(slots)
    if len(result) != required_count:
        raise ValueError(f"当前规则需要选择 {required_count} 只宝可梦，实际选择了 {len(result)} 只。")
    if len(set(result)) != len(result):
        raise ValueError("选出编号不能重复。")
    invalid = [slot for slot in result if slot < 1 or slot > team_size]
    if invalid:
        raise ValueError(f"选出编号超出队伍范围 1-{team_size}：{invalid}")
    return result


def choose_slots(config: TeamSelectionConfig, *, required_count: int, team_size: int) -> list[int]:
    if config.mode == "fixed":
        return validate_selected_slots(config.fixed_order, required_count=required_count, team_size=team_size)
    if config.mode == "random":
        slots = list(range(1, team_size + 1))
        random.shuffle(slots)
        return slots[:required_count]
    if config.mode == "auto":
        return list(range(1, min(required_count, team_size) + 1))
    raise ValueError("manual selection must be handled with battle context")
