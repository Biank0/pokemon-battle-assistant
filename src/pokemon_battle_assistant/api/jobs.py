"""后台任务注册表：battle / lab / orchestrator 长任务的统一状态管理。

BackgroundTasks 在线程池里调用同步入口，内部用独立事件循环跑协程，
对 uvicorn 与 TestClient 都成立。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass
class JobInfo:
    """一个后台任务的运行状态。"""

    job_id: str
    kind: str  # battle / lab / orchestrator
    status: str = "running"  # running / done / error
    created_at: str = ""
    finished_at: str = ""
    error: str | None = None
    result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "status": self.status,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "result": self.result,
        }


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class JobRegistry:
    """job_id -> JobInfo 注册表。"""

    def __init__(self) -> None:
        self._jobs: dict[str, JobInfo] = {}

    def create(self, kind: str) -> JobInfo:
        job = JobInfo(job_id=f"job-{uuid4().hex[:8]}", kind=kind, created_at=_now())
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> JobInfo | None:
        return self._jobs.get(job_id)

    def run(self, job: JobInfo, factory: Callable[[], Coroutine[Any, Any, dict[str, Any]]]) -> None:
        """同步入口（线程池调用），内部用独立事件循环执行协程。"""

        async def _wrapper() -> dict[str, Any]:
            return await factory()

        try:
            job.result = asyncio.run(_wrapper())
            job.status = "done"
        except Exception as exc:  # noqa: BLE001
            job.status = "error"
            job.error = str(exc)
        finally:
            job.finished_at = _now()
