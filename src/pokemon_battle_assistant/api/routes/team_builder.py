"""Team Builder API：AI 建队 / 迭代优化 / 历史记录。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

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


def create_team_builder_router(get_builder: Callable[[], Any]) -> APIRouter:
    history: list[dict[str, Any]] = []
    router = APIRouter(prefix="/api/team-builder", tags=["team-builder"])

    @router.post("/generate")
    def generate(request: GenerateRequest) -> dict[str, Any]:
        result = get_builder().generate_team(request.requirement, format=request.format)
        payload = _result_payload(result)
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
        return payload

    @router.post("/iterate")
    def iterate(request: IterateRequest) -> dict[str, Any]:
        result = get_builder().iterate_team(request.team, request.report, format=request.format)
        payload = _result_payload(result)
        history.append(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "action": "iterate",
                "format": request.format,
                "valid": payload["valid"],
                "team_name": payload["team"].get("name"),
            }
        )
        return payload

    @router.get("/history")
    def get_history() -> dict[str, Any]:
        return {"history": list(history[-_HISTORY_LIMIT:])}

    return router
