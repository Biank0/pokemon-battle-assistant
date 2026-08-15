"""Track revealed information about the opponent's team."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RevealedPokemon:
    """对手一只宝可梦已揭示的信息（按 species 聚合）。"""

    species: str
    moves: list[str] = field(default_factory=list)
    ability: str | None = None
    item: str | None = None
    tera_type: str | None = None
    fainted: bool = False
    first_seen_turn: int = 0
    last_seen_turn: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "species": self.species,
            "moves": list(self.moves),
            "ability": self.ability,
            "item": self.item,
            "tera_type": self.tera_type,
            "fainted": self.fainted,
            "first_seen_turn": self.first_seen_turn,
            "last_seen_turn": self.last_seen_turn,
        }


@dataclass
class OpponentRevealedInfo:
    """整局对手已揭示信息的聚合。"""

    battle_tag: str
    pokemon: dict[str, RevealedPokemon] = field(default_factory=dict)
    tera_used: bool = False
    revealed_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "battle_tag": self.battle_tag,
            "pokemon": {k: v.to_dict() for k, v in self.pokemon.items()},
            "tera_used": self.tera_used,
            "revealed_count": self.revealed_count,
        }


def _iter_opponent_pokemon(battle: Any):
    team = getattr(battle, "opponent_team", None) or {}
    if hasattr(team, "values"):
        return list(team.values())
    if isinstance(team, (list, tuple)):
        return list(team)
    return []


class InfoTracker:
    """每回合调用 `update()`，聚合对手已揭示的宝可梦/招式/道具/太晶信息。

    poke-env 只在信息实际暴露后填充对手宝可梦属性：
    - `moves`：对手用过的招式
    - `ability`：特性触发或公开队表后才有值
    - `item`：道具效果揭示后才有值
    - `tera_type`：对手太晶化后才有值
    """

    def __init__(self) -> None:
        self._cache: dict[str, OpponentRevealedInfo] = {}

    def get(self, battle_tag: str) -> OpponentRevealedInfo:
        return self._cache.setdefault(battle_tag, OpponentRevealedInfo(battle_tag=battle_tag))

    def update(self, battle: Any) -> OpponentRevealedInfo:
        battle_tag = str(getattr(battle, "battle_tag", ""))
        info = self.get(battle_tag)
        turn = int(getattr(battle, "turn", 0) or 0)

        for mon in _iter_opponent_pokemon(battle):
            species = str(getattr(mon, "species", "?"))
            record = info.pokemon.get(species)
            if record is None:
                record = RevealedPokemon(species=species, first_seen_turn=turn)
                info.pokemon[species] = record
            record.last_seen_turn = turn

            for move in (getattr(mon, "moves", None) or {}):
                move_name = str(move)
                if move_name not in record.moves:
                    record.moves.append(move_name)

            ability = getattr(mon, "ability", None)
            if ability:
                record.ability = str(ability)
            item = getattr(mon, "item", None)
            if item:
                record.item = str(item)

            if bool(getattr(mon, "terastallized", False)):
                tera = getattr(mon, "tera_type", None)
                if tera:
                    record.tera_type = str(tera)
                    info.tera_used = True

            if bool(getattr(mon, "fainted", False)):
                record.fainted = True

        info.revealed_count = len(info.pokemon)
        return info
