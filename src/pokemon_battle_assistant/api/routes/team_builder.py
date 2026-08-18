"""Team Builder API：AI 建队 / 迭代优化 / 历史记录。"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from .teams import TeamsStore, translate_team_zh

_HISTORY_LIMIT = 50


class GenerateRequest(BaseModel):
    requirement: str
    format: str = "gen9bssregi"


class IterateRequest(BaseModel):
    team: dict[str, Any]
    report: dict[str, Any]
    format: str = "gen9bssregi"


def _result_payload(result: Any) -> dict[str, Any]:
    return {
        "team": dict(getattr(result, "team", {}) or {}),
        "valid": bool(getattr(result, "valid", False)),
        "validation_errors": list(getattr(result, "validation_errors", []) or []),
        "reasoning": str(getattr(result, "reasoning", "") or ""),
        "iteration": int(getattr(result, "iteration", 0) or 0),
    }


def _slugify(name: Any) -> str | None:
    """把生成器给的队名压成合法文件 ID（字母数字下划线连字符）。"""
    text = str(name or "").strip().lower()
    slug = re.sub(r"[^0-9a-z_\-]+", "_", text).strip("_")
    return slug or None


def _persist_team(
    store: TeamsStore | None,
    template: dict[str, Any],
    *,
    display_name: str,
) -> str | None:
    """把生成/迭代的队伍存进 generated 目录（重名覆盖），供实验室/对战选用。

    返回实际保存的队伍 ID（slug），未保存时返回 None。
    """
    if store is None:
        return None
    slug = _slugify(template.get("name"))
    if not slug or not isinstance(template.get("team"), list):
        return None
    store.delete(slug)  # 同名覆盖（迭代场景）
    try:
        store.create(slug, template, source="generated", display_name=display_name)
    except Exception:  # 持久化失败不阻塞主流程
        return None
    return slug


def create_team_builder_router(
    get_builder: Callable[[], Any],
    store: TeamsStore | None = None,
) -> APIRouter:
    history: list[dict[str, Any]] = []
    router = APIRouter(prefix="/api/team-builder", tags=["team-builder"])

    @router.post("/generate")
    def generate(request: GenerateRequest) -> dict[str, Any]:
        result = get_builder().generate_team(request.requirement, format=request.format)
        payload = _result_payload(result)
        payload["saved_name"] = (
            _persist_team(
                store,
                payload["team"],
                display_name="AI 生成·" + request.requirement.strip()[:12],
            )
            if payload["valid"]
            else None
        )
        history.append(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "action": "generate",
                "requirement": request.requirement,
                "format": request.format,
                "valid": payload["valid"],
                "team_name": payload["team"].get("name"),
            }
        )
        payload["team_zh"] = translate_team_zh(payload["team"])
        return payload

    @router.post("/iterate")
    def iterate(request: IterateRequest) -> dict[str, Any]:
        result = get_builder().iterate_team(request.team, request.report, format=request.format)
        payload = _result_payload(result)
        payload["saved_name"] = (
            _persist_team(
                store,
                payload["team"],
                display_name="AI 迭代·v" + str(payload["iteration"]),
            )
            if payload["valid"]
            else None
        )
        history.append(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "action": "iterate",
                "format": request.format,
                "valid": payload["valid"],
                "team_name": payload["team"].get("name"),
            }
        )
        payload["team_zh"] = translate_team_zh(payload["team"])
        return payload

    @router.get("/history")
    def get_history() -> dict[str, Any]:
        return {"history": list(history[-_HISTORY_LIMIT:])}

    return router
