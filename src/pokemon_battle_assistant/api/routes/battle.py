"""Battle API：后台启动单局 Agent 对战并查询状态/结果。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ..jobs import JobRegistry
from ...translation import translate_move, translate_pokemon

KIND_ZH_NAMES = {"move": "招式", "switch": "换人", "order": "指令"}


class BattleStartRequest(BaseModel):
    template: str
    opponent: str | None = None
    format: str | None = None
    opponent_control: str = "random"
    backend: str | None = None
    model: str | None = None


def _first_species(slot: Any) -> str | None:
    """从 active_pokemon 槽位取第一只在场宝可梦的名字。"""
    if isinstance(slot, list):
        first = next((item for item in slot if isinstance(item, dict)), None)
    else:
        first = slot
    if isinstance(first, dict) and first.get("species"):
        return str(first["species"])
    return None


def _translate_move_label(label: str) -> str:
    """翻译招式标签；标签可能带目标后缀（如 'heatwave -1'）。"""
    parts = label.split()
    if not parts:
        return label
    rest = " ".join(parts[1:])
    return translate_move(parts[0]) + (f" {rest}" if rest else "")


def _translate_order_segment(segment: str) -> str:
    seg = segment.strip().removeprefix("/choose").strip()
    parts = seg.split()
    if not parts:
        return segment
    head = parts[0].lower()
    rest = parts[1:]
    if head == "move" and rest:
        tail = " ".join(rest[1:])
        return "招式 " + translate_move(rest[0]) + (f" {tail}" if tail else "")
    if head == "switch" and rest:
        return "换上 " + translate_pokemon(" ".join(rest))
    if head == "team" and rest:
        return "选择出场顺序 " + " ".join(rest)
    return segment


def _translate_order_label(text: str) -> str:
    """双打组合指令（含逗号）逐段翻译后用中文逗号连接。"""
    return "，".join(_translate_order_segment(seg) for seg in text.split(","))


def _translate_chosen_action(action: dict[str, Any]) -> tuple[str, str] | None:
    """把 chosen_action 转成 (kind_zh, label_zh)；无法识别时返回 None。"""
    kind = action.get("kind")
    label = str(action.get("label") or "")
    command = str(action.get("command") or "")
    if kind == "move":
        return KIND_ZH_NAMES["move"], _translate_move_label(label)
    if kind == "switch":
        return KIND_ZH_NAMES["switch"], "换上 " + translate_pokemon(label)
    if command.startswith("/team"):
        return "选队", "选择出场顺序 " + command.removeprefix("/team").strip()
    return KIND_ZH_NAMES["order"], _translate_order_label(command or label)


def build_turn_log(record: dict[str, Any]) -> list[dict[str, Any]]:
    """从对战记录的 steps 生成逐回合中文出招时间线。"""
    log: list[dict[str, Any]] = []
    for step in record.get("steps") or []:
        action = step.get("chosen_action")
        if not isinstance(action, dict):
            continue
        translated = _translate_chosen_action(action)
        if translated is None:
            continue
        kind_zh, label_zh = translated
        observation = step.get("observation") or {}
        active = _first_species(observation.get("active_pokemon"))
        opponent_active = _first_species(observation.get("opponent_active_pokemon"))
        log.append(
            {
                "turn": step.get("turn"),
                "side": "己方" if step.get("player") == "player_1" else "对手",
                "kind_zh": kind_zh,
                "label_zh": label_zh,
                "active_zh": translate_pokemon(active) if active else None,
                "opponent_active_zh": translate_pokemon(opponent_active) if opponent_active else None,
            }
        )
    return log


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
        "turn_log": build_turn_log(result.record),
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
