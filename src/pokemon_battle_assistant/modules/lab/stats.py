"""批量对战统计：胜率、回合数、按对手拆分、选出频次。"""

from __future__ import annotations

from typing import Any


class StatsCollector:
    def __init__(self) -> None:
        self.total = 0
        self.wins = 0
        self.losses = 0
        self.errors = 0
        self.turns_sum = 0
        self.by_opponent: dict[str, dict[str, int]] = {}
        self.lead_slots: dict[str, int] = {}
        self.member_slots: dict[str, int] = {}

    def add(
        self,
        opponent: str,
        *,
        won: bool | None,
        turns: int | None = None,
        selected_slots: list[int] | None = None,
        error: str | None = None,
    ) -> None:
        self.total += 1
        bucket = self.by_opponent.setdefault(opponent, {"total": 0, "wins": 0, "errors": 0})
        bucket["total"] += 1
        if error:
            self.errors += 1
            bucket["errors"] += 1
            return
        if won is None:
            return
        if won:
            self.wins += 1
            bucket["wins"] += 1
        else:
            self.losses += 1
        if turns:
            self.turns_sum += turns
        if selected_slots:
            if selected_slots[0]:
                self.lead_slots[str(selected_slots[0])] = self.lead_slots.get(str(selected_slots[0]), 0) + 1
            for slot in selected_slots:
                self.member_slots[str(slot)] = self.member_slots.get(str(slot), 0) + 1

    def summary(self) -> dict[str, Any]:
        decided = self.wins + self.losses
        return {
            "total_battles": self.total,
            "wins": self.wins,
            "losses": self.losses,
            "errors": self.errors,
            "win_rate": round(self.wins / decided, 4) if decided else None,
            "avg_turns": round(self.turns_sum / decided, 2) if decided else None,
            "by_opponent": {
                opponent: {
                    "total": data["total"],
                    "wins": data["wins"],
                    "errors": data["errors"],
                    "win_rate": round(data["wins"] / data["total"], 4) if data["total"] else None,
                }
                for opponent, data in self.by_opponent.items()
            },
            "lead_slot_frequency": dict(sorted(self.lead_slots.items(), key=lambda kv: -kv[1])),
            "member_slot_frequency": dict(sorted(self.member_slots.items(), key=lambda kv: -kv[1])),
        }
