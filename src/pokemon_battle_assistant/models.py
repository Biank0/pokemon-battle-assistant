"""Core data models for the MVP battle assistant.

The first version intentionally keeps the model small and explicit.  It is not
trying to fully reproduce the official battle engine yet; it only stores the
minimum information needed to rank candidate actions and explain the ranking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ActionKind = Literal["move", "switch"]
Confidence = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Move:
    """A move that can be selected by a Pokemon."""

    name: str
    type: str
    power: int | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | str) -> "Move":
        """Create a move from either a string name or a JSON object."""

        if isinstance(data, str):
            return cls(name=data, type="Unknown")
        return cls(
            name=str(data["name"]),
            type=str(data.get("type", "Unknown")),
            power=data.get("power"),
            category=data.get("category"),
            tags=list(data.get("tags", [])),
        )


@dataclass(frozen=True)
class PokemonSet:
    """A lightweight representation of one Pokemon in the current battle."""

    name: str
    types: list[str]
    hp_percent: int = 100
    moves: list[Move] = field(default_factory=list)
    role: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PokemonSet":
        return cls(
            name=str(data["name"]),
            types=list(data.get("types", [])),
            hp_percent=int(data.get("hp_percent", 100)),
            moves=[Move.from_dict(move) for move in data.get("moves", [])],
            role=data.get("role"),
        )


@dataclass(frozen=True)
class Action:
    """A candidate action for the assistant to evaluate."""

    kind: ActionKind
    name: str
    move_type: str | None = None
    target: str | None = None
    power: int | None = None
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Action":
        raw_kind = data.get("kind", data.get("type", "move"))
        if raw_kind not in {"move", "switch"}:
            raise ValueError(f"Unsupported action kind: {raw_kind}")

        name = str(data.get("name") or data.get("target"))
        return cls(
            kind=raw_kind,
            name=name,
            move_type=data.get("move_type") or data.get("type_name"),
            target=data.get("target"),
            power=data.get("power"),
            tags=list(data.get("tags", [])),
        )


@dataclass(frozen=True)
class BattleState:
    """The minimum battle state needed by the MVP evaluator."""

    rule_set: str
    my_active: PokemonSet
    opponent_active: PokemonSet
    available_actions: list[Action]
    notes: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BattleState":
        return cls(
            rule_set=str(data.get("rule_set", "unknown")),
            my_active=PokemonSet.from_dict(data["my_active"]),
            opponent_active=PokemonSet.from_dict(data["opponent_active"]),
            available_actions=[Action.from_dict(action) for action in data.get("available_actions", [])],
            notes=data.get("notes"),
        )


@dataclass(frozen=True)
class ActionEvaluation:
    """A scored action plus machine-readable reasons and risks."""

    action: Action
    score: int
    confidence: Confidence
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
