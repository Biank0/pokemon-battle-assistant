"""Structured turn-level battle events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 关键事件类型：击倒 / 换人 / 太晶化 / 道具揭示 / 状态施加等
EVENT_KINDS = {
    "ko": "击倒",
    "switch": "换人",
    "terastallize": "太晶化",
    "item_reveal": "道具揭示",
    "status": "状态施加",
    "weather": "天气变化",
    "other": "其他",
}


@dataclass(frozen=True)
class BattleEvent:
    """One notable event in a battle."""

    turn: int
    kind: str  # EVENT_KINDS key
    side: str  # "my" / "opponent"
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn": self.turn,
            "kind": self.kind,
            "kind_zh": EVENT_KINDS.get(self.kind, self.kind),
            "side": self.side,
            "detail": self.detail,
            "data": dict(self.data),
        }


class EventLog:
    """Append-only structured event log for one battle."""

    def __init__(self) -> None:
        self._events: list[BattleEvent] = []

    def append(self, event: BattleEvent) -> None:
        self._events.append(event)

    def log(self, turn: int, kind: str, side: str, detail: str = "", **data: Any) -> None:
        self.append(BattleEvent(turn=turn, kind=kind, side=side, detail=detail, data=dict(data)))

    def all(self) -> list[BattleEvent]:
        return list(self._events)

    def tail(self, n: int = 10) -> list[BattleEvent]:
        return list(self._events[-n:])

    def by_kind(self, kind: str) -> list[BattleEvent]:
        return [e for e in self._events if e.kind == kind]

    def __len__(self) -> int:
        return len(self._events)

    def to_dicts(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._events]
