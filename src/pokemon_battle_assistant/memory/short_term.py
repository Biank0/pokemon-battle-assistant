"""Short-term memory: everything tracked within a single battle."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..perception.tracker import RevealedPokemon
from .event_log import BattleEvent, EventLog

if TYPE_CHECKING:
    from ..perception.observation import BattleObservation


@dataclass(frozen=True)
class TurnAction:
    """One turn's chosen orders (as order messages)."""

    turn: int
    my_order: str | None = None
    opponent_order: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"turn": self.turn, "my_order": self.my_order, "opponent_order": self.opponent_order}


@dataclass
class BeliefState:
    """对手未揭示宝可梦的粗略估计（BSS：对手带 6 只，选 3 出战）。"""

    team_size: int = 6
    revealed_species: list[str] = field(default_factory=list)

    @property
    def unseen_count(self) -> int:
        return max(0, self.team_size - len(self.revealed_species))

    def to_dict(self) -> dict[str, Any]:
        return {"team_size": self.team_size, "revealed_species": list(self.revealed_species), "unseen_count": self.unseen_count}


@dataclass
class ShortTermMemory:
    """本局记忆，每回合由 MemoryManager 更新。"""

    battle_tag: str
    revealed_pokemon: dict[str, RevealedPokemon] = field(default_factory=dict)
    action_history: list[TurnAction] = field(default_factory=list)
    hp_history: list[dict[str, Any]] = field(default_factory=list)
    weather_history: list[str] = field(default_factory=list)
    events: EventLog = field(default_factory=EventLog)
    current_belief: BeliefState = field(default_factory=lambda: BeliefState())
    tera_used: bool = False
    last_turn: int = 0

    def update_from_observation(self, observation: BattleObservation) -> list[BattleEvent]:
        """用新的观测更新本局记忆，返回本轮新产生的事件列表。"""
        new_events: list[BattleEvent] = []
        turn = observation.turn
        self.last_turn = turn

        # 1) 已揭示宝可梦信息（对比旧记录生成事件）
        for species, record in observation.opponent_revealed.get("pokemon", {}).items():
            existing = self.revealed_pokemon.get(species)
            if existing is None:
                self.revealed_pokemon[species] = RevealedPokemon(
                    species=species,
                    moves=list(record.get("moves", [])),
                    ability=record.get("ability"),
                    item=record.get("item"),
                    tera_type=record.get("tera_type"),
                    fainted=bool(record.get("fainted", False)),
                    first_seen_turn=turn,
                    last_seen_turn=turn,
                )
                new_events.append(
                    BattleEvent(turn=turn, kind="switch", side="opponent", detail=f"{species} 首次登场", data={"species": species})
                )
                continue

            existing.last_seen_turn = turn
            for move in record.get("moves", []):
                if move not in existing.moves:
                    existing.moves.append(move)
            if record.get("ability") and not existing.ability:
                existing.ability = record["ability"]
            if record.get("item") and not existing.item:
                existing.item = record["item"]
                new_events.append(
                    BattleEvent(turn=turn, kind="item_reveal", side="opponent", detail=f"{species} 的道具是 {record['item']}", data={"species": species, "item": record["item"]})
                )
            if record.get("tera_type") and not existing.tera_type:
                existing.tera_type = record["tera_type"]
                self.tera_used = True
                new_events.append(
                    BattleEvent(turn=turn, kind="terastallize", side="opponent", detail=f"{species} 太晶化为 {record['tera_type']}", data={"species": species, "tera_type": record["tera_type"]})
                )
            if record.get("fainted") and not existing.fainted:
                existing.fainted = True
                new_events.append(
                    BattleEvent(turn=turn, kind="ko", side="opponent", detail=f"{species} 被击倒", data={"species": species})
                )

        # 2) 我方/对方在场 HP 快照
        hp_entry: dict[str, Any] = {"turn": turn}
        if observation.my_active:
            hp_entry["my_active"] = observation.my_active.hp_percent
        if observation.opponent_active:
            hp_entry["opponent_active"] = observation.opponent_active.hp_percent
        self.hp_history.append(hp_entry)

        # 3) 天气历史
        if observation.weather:
            current_weather = "/".join(sorted(observation.weather))
            if not self.weather_history or self.weather_history[-1] != current_weather:
                self.weather_history.append(current_weather)
                new_events.append(BattleEvent(turn=turn, kind="weather", side="both", detail=current_weather))

        # 4) 信念状态
        self.current_belief = BeliefState(
            team_size=max(len(observation.opponent_team), 6) if observation.opponent_team else 6,
            revealed_species=list(self.revealed_pokemon.keys()),
        )

        for event in new_events:
            self.events.append(event)
        return new_events

    def record_action(self, turn: int, my_order: str | None, opponent_order: str | None = None) -> None:
        self.action_history.append(TurnAction(turn=turn, my_order=my_order, opponent_order=opponent_order))

    def to_dict(self) -> dict[str, Any]:
        return {
            "battle_tag": self.battle_tag,
            "revealed_pokemon": {k: v.to_dict() for k, v in self.revealed_pokemon.items()},
            "action_history": [a.to_dict() for a in self.action_history],
            "hp_history": list(self.hp_history),
            "weather_history": list(self.weather_history),
            "events": self.events.to_dicts(),
            "current_belief": self.current_belief.to_dict(),
            "tera_used": self.tera_used,
            "last_turn": self.last_turn,
        }
