"""LabRunner：批量对战调度（asyncio + 并发上限）。

``run_battle`` 可注入：测试传假函数，生产用默认的真实 BattleSession。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import BatchConfig, BattleTask
from .stats import StatsCollector

BattleFn = Callable[[BattleTask, BatchConfig], Awaitable["BattleTaskResult"]]


@dataclass
class BattleTaskResult:
    task_id: str
    opponent: str
    won: bool | None = None
    turns: int | None = None
    battle_tag: str = ""
    record_path: str = ""
    selected_slots: list[int] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "opponent": self.opponent,
            "won": self.won,
            "turns": self.turns,
            "battle_tag": self.battle_tag,
            "record_path": self.record_path,
            "selected_slots": self.selected_slots,
            "error": self.error,
        }


@dataclass
class LabReport:
    config: dict[str, Any]
    results: list[BattleTaskResult] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "lab-report.v1",
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "config": self.config,
            "stats": self.stats,
            "results": [r.to_dict() for r in self.results],
        }


async def run_real_battle(task: BattleTask, config: BatchConfig) -> BattleTaskResult:
    """默认实现：加载双方队伍模板，用 BattleSession 跑一局真实对战。"""
    from ...modules.battle.agent_player import create_agent_player
    from ...modules.battle.session import AgentBattleConfig, BattleSession

    result = BattleTaskResult(task_id=task.task_id, opponent=task.opponent)
    try:
        from ...agent.llm_client import LLMClient
        from ...pba_cli import load_trainer_template_for_cli
        from ...team_converter import template_to_showdown_text

        _, p1_template = load_trainer_template_for_cli(config.team)
        p1_team_text = template_to_showdown_text(p1_template)
        _, p2_template = load_trainer_template_for_cli(task.opponent)
        p2_team_text = template_to_showdown_text(p2_template)

        backend = config.backend if config.backend in ("openai", "ollama") else None
        llm = LLMClient(backend=backend, model=config.model)  # type: ignore[arg-type]
        agent_player = create_agent_player(
            llm,
            label="player_1",
            battle_format=config.battle_format,
            team=p1_team_text,
        )
        battle_config = AgentBattleConfig(
            battle_format=config.battle_format,
            player_team=p1_team_text,
            player_source=config.team,
            opponent_team=p2_team_text,
            opponent_source=task.opponent,
            opponent_control="random",
            output_root=Path(config.output_root) / "battles",
            metadata={"entrypoint": "pba lab run", "task_id": task.task_id},
        )
        battle_result = await BattleSession(agent_player).run(battle_config)
        record = battle_result.record
        battle = record.get("battle", {})
        result.won = bool(battle.get("won"))
        result.turns = int(battle.get("turns") or 0)
        result.battle_tag = str(battle.get("battle_tag") or battle_result.battle_tag)
        result.record_path = str(battle_result.record_path)
        preview = (record.get("team_preview") or {}).get("player_1") or {}
        result.selected_slots = [int(s) for s in preview.get("selected_slots") or []]
    except Exception as exc:  # noqa: BLE001 — 单局失败不应中断批量
        result.error = f"{type(exc).__name__}: {exc}"
    return result


class LabRunner:
    """并发调度批量对战。"""

    def __init__(self, run_battle: BattleFn | None = None) -> None:
        self.run_battle = run_battle or run_real_battle

    async def run(self, config: BatchConfig) -> LabReport:
        started = datetime.now().isoformat(timespec="seconds")
        stats = StatsCollector()
        semaphore = asyncio.Semaphore(max(1, config.concurrency))
        tasks = config.battle_tasks()
        results: list[BattleTaskResult] = []

        async def worker(task: BattleTask) -> BattleTaskResult:
            async with semaphore:
                return await self.run_battle(task, config)

        results = list(await asyncio.gather(*(worker(task) for task in tasks)))
        for item in results:
            stats.add(
                item.opponent,
                won=item.won,
                turns=item.turns,
                selected_slots=item.selected_slots or None,
                error=item.error,
            )
        return LabReport(
            config=config.to_dict(),
            results=results,
            stats=stats.summary(),
            started_at=started,
            finished_at=datetime.now().isoformat(timespec="seconds"),
        )
