"""Lab API：后台启动批量对战并查询状态/报告。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ..jobs import JobRegistry


class LabStartRequest(BaseModel):
    team: str
    opponents: list[str]
    battles_per_opponent: int = 3
    format: str = "gen9bssregi"
    concurrency: int = 2
    backend: str | None = None
    model: str | None = None
    output_root: str = "lab_outputs"


def create_lab_router(registry: JobRegistry, *, lab_runner_provider: Callable[[], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/lab", tags=["lab"])

    @router.post("/start")
    def start(request: LabStartRequest, background: BackgroundTasks) -> dict[str, str]:
        job = registry.create("lab")
        payload = request.model_dump()

        async def _factory() -> dict[str, Any]:
            from ...modules.lab.config import BatchConfig

            backend = payload.get("backend")
            config = BatchConfig(
                team=payload["team"],
                opponents=list(payload["opponents"]),
                battles_per_opponent=int(payload.get("battles_per_opponent") or 3),
                battle_format=payload.get("format") or "gen9bssregi",
                concurrency=int(payload.get("concurrency") or 2),
                backend=backend if backend in ("openai", "ollama") else None,
                model=payload.get("model"),
                output_root=Path(payload.get("output_root") or "lab_outputs"),
            )
            report = await lab_runner_provider().run(config)
            try:
                return dict(report.to_dict())
            except AttributeError:
                return {"stats": dict(getattr(report, "stats", {}) or {})}

        background.add_task(registry.run, job, _factory)
        return {"job_id": job.job_id, "status": job.status}

    @router.get("/{job_id}/status")
    def status(job_id: str) -> dict[str, Any]:
        job = registry.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"任务不存在：{job_id}")
        return job.to_dict()

    @router.get("/{job_id}/report")
    def report(job_id: str) -> dict[str, Any]:
        job = registry.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"任务不存在：{job_id}")
        if job.status == "error":
            raise HTTPException(status_code=500, detail=job.error or "任务执行失败")
        if job.status != "done":
            raise HTTPException(status_code=409, detail="任务尚未完成")
        return job.result

    return router
