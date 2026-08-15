"""BattleAgentPlayer 工厂：组装 LLMClient + BattleAgent + RecordingAgentPlayer。"""

from __future__ import annotations

from typing import Any

from ...agent.agent import BattleAgent
from ...agent.llm_client import LLMClient


def create_agent_player(
    llm: LLMClient,
    *,
    label: str,
    battle_format: str,
    team: str | None = None,
    memory: Any = None,
    builder: Any = None,
    selection_config: Any = None,
    expected_selection_size: int | None = None,
    max_tool_rounds: int = 3,
    team_size: int = 3,
) -> Any:
    """创建一个由 BattleAgent 驱动的 RecordingAgentPlayer。"""
    from ...battle_recorder import RecordingAgentPlayer

    agent = BattleAgent(
        llm,
        max_tool_rounds=max_tool_rounds,
        team_size=team_size,
    )
    return RecordingAgentPlayer(
        label=label,
        battle_format=battle_format,
        max_concurrent_battles=1,
        save_replays=False,
        team=team,
        agent=agent,
        memory=memory,
        builder=builder,
        selection_config=selection_config,
        expected_selection_size=expected_selection_size,
    )
