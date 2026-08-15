"""Perception layer: structured battle observations from poke-env battles.

将 poke-env 的原始 `AbstractBattle` 对象解析为结构化 `BattleObservation`，
跟踪对手已揭示信息，分类局面阶段，并生成中文局面摘要。
Battle Module 与 Lab Module 共用。
"""

from .classifier import classify_phase
from .observation import (
    BattleObservation,
    LegalOrder,
    MoveInfo,
    ObservationBuilder,
    PokemonSnapshot,
    SwitchTarget,
)
from .summary import build_summary
from .tracker import InfoTracker, OpponentRevealedInfo, RevealedPokemon

__all__ = [
    "BattleObservation",
    "InfoTracker",
    "LegalOrder",
    "MoveInfo",
    "ObservationBuilder",
    "OpponentRevealedInfo",
    "PokemonSnapshot",
    "RevealedPokemon",
    "SwitchTarget",
    "build_summary",
    "classify_phase",
]
