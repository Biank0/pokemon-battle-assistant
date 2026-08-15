"""Long-term memory persisted across battles (data/memory/long_term.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MAX_BATTLE_HISTORY = 50


@dataclass
class OpponentStats:
    """一个对手（用户名）的跨局统计。"""

    battles: int = 0
    wins: int = 0  # 我方战胜该对手的次数
    losses: int = 0
    teams_seen: list[str] = field(default_factory=list)
    style_tags: list[str] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        return self.wins / self.battles if self.battles else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "battles": self.battles,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate, 3),
            "teams_seen": list(self.teams_seen),
            "style_tags": list(self.style_tags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpponentStats:
        return cls(
            battles=int(data.get("battles", 0)),
            wins=int(data.get("wins", 0)),
            losses=int(data.get("losses", 0)),
            teams_seen=list(data.get("teams_seen", [])),
            style_tags=list(data.get("style_tags", [])),
        )


@dataclass
class TeamWinRate:
    """一个队伍配置的跨局战绩（key 为队伍名或配置 hash）。"""

    battles: int = 0
    wins: int = 0

    @property
    def win_rate(self) -> float:
        return self.wins / self.battles if self.battles else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"battles": self.battles, "wins": self.wins, "win_rate": round(self.win_rate, 3)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TeamWinRate:
        return cls(battles=int(data.get("battles", 0)), wins=int(data.get("wins", 0)))


@dataclass
class LongTermMemory:
    """跨局记忆，持久化到 data/memory/long_term.json。"""

    opponent_stats: dict[str, OpponentStats] = field(default_factory=dict)
    team_winrate: dict[str, TeamWinRate] = field(default_factory=dict)
    common_leads: dict[str, dict[str, int]] = field(default_factory=dict)  # team_key -> {species: count}
    battle_history: list[dict[str, Any]] = field(default_factory=list)

    # ---- 对手统计 ----
    def record_battle_result(
        self,
        *,
        opponent: str,
        won: bool,
        my_team_key: str = "default",
        my_lead: str | None = None,
        summary: dict[str, Any] | None = None,
    ) -> None:
        stats = self.opponent_stats.setdefault(opponent, OpponentStats())
        stats.battles += 1
        if won:
            stats.wins += 1
        else:
            stats.losses += 1
        if my_team_key not in stats.teams_seen:
            stats.teams_seen.append(my_team_key)

        team = self.team_winrate.setdefault(my_team_key, TeamWinRate())
        team.battles += 1
        if won:
            team.wins += 1

        if my_lead:
            leads = self.common_leads.setdefault(my_team_key, {})
            leads[my_lead] = leads.get(my_lead, 0) + 1

        entry = dict(summary or {})
        entry.setdefault("opponent", opponent)
        entry.setdefault("won", won)
        entry.setdefault("my_team_key", my_team_key)
        self.battle_history.append(entry)
        if len(self.battle_history) > MAX_BATTLE_HISTORY:
            self.battle_history = self.battle_history[-MAX_BATTLE_HISTORY:]

    def most_common_lead(self, team_key: str) -> str | None:
        leads = self.common_leads.get(team_key)
        if not leads:
            return None
        return max(leads.items(), key=lambda kv: kv[1])[0]

    # ---- 持久化 ----
    def to_dict(self) -> dict[str, Any]:
        return {
            "opponent_stats": {k: v.to_dict() for k, v in self.opponent_stats.items()},
            "team_winrate": {k: v.to_dict() for k, v in self.team_winrate.items()},
            "common_leads": {k: dict(v) for k, v in self.common_leads.items()},
            "battle_history": list(self.battle_history),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LongTermMemory:
        return cls(
            opponent_stats={k: OpponentStats.from_dict(v) for k, v in data.get("opponent_stats", {}).items()},
            team_winrate={k: TeamWinRate.from_dict(v) for k, v in data.get("team_winrate", {}).items()},
            common_leads={k: dict(v) for k, v in data.get("common_leads", {}).items()},
            battle_history=list(data.get("battle_history", [])),
        )

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> LongTermMemory:
        path = Path(path)
        if not path.exists():
            return cls()
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            return cls()
