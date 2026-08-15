"""批量对战配置。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class BattleTask:
    """一场待运行的对战。"""

    task_id: str
    opponent: str
    battle_index: int  # 对同一对手的第几局（1 起）


@dataclass(frozen=True)
class BatchConfig:
    """Lab 批量模拟配置。"""

    team: str
    opponents: list[str] = field(default_factory=list)
    battles_per_opponent: int = 10
    battle_format: str = "gen9bssregi"
    concurrency: int = 2
    backend: str | None = None
    model: str | None = None
    output_root: Path = Path("lab_outputs")
    skip_validation: bool = False

    def total_battles(self) -> int:
        return max(1, self.battles_per_opponent) * max(1, len(self.opponents))

    def battle_tasks(self) -> list[BattleTask]:
        tasks: list[BattleTask] = []
        for opponent in self.opponents:
            for idx in range(1, max(1, self.battles_per_opponent) + 1):
                tasks.append(
                    BattleTask(
                        task_id=f"{opponent}-{idx}",
                        opponent=opponent,
                        battle_index=idx,
                    )
                )
        return tasks

    def to_dict(self) -> dict:
        return {
            "team": self.team,
            "opponents": list(self.opponents),
            "battles_per_opponent": self.battles_per_opponent,
            "battle_format": self.battle_format,
            "concurrency": self.concurrency,
            "backend": self.backend,
            "model": self.model,
            "total_battles": self.total_battles(),
        }
