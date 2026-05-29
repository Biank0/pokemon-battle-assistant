"""Action-space helpers for environment records.

This module does not choose actions. It only turns poke-env battle snapshots
into a stable, serializable list of legal actions for future user/RL clients.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ActionKind = Literal["move", "switch", "order"]


@dataclass(frozen=True)
class LegalAction:
    """A serializable legal action exposed by the battle environment.

    `action_id` is intended to be stable enough for logs and future adapters.
    `command` stores the raw poke-env / Showdown order message when available.
    """

    action_id: str
    kind: ActionKind
    label: str
    command: str | None = None
    index: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def legal_actions_from_snapshot(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Build JSON-serializable legal actions from a recorded battle snapshot."""

    actions: list[LegalAction] = []

    # Prefer exact poke-env valid order messages when present. These preserve
    # special flags such as terastallize/dynamax if poke-env exposes them.
    for idx, message in enumerate(snapshot.get("legal_order_messages") or [], start=1):
        actions.append(
            LegalAction(
                action_id=f"order:{idx}",
                kind="order",
                label=str(message).replace("/choose ", "", 1),
                command=str(message),
                index=idx,
                payload={},
            )
        )

    if actions:
        return [action.to_dict() for action in actions]

    # Fallback for older records that only have normalized available moves and
    # switches. This is less exact than valid_order_messages but still useful for
    # offline datasets and reports.
    for idx, move in enumerate(snapshot.get("available_moves") or [], start=1):
        move_id = move.get("id") or move.get("name") or f"move-{idx}"
        actions.append(
            LegalAction(
                action_id=f"move:{move_id}",
                kind="move",
                label=str(move.get("name") or move_id),
                command=f"/choose move {move_id}",
                index=idx,
                payload=move,
            )
        )

    for idx, mon in enumerate(snapshot.get("available_switches") or [], start=1):
        species = mon.get("species") or mon.get("base_species") or f"switch-{idx}"
        actions.append(
            LegalAction(
                action_id=f"switch:{species}",
                kind="switch",
                label=str(species),
                command=f"/choose switch {species}",
                index=idx,
                payload=mon,
            )
        )

    return [action.to_dict() for action in actions]


def chosen_action_from_message(message: str | None) -> dict[str, Any] | None:
    """Create a serializable chosen-action record from a raw order message."""

    if not message:
        return None
    text = str(message)
    if text.startswith("/choose move "):
        label = text.removeprefix("/choose move ")
        return LegalAction(action_id=f"chosen:{label}", kind="move", label=label, command=text).to_dict()
    if text.startswith("/choose switch "):
        label = text.removeprefix("/choose switch ")
        return LegalAction(action_id=f"chosen:{label}", kind="switch", label=label, command=text).to_dict()
    return LegalAction(action_id="chosen:order", kind="order", label=text, command=text).to_dict()
