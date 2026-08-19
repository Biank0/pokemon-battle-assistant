"""AI 建队任务 API：POST 发起（后台线程）+ GET 轮询。

建队流水线一次约 15~30 秒（两次 LLM 调用 + 校验修复），不适合同步请求，
用内存任务表 + 前端轮询。服务重启任务表即清空（任务本身短命，可接受）。
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...harness.llm import LLMError, LLMHarness
from ...skills.team_building import skill as skill_pkg
from ...team_builder import pipeline

ROOT_DIR = Path(__file__).resolve().parents[4]
router = APIRouter()

_jobs: dict[str, dict] = {}


class GenerateRequest(BaseModel):
    requirement: str
    format: str = "gen9bssregi"
    skill_version: str = "v1"


@router.post("/generate")
def start_generate(req: GenerateRequest):
    req.requirement = req.requirement.strip()
    if not req.requirement:
        raise HTTPException(400, "建队需求不能为空")
    try:
        skill_pkg.load(req.skill_version).constraints(req.format)
    except (KeyError, FileNotFoundError) as e:
        raise HTTPException(400, str(e))
    try:
        harness = LLMHarness.from_env(ROOT_DIR / ".env")
    except LLMError as e:
        raise HTTPException(500, f"LLM 配置异常: {e}")

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        "id": job_id, "status": "running", "logs": [],
        "team": None, "usage": "", "attempts": 0,
        "error": None, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    threading.Thread(target=_run_job, args=(job_id, req, harness), daemon=True).start()
    return {"job_id": job_id}


@router.get("/generate/{job_id}")
def get_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"任务不存在或已过期: {job_id}")
    return job


def _run_job(job_id: str, req: GenerateRequest, harness: LLMHarness) -> None:
    """后台线程：跑流水线，日志经 pipeline 的 threading.local 钩子送回任务表。"""
    job = _jobs[job_id]

    def hook(msg: str) -> None:
        job["logs"].append(msg.strip())

    pipeline._local.hook = hook
    try:
        res = pipeline.generate_team(req.requirement, format_id=req.format,
                                     harness=harness, skill_version=req.skill_version)
        job.update(
            status="done",
            team={"name": res.name, "display_name": res.display_name,
                  "strategy": res.strategy},
            usage=res.usage, attempts=res.attempts)
    except Exception as e:  # 流水线任何失败都转为任务失败（前端可见）
        job.update(status="failed", error=str(e))
    finally:
        pipeline._local.hook = None
        # 只保留最近 50 个任务，防内存膨胀
        if len(_jobs) > 50:
            for k in list(_jobs)[:len(_jobs) - 50]:
                _jobs.pop(k, None)
