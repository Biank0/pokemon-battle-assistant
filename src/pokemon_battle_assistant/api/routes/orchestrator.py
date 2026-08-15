"""Orchestrator API：启动/查询/确认闭环流程。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ..jobs import JobRegistry


class OrchestratorStartRequest(BaseModel):
    requirement: str
    opponents: list[str] = Field(default_factory=list)
    iterations: int = 3
    auto: bool = True
    battles: int = 3
    format: str = "gen9bssregi"
    concurrency: int = 2
    backend: str | None = None
    model: str | None = None
    stop_win_rate: float | None = None
    output_root: str = "orchestrator_outputs"


def create_orchestrator_router(
    registry: JobRegistry,
    *,
    orchestrator_provider: Callable[[], Any],
) -> APIRouter:
    router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])

    @router.post("/start")
    def start(request: OrchestratorStartRequest, background: BackgroundTasks) -> dict[str, str]:
        from ...modules.orchestrator import LoopConfig

        orchestrator = orchestrator_provider()
        run_id = f"run-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}"
        job = registry.create("orchestrator")
        payload = request.model_dump()

        async def _factory() -> dict[str, Any]:
            backend = payload.get("backend")
            config = LoopConfig(
                opponents=list(payload["opponents"]),
                battles_per_opponent=int(payload.get("battles") or 3),
                battle_format=payload.get("format") or "gen9bssregi",
                concurrency=int(payload.get("concurrency") or 2),
                backend=backend if backend in ("openai", "ollama") else None,
                model=payload.get("model"),
                stop_win_rate=payload.get("stop_win_rate"),
                output_root=Path(payload.get("output_root") or "orchestrator_outputs"),
            )
            result_run_id = await orchestrator.start_closed_loop(
                payload["requirement"],
                max_iterations=int(payload.get("iterations") or 3),
                auto_iterate=bool(payload.get("auto", True)),
                config=config,
                run_id=run_id,
            )
            return {"run_id": result_run_id}

        background.add_task(registry.run, job, _factory)
        return {"job_id": job.job_id, "run_id": run_id, "status": job.status}

    @router.get("/jobs/{job_id}")
    def job_status(job_id: str) -> dict[str, Any]:
        job = registry.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"任务不存在：{job_id}")
        return job.to_dict()

    @router.get("/{run_id}/status")
    def status(run_id: str) -> dict[str, Any]:
        orchestrator = orchestrator_provider()
        try:
            return orchestrator.get_status(run_id).to_dict()
        except KeyError:
            raise HTTPException(status_code=404, detail=f"闭环流程不存在：{run_id}") from None

    @router.get("/{run_id}/history")
    def history(run_id: str) -> dict[str, Any]:
        orchestrator = orchestrator_provider()
        try:
            records = orchestrator.get_iteration_history(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"闭环流程不存在：{run_id}") from None
        return {"iterations": [record.to_dict() for record in records]}

    @router.post("/{run_id}/confirm")
    async def confirm(run_id: str) -> dict[str, Any]:
        orchestrator = orchestrator_provider()
        try:
            await orchestrator.confirm_iteration(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"闭环流程不存在：{run_id}") from None
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        return orchestrator.get_status(run_id).to_dict()

    return router
