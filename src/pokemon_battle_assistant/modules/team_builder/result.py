"""TeamBuildResult 数据结构与工具函数。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


def team_hash(team: dict[str, Any]) -> str:
    canonical = json.dumps(team, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@dataclass
class TeamBuildResult:
    """建队结果：队伍 + 校验 + 理由 + 工具调用记录 + 迭代信息。"""

    team: dict[str, Any]
    valid: bool = False
    validation_errors: list[str] = field(default_factory=list)
    reasoning: str = ""
    tool_calls_log: list[dict[str, Any]] = field(default_factory=list)
    iteration: int = 0
    parent_team_hash: str | None = None

    @property
    def team_id(self) -> str:
        return team_hash(self.team)

    def to_dict(self) -> dict[str, Any]:
        return {
            "team": self.team,
            "valid": self.valid,
            "validation_errors": self.validation_errors,
            "reasoning": self.reasoning,
            "tool_calls_log": self.tool_calls_log,
            "iteration": self.iteration,
            "parent_team_hash": self.parent_team_hash,
            "team_hash": self.team_id,
        }
