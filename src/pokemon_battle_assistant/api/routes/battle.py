"""Battle API：后台启动单局 Agent 对战并查询状态/结果。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ..jobs import JobRegistry


class BattleStartRequest(BaseModel):
    template: str
    opponent: str | None = None
    format: str | None = None
    opponent_control: str = "random"
    backend: str | None = None
    model: str | None = None


async def _run_real_battle(payload: dict[str, Any], output_root: str) -> dict[str, Any]:
    """默认实现：加载队伍模板，用 BattleSession 跑一局真实对战。"""
    from ...agent.llm_client import LLMClient
    from ...modules.battle.agent_player import create_agent_player
    from ...modules.battle.session import AgentBattleConfig, BattleSession
    from ...pba_cli import load_trainer_template_for_cli
    from ...team_converter import template_to_showdown_text

    _, p1_template = load_trainer_template_for_cli(payload["template"])
    p1_team = template_to_showdown_text(p1_template)
    if payload.get("opponent"):
        _, p2_template = load_trainer_template_for_cli(payload["opponent"])
        p2_team = template_to_showdown_text(p2_template)
    else:
        p2_team = p1_team

    battle_format = payload.get("format") or p1_template.get("format") or "gen9bssregi"
    backend = payload.get("backend")
    backend = backend if backend in ("openai", "ollama") else None
    llm = LLMClient(backend=backend, model=payload.get("model"))

    player = create_agent_player(llm, label="player_1", battle_format=battle_format, team=p1_team)
    config = AgentBattleConfig(
        battle_format=battle_format,
        player_team=p1_team,
        player_source=payload["template"],
        opponent_team=p2_team,
        opponent_source=payload.get("opponent") or payload["template"],
        opponent_control=payload.get("opponent_control") or "random",
        output_root=Path(output_root),
        metadata={"entrypoint": "api /api/battle/start"},
    )
    result = await BattleSession(player).run(config)
    battle = result.record.get("battle", {})
    return {
        "battle_tag": battle.get("battle_tag"),
        "turns": battle.get("turns"),
        "won": battle.get("won"),
        "files": result.to_dict(),
    }


def create_battle_router(
    registry: JobRegistry,
    *,
    battle_runner: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
    battle_output_root: str = "battle_outputs",
) -> APIRouter:
    router = APIRouter(prefix="/api/battle", tags=["battle"])

    @router.post("/start")
    def start(request: BattleStartRequest, background: BackgroundTasks) -> dict[str, str]:
        job = registry.create("battle")
        payload = request.model_dump()

        async def _factory() -> dict[str, Any]:
            if battle_runner is not None:
                return dict(await battle_runner(payload))
            return await _run_real_battle(payload, battle_output_root)

        background.add_task(registry.run, job, _factory)
        return {"job_id": job.job_id, "status": job.status}

    @router.get("/{job_id}/status")
    def status(job_id: str) -> dict[str, Any]:
        job = registry.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"任务不存在：{job_id}")
        return job.to_dict()

    @router.get("/{job_id}/result")
    def result(job_id: str) -> dict[str, Any]:
        job = registry.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"任务不存在：{job_id}")
        if job.status == "error":
            raise HTTPException(status_code=500, detail=job.error or "任务执行失败")
        if job.status != "done":
            raise HTTPException(status_code=409, detail="任务尚未完成")
        return job.result

    return router
