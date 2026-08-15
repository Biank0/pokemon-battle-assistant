"""Agent 决策日志：记录每回合推理过程，导出到 record.json。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecisionRecord:
    turn: int
    decision_type: str  # "team_preview" | "turn"
    order_message: str
    reasoning: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    fallback: bool = False
    model: str = ""
    backend: str = ""
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn": self.turn,
            "decision_type": self.decision_type,
            "order_message": self.order_message,
            "reasoning": self.reasoning,
            "tool_calls": self.tool_calls,
            "fallback": self.fallback,
            "model": self.model,
            "backend": self.backend,
            "elapsed_ms": self.elapsed_ms,
        }


class DecisionLogger:
    """累积一次对局的全部决策记录。"""

    def __init__(self) -> None:
        self._records: list[DecisionRecord] = []

    def log(
        self,
        *,
        turn: int,
        decision_type: str,
        order_message: str,
        reasoning: str,
        tool_calls: list[dict[str, Any]] | None = None,
        fallback: bool = False,
        model: str = "",
        backend: str = "",
        started_at: float | None = None,
    ) -> DecisionRecord:
        elapsed = int((time.time() - started_at) * 1000) if started_at else 0
        record = DecisionRecord(
            turn=turn,
            decision_type=decision_type,
            order_message=order_message,
            reasoning=reasoning,
            tool_calls=list(tool_calls or []),
            fallback=fallback,
            model=model,
            backend=backend,
            elapsed_ms=elapsed,
        )
        self._records.append(record)
        return record

    def to_list(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._records]

    def __len__(self) -> int:
        return len(self._records)
