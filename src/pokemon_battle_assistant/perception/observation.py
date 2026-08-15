"""Structured battle observation built from a poke-env battle object."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ..translation import translate_move, translate_pokemon


@dataclass(frozen=True)
class MoveInfo:
    """A move currently usable by my active pokemon."""

    name: str
    zh_name: str
    move_type: str
    base_power: int | None
    accuracy: int | None
    category: str
    priority: int
    target: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "zh_name": self.zh_name,
            "type": self.move_type,
            "base_power": self.base_power,
            "accuracy": self.accuracy,
            "category": self.category,
            "priority": self.priority,
            "target": self.target,
        }


@dataclass(frozen=True)
class SwitchTarget:
    """A pokemon I can switch into."""

    species: str
    zh_name: str
    hp_percent: float | None
    status: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "species": self.species,
            "zh_name": self.zh_name,
            "hp_percent": self.hp_percent,
            "status": self.status,
        }


@dataclass(frozen=True)
class LegalOrder:
    """A legal order message as produced by the battle recorder."""

    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"message": self.message}


@dataclass(frozen=True)
class PokemonSnapshot:
    """Snapshot of one pokemon (mine or opponent's)."""

    species: str
    zh_name: str
    level: int | None
    hp_percent: float | None
    status: str | None
    types: tuple[str, ...]
    tera_type: str | None
    terastallized: bool
    item: str | None
    ability: str | None
    moves: tuple[str, ...]
    fainted: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "species": self.species,
            "zh_name": self.zh_name,
            "level": self.level,
            "hp_percent": self.hp_percent,
            "status": self.status,
            "types": list(self.types),
            "tera_type": self.tera_type,
            "terastallized": self.terastallized,
            "item": self.item,
            "ability": self.ability,
            "moves": list(self.moves),
            "fainted": self.fainted,
        }


@dataclass(frozen=True)
class BattleObservation:
    """Structured observation of one decision point."""

    battle_tag: str
    turn: int
    format: str
    game_type: str
    my_active: PokemonSnapshot | None
    opponent_active: PokemonSnapshot | None
    my_team: list[PokemonSnapshot] = field(default_factory=list)
    opponent_team: list[PokemonSnapshot] = field(default_factory=list)
    available_moves: list[MoveInfo] = field(default_factory=list)
    available_switches: list[SwitchTarget] = field(default_factory=list)
    legal_orders: list[LegalOrder] = field(default_factory=list)
    weather: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    side_conditions: list[str] = field(default_factory=list)
    opponent_side_conditions: list[str] = field(default_factory=list)
    opponent_revealed: dict[str, dict[str, Any]] = field(default_factory=dict)
    phase: str = "midgame"
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "battle_tag": self.battle_tag,
            "turn": self.turn,
            "format": self.format,
            "game_type": self.game_type,
            "my_active": self.my_active.to_dict() if self.my_active else None,
            "opponent_active": self.opponent_active.to_dict() if self.opponent_active else None,
            "my_team": [m.to_dict() for m in self.my_team],
            "opponent_team": [m.to_dict() for m in self.opponent_team],
            "available_moves": [m.to_dict() for m in self.available_moves],
            "available_switches": [s.to_dict() for s in self.available_switches],
            "legal_orders": [o.to_dict() for o in self.legal_orders],
            "weather": list(self.weather),
            "fields": list(self.fields),
            "side_conditions": list(self.side_conditions),
            "opponent_side_conditions": list(self.opponent_side_conditions),
            "opponent_revealed": self.opponent_revealed,
            "phase": self.phase,
            "summary": self.summary,
        }


def _zh(value: str | None, translator) -> str:
    if not value:
        return ""
    translated = translator(value)
    return translated if translated else value


