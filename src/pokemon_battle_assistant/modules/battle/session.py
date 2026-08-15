"""BattleSession：单局 Agent 对战会话管理。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...environment import OUTPUT_ROOT
from .exporter import AgentBattleResult, build_agent_record, export_agent_battle


@dataclass(frozen=True)
class AgentBattleConfig:
    battle_format: str = "gen9bssregi"
    player_team: str | None = None
    player_source: str = "template"
    opponent_team: str | None = None
    opponent_source: str = "template"
    opponent_control: str = "random"  # random | manual
    output_root: Path = OUTPUT_ROOT
    expected_selection_size: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BattleSession:
    """一局对战：Agent player vs 对手 player，结束后导出全量记录。"""

    def __init__(self, agent_player: Any) -> None:
        self.agent_player = agent_player

    async def run(self, config: AgentBattleConfig) -> AgentBattleResult:
        from ...battle_recorder import RecordingManualPlayer, RecordingRandomPlayer

        opponent_cls = RecordingManualPlayer if config.opponent_control == "manual" else RecordingRandomPlayer
        opponent = opponent_cls(
            label="player_2",
            battle_format=config.battle_format,
            max_concurrent_battles=1,
            save_replays=False,
            team=config.opponent_team,
            expected_selection_size=config.expected_selection_size,
        )
        try:
            await self.agent_player.battle_against(opponent, n_battles=1)
            battle_tag = next(iter(self.agent_player.battles))
            battle = self.agent_player.battles[battle_tag]
            agent = self.agent_player.agent
            record = build_agent_record(
                battle=battle,
                agent_player=self.agent_player,
                opponent_player=opponent,
                battle_format=config.battle_format,
                player_source=config.player_source,
                opponent_source=config.opponent_source,
                agent_backend=str(getattr(agent.llm, "backend", "") or ""),
                agent_model=str(getattr(agent.llm, "model", "") or ""),
                metadata=config.metadata,
            )
            return export_agent_battle(record, battle=battle, output_root=config.output_root)
        finally:
            await self.agent_player.ps_client.stop_listening()
            await opponent.ps_client.stop_listening()
