"""FastAPI 应用工厂：组装 teams / team-builder / battle / lab / analysis / orchestrator 路由。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .jobs import JobRegistry
from .routes.analysis import create_analysis_router
from .routes.battle import create_battle_router
from .routes.lab import create_lab_router
from .routes.orchestrator import create_orchestrator_router
from .routes.team_builder import create_team_builder_router
from .routes.teams import TeamsStore, create_teams_router

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TRAINERS_DIR = PROJECT_ROOT / "data" / "trainers"

SUPPORTED_FORMATS = [
    {
        "id": "gen9bssregi",
        "name": "BSS Regulation I（6选3单打）",
        "game_type": "singles",
        "picked_team_size": 3,
    },
    {
        "id": "gen9vgc2026regi",
        "name": "VGC 2026 Regulation I（6选4双打）",
        "game_type": "doubles",
        "picked_team_size": 4,
    },
    {"id": "gen9randombattle", "name": "Gen9 随机对战", "game_type": "singles", "picked_team_size": None},
    {
        "id": "gen9randomdoublesbattle",
        "name": "Gen9 随机双打",
        "game_type": "doubles",
        "picked_team_size": None,
    },
]


def create_app(
    *,
    llm: Any | None = None,
    team_builder: Any | None = None,
    lab_runner: Any | None = None,
    analysis_engine: Any | None = None,
    orchestrator: Any | None = None,
    battle_runner: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
    trainers_dir: Path | str | None = None,
    battle_output_root: str = "battle_outputs",
) -> FastAPI:
    """创建 FastAPI 应用；重依赖全部可注入，测试传 fake，生产延迟构建。"""
    app = FastAPI(
        title="Pokemon Battle Assistant API",
        version="0.1.0",
        description="宝可梦对战助手：建队 / 对战 / 批量模拟 / 深度复盘 / 闭环迭代",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    registry = JobRegistry()
    app.state.jobs = registry

    llm_holder: dict[str, Any] = {"llm": llm}

    def _get_llm() -> Any:
        if llm_holder["llm"] is None:
            from ..agent.llm_client import LLMClient

            llm_holder["llm"] = LLMClient()
        return llm_holder["llm"]

    builder_holder: dict[str, Any] = {"builder": team_builder}

    def _get_builder() -> Any:
        if builder_holder["builder"] is None:
            from ..modules.team_builder.agent import TeamBuilderAgent

            builder_holder["builder"] = TeamBuilderAgent(llm=_get_llm())
        return builder_holder["builder"]

    lab_holder: dict[str, Any] = {"runner": lab_runner}

    def _get_lab_runner() -> Any:
        if lab_holder["runner"] is None:
            from ..modules.lab.runner import LabRunner

            lab_holder["runner"] = LabRunner()
        return lab_holder["runner"]

    analysis_holder: dict[str, Any] = {"engine": analysis_engine}

    def _get_analysis_engine() -> Any:
        if analysis_holder["engine"] is None:
            from ..modules.analysis.engine import AnalysisEngine

            analysis_holder["engine"] = AnalysisEngine(llm=_get_llm())
        return analysis_holder["engine"]

    orchestrator_holder: dict[str, Any] = {"orchestrator": orchestrator}

    def _get_orchestrator() -> Any:
        if orchestrator_holder["orchestrator"] is None:
            from ..modules.orchestrator import Orchestrator

            orchestrator_holder["orchestrator"] = Orchestrator(
                llm=_get_llm(),
                team_builder=_get_builder(),
                lab_runner=_get_lab_runner(),
                analysis_engine=_get_analysis_engine(),
            )
        return orchestrator_holder["orchestrator"]

    store = TeamsStore(trainers_dir or DEFAULT_TRAINERS_DIR)

    @app.get("/api/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "pokemon-battle-assistant"}

    @app.get("/api/formats", tags=["meta"])
    def formats() -> dict[str, Any]:
        return {"formats": SUPPORTED_FORMATS}

    app.include_router(create_teams_router(store))
    app.include_router(create_team_builder_router(_get_builder))
    app.include_router(create_battle_router(registry, battle_runner=battle_runner, battle_output_root=battle_output_root))
    app.include_router(create_lab_router(registry, lab_runner_provider=_get_lab_runner))
    app.include_router(create_analysis_router(_get_analysis_engine))
    app.include_router(create_orchestrator_router(registry, orchestrator_provider=_get_orchestrator))

    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """托管 frontend/ 下的免构建静态资源（SPA，history 路由回退到 index.html）。"""
    frontend = PROJECT_ROOT / "frontend"
    index = frontend / "index.html"
    if not index.is_file():
        return

    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    for sub in ("vendor", "js", "css"):
        directory = frontend / sub
        if directory.is_dir():
            app.mount(f"/{sub}", StaticFiles(directory=directory), name=sub)

    @app.get("/", include_in_schema=False)
    def spa_root() -> FileResponse:
        return FileResponse(index)

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        candidate = frontend / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


app = create_app()
