"""Analysis API：提交对战深度复盘并获取结果。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class AnalysisStartRequest(BaseModel):
    depth: str = "full"
    record: dict[str, Any] | None = None


def create_analysis_router(engine_provider: Callable[[], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/analysis", tags=["analysis"])

    @router.post("/battle/{battle_tag}")
    async def analyze(battle_tag: str, request: AnalysisStartRequest) -> dict[str, Any]:
        engine = engine_provider()
        analysis_id = await engine.analyze_battle(battle_tag, request.depth, record=request.record)
        return engine.get_result(analysis_id).to_dict()

    @router.get("/list")
    def list_analyses() -> dict[str, Any]:
        engine = engine_provider()
        try:
            analyses = list(engine.list_analyses())
        except AttributeError:
            analyses = []
        return {"analyses": analyses}

    @router.get("/{analysis_id}")
    def get_analysis(analysis_id: str) -> dict[str, Any]:
        engine = engine_provider()
        try:
            report = engine.get_result(analysis_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"分析结果不存在：{analysis_id}") from None
        return report.to_dict()

    return router
