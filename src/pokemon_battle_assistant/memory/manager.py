"""MemoryManager: unified entry point for the memory layer."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..perception.tracker import InfoTracker
from .long_term import LongTermMemory
from .opponent import OpponentModel
from .short_term import ShortTermMemory

if TYPE_CHECKING:
    from ..perception.observation import BattleObservation

DEFAULT_MEMORY_PATH = Path("data/memory/long_term.json")


class MemoryManager:
    """组合 InfoTracker + ShortTermMemory + LongTermMemory + OpponentModel。

    典型用法（每回合决策前）::

        manager = MemoryManager()
        observation = builder.build(battle, opponent_revealed=manager.update(battle).to_dict())
        manager.update_after_turn(battle.battle_tag, observation)
        model = manager.get_opponent_model(battle.battle_tag)
    """

    def __init__(self, *, memory_path: str | Path | None = None, project_root: str | Path | None = None) -> None:
        if memory_path is None:
            root = Path(project_root) if project_root else Path.cwd()
            self.memory_path = root / "data" / "memory" / "long_term.json"
        else:
            self.memory_path = Path(memory_path)
        self.tracker = InfoTracker()
        self._short_term: dict[str, ShortTermMemory] = {}
        self.long_term = LongTermMemory.load(self.memory_path)

    # ---- 短期记忆 ----
    def get_short_term(self, battle_tag: str) -> ShortTermMemory:
        return self._short_term.setdefault(battle_tag, ShortTermMemory(battle_tag=battle_tag))

    def get_opponent_model(self, battle_tag: str) -> OpponentModel:
        return OpponentModel(self.get_short_term(battle_tag))

    # ---- 长期记忆 ----
    def get_long_term(self) -> LongTermMemory:
        return self.long_term

    # ---- 每回合更新 ----
    def update(self, battle: Any) -> Any:
        """先用原始 battle 更新 InfoTracker（感知层揭示信息）。"""
        return self.tracker.update(battle)

    def update_after_turn(self, battle_tag: str, observation: BattleObservation) -> list[Any]:
        """每回合调用：更新短期记忆，返回新事件列表。"""
        return self.get_short_term(battle_tag).update_from_observation(observation)

    def record_action(self, battle_tag: str, turn: int, my_order: str | None, opponent_order: str | None = None) -> None:
        self.get_short_term(battle_tag).record_action(turn, my_order, opponent_order)

    # ---- 每局结束 ----
    def update_after_battle(
        self,
        battle_tag: str,
        *,
        won: bool,
        opponent: str = "unknown",
        my_team_key: str = "default",
        my_lead: str | None = None,
        summary: dict[str, Any] | None = None,
    ) -> None:
        self.long_term.record_battle_result(
            opponent=opponent,
            won=won,
            my_team_key=my_team_key,
            my_lead=my_lead,
            summary=summary,
        )
        self.persist()

    # ---- 持久化 ----
    def persist(self) -> None:
        self.long_term.save(self.memory_path)