def _first_slot(value: Any) -> Any:
    """Return the single active pokemon from a possibly-sequence slot."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _hp_percent(mon: Any) -> float | None:
    hp = getattr(mon, "current_hp", None)
    max_hp = getattr(mon, "max_hp", None)
    if not max_hp or hp is None:
        return None
    return round(100.0 * hp / max_hp, 1)


def _status_name(mon: Any) -> str | None:
    status = getattr(mon, "status", None)
    if status is None:
        return None
    name = str(status).split(".")[-1]
    if name in {"NORMAL", "UNKNOWN", "None"}:
        return None
    return name


def _pokemon_snapshot(mon: Any) -> PokemonSnapshot:
    species = str(getattr(mon, "species", "?"))
    return PokemonSnapshot(
        species=species,
        zh_name=_zh(species, translate_pokemon),
        level=getattr(mon, "level", None),
        hp_percent=_hp_percent(mon),
        status=_status_name(mon),
        types=tuple(str(t) for t in (getattr(mon, "types", []) or [])),
        tera_type=getattr(mon, "tera_type", None),
        terastallized=bool(getattr(mon, "terastallized", False)),
        item=getattr(mon, "item", None) or None,
        ability=getattr(mon, "ability", None) or None,
        # poke-env 只在招式实际使用后记录，天然就是"已揭示"信息
        moves=tuple(str(m) for m in (getattr(mon, "moves", {}) or {}).keys()),
        fainted=bool(getattr(mon, "fainted", False)),
    )


def _move_info(move: Any) -> MoveInfo:
    name = str(getattr(move, "id", "") or "unknown")
    return MoveInfo(
        name=name,
        zh_name=_zh(name, translate_move),
        move_type=str(getattr(move, "type", "Unknown")),
        base_power=getattr(move, "base_power", None),
        accuracy=getattr(move, "accuracy", None),
        category=str(getattr(move, "category", "Unknown")),
        priority=getattr(move, "priority", 0) or 0,
        target=str(getattr(move, "target", "unknown")),
    )


def _switch_target(mon: Any) -> SwitchTarget:
    species = str(getattr(mon, "species", "?"))
    return SwitchTarget(
        species=species,
        zh_name=_zh(species, translate_pokemon),
        hp_percent=_hp_percent(mon),
        status=_status_name(mon),
    )


def _team_snapshots(team: Any) -> list[PokemonSnapshot]:
    if not team:
        return []
    mons = team.values() if hasattr(team, "values") else team
    return [_pokemon_snapshot(mon) for mon in mons]


def _legal_order_messages(battle: Any) -> list[str]:
    """Reuse battle_recorder's legal order rendering when available."""
    try:
        from ..battle_recorder import legal_order_messages

        return list(legal_order_messages(battle))
    except Exception:
        return []


class ObservationBuilder:
    """Build a `BattleObservation` from an `AbstractBattle`.

    `opponent_revealed` comes from `InfoTracker`（或 MemoryManager 转发），
    用于把对手已揭示信息嵌入观测。
    """

    def build(self, battle: Any, opponent_revealed: dict[str, Any] | None = None) -> BattleObservation:
        from .classifier import classify_phase
        from .summary import build_summary

        my_active_slot = getattr(battle, "active_pokemon", None)
        my_active = _first_slot(my_active_slot)
        opp_active = _first_slot(getattr(battle, "opponent_active_pokemon", None))
        game_type = "doubles" if isinstance(my_active_slot, (list, tuple)) else "singles"
        switches = getattr(battle, "available_switches", None) or {}

        observation = BattleObservation(
            battle_tag=str(getattr(battle, "battle_tag", "")),
            turn=int(getattr(battle, "turn", 0) or 0),
            format=str(getattr(battle, "format", "") or ""),
            game_type=game_type,
            my_active=_pokemon_snapshot(my_active) if my_active else None,
            opponent_active=_pokemon_snapshot(opp_active) if opp_active else None,
            my_team=_team_snapshots(getattr(battle, "team", None)),
            opponent_team=_team_snapshots(getattr(battle, "opponent_team", None)),
            available_moves=[_move_info(m) for m in (getattr(battle, "available_moves", None) or [])],
            available_switches=[_switch_target(mon) for mon in switches.values()]
            if hasattr(switches, "values")
            else [_switch_target(mon) for mon in switches],
            legal_orders=[LegalOrder(message=str(msg)) for msg in _legal_order_messages(battle)],
            weather=[str(k) for k in (getattr(battle, "weather", None) or {}).keys()],
            fields=[str(k) for k in (getattr(battle, "fields", None) or {}).keys()],
            side_conditions=[str(k) for k in (getattr(battle, "side_conditions", None) or {}).keys()],
            opponent_side_conditions=[
                str(k) for k in (getattr(battle, "opponent_side_conditions", None) or {}).keys()
            ],
            opponent_revealed=dict(opponent_revealed or {}),
        )
        phase = classify_phase(observation)
        summary = build_summary(observation, phase=phase)
        return replace(observation, phase=phase, summary=summary)
