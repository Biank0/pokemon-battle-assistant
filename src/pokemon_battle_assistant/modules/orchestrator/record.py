"""闭环迭代的数据结构：LoopConfig / IterationRecord / OrchestratorStatus。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_OUTPUT_ROOT = Path("orchestrator_outputs")


@dataclass
class LoopConfig:
    """闭环流程配置。"""

    opponents: list[str] = field(default_factory=list)
    battles_per_opponent: int = 3
    battle_format: str = "gen9bssregi"
    concurrency: int = 2
    analysis_battles_limit: int = 3
    backend: str | None = None
    model: str | None = None
    stop_win_rate: float | None = None
    output_root: Path = DEFAULT_OUTPUT_ROOT

    def to_dict(self) -> dict[str, Any]:
        return {
            "opponents": list(self.opponents),
            "battles_per_opponent": self.battles_per_opponent,
            "battle_format": self.battle_format,
            "concurrency": self.concurrency,
            "analysis_battles_limit": self.analysis_battles_limit,
            "backend": self.backend,
            "model": self.model,
            "stop_win_rate": self.stop_win_rate,
            "output_root": str(self.output_root),
        }


@dataclass
class IterationRecord:
    """一轮迭代的队伍 + Lab 结果 + 分析记录。"""

    iteration: int
    team: dict[str, Any] = field(default_factory=dict)
    team_hash: str = ""
    valid: bool = False
    win_rate: float | None = None
    wins: int = 0
    total_battles: int = 0
    analysis_ids: list[str] = field(default_factory=list)
    advice_summary: str = ""
    team_builder_feedback: list[str] = field(default_factory=list)
    output_dir: str = ""
    created_at: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "team": self.team,
            "team_hash": self.team_hash,
            "valid": self.valid,
            "win_rate": self.win_rate,
            "wins": self.wins,
            "total_battles": self.total_battles,
            "analysis_ids": list(self.analysis_ids),
            "advice_summary": self.advice_summary,
            "team_builder_feedback": list(self.team_builder_feedback),
            "output_dir": self.output_dir,
            "created_at": self.created_at,
            "error": self.error,
        }


@dataclass
class OrchestratorStatus:
    """闭环流程运行状态。"""

    run_id: str
    requirement: str
    state: str = "running"  # running / waiting_confirm / completed / error
    current_iteration: int = 0
    max_iterations: int = 3
    auto_iterate: bool = True
    message: str = ""
    started_at: str = ""
    finished_at: str = ""
    best_iteration: int | None = None
    best_win_rate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "requirement": self.requirement,
            "state": self.state,
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_iterations,
            "auto_iterate": self.auto_iterate,
            "message": self.message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "best_iteration": self.best_iteration,
            "best_win_rate": self.best_win_rate,
        }
