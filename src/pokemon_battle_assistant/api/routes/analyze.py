"""分析任务 API：POST 发起（后台线程）+ GET 轮询 + 报告列表/详情。

  POST /api/analyze            {session_id, focus?} → {job_id}
  GET  /api/analyze/{job_id}   轮询任务进度/结果
  GET  /api/analyses           报告索引列表
  GET  /api/analyses/{id}      报告详情（结构化 JSON + 高光跳转）
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...battle_analyzer import pipeline, repository
from ...battle_analyzer import distiller as distiller_mod
from ...harness.llm import LLMError, LLMHarness

ROOT_DIR = Path(__file__).resolve().parents[4]
router = APIRouter()

_jobs: dict[str, dict] = {}


class AnalyzeRequest(BaseModel):
    session_id: str
    focus: str = ""  # 用户特别关注点（可选，如"重点看看九尾"）


@router.post("/analyze")
def start_analyze(req: AnalyzeRequest):
    # 会话存在且有效（有对战数据）前置检查
    try:
        conn_meta = distiller_mod.distill_session(req.session_id)["session_meta"]
    except KeyError:
        raise HTTPException(404, "会话不存在")
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        harness = LLMHarness.from_env(ROOT_DIR / ".env")
    except LLMError as e:
        raise HTTPException(500, f"LLM 配置异常: {e}")

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {
        "id": job_id, "status": "running", "logs": [
            f"[分析] 目标：{conn_meta['team_a']} vs {conn_meta['team_b']}"],
        "result": None, "usage": "", "attempts": 0, "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    threading.Thread(target=_run_job, args=(job_id, req, harness), daemon=True).start()
    return {"job_id": job_id}


@router.get("/analyze/{job_id}")
def get_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"任务不存在或已过期: {job_id}")
    return job


@router.get("/analyses")
def list_reports():
    return {"analyses": repository.list_analyses()}


@router.get("/analyses/{analysis_id}")
def get_report(analysis_id: str):
    try:
        doc = repository.get_doc(analysis_id)
    except FileNotFoundError as e:
        raise HTTPException(410, str(e))
    if doc is None:
        raise HTTPException(404, "分析报告不存在")
    _enrich_species_slug(doc)
    return doc


def _enrich_species_slug(doc: dict) -> None:
    """就地补充 pokemon_performance[].species（slug，供前端精灵图）。

    分析文档由模型生成、只含中文名；slug 映射放读取侧补齐，
    存量文档无需重跑，skill 迭代也不受影响。
    """
    perf = (doc.get("report") or {}).get("pokemon_performance") or []
    if not perf:
        return
    dex_db = ROOT_DIR / "data" / "dex" / "dex.db"
    conn = sqlite3.connect(f"file:{dex_db}?mode=ro", uri=True)
    try:
        zh2slug = {r[1]: r[0] for r in conn.execute(
            "SELECT id, name_zh FROM species WHERE name_zh IS NOT NULL")}
    finally:
        conn.close()
    for p in perf:
        slug = zh2slug.get(p.get("species_zh", ""))
        if slug:
            p["species"] = slug


def _run_job(job_id: str, req: AnalyzeRequest, harness: LLMHarness) -> None:
    job = _jobs[job_id]

    def hook(msg: str) -> None:
        job["logs"].append(msg.strip())

    pipeline._local.hook = hook
    try:
        res = pipeline.analyze_session(req.session_id, harness,
                                       focus=req.focus)
        job.update(status="done",
                   result={"analysis_id": res.analysis_id, "title": res.title,
                           "headline": res.headline, "rating": res.rating},
                   usage=res.usage, attempts=res.attempts)
    except Exception as e:
        job.update(status="failed", error=str(e))
    finally:
        pipeline._local.hook = None
        if len(_jobs) > 50:
            for k in list(_jobs)[:len(_jobs) - 50]:
                _jobs.pop(k, None)
