"""对战实验室 API。

  POST /api/lab/start          发起跑量会话（后台线程，立即返回 session_id）
  GET  /api/lab/sessions       历史会话列表
  GET  /api/lab/session/{id}   会话进度 + 逐场结果 + 聚合统计（前端 1.5s 轮询）
  GET  /api/lab/battle/{id}    单场逐回合明细（中文渲染，JOIN dex）
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...lab import session as session_mod

ROOT = Path(__file__).resolve().parents[4]
BATTLES_DB = ROOT / "data" / "battles" / "battles.db"
DEX_DB = ROOT / "data" / "dex" / "dex.db"

router = APIRouter(prefix="/lab", tags=["lab"])

# 第一期实验室仅支持单打（VGC 双打的采集与决策路径未适配，实测会卡死）
SUPPORTED_FORMATS = {"gen9bssregi", "gen9ou"}


class LabStartRequest(BaseModel):
    team_a: str
    team_b: str
    format: str = "gen9bssregi"
    rounds: int = Field(default=10, ge=1, le=200)


@router.post("/start")
def start_lab(req: LabStartRequest):
    # 赛制白名单：第一期仅单打
    if req.format not in SUPPORTED_FORMATS:
        raise HTTPException(400, (
            f"对战赛制 {req.format} 暂不支持：实验室第一期仅支持单打"
            f"（gen9bssregi / gen9ou）"))
    # 赛制一致性校验：两队 format 必须与对战赛制一致（拒队风险前置暴露）
    try:
        for side in ("team_a", "team_b"):
            t = session_mod.get_team(getattr(req, side))
            if t.get("format") and t["format"] != req.format:
                raise HTTPException(400, (
                    f"{t['display_name']} 的赛制是 {t['format']}，与对战赛制 {req.format} "
                    f"不一致，会被服务器拒队"))
    except KeyError as e:
        raise HTTPException(404, str(e))
    session_id = session_mod.create_session(req.team_a, req.team_b, req.format, req.rounds)
    session_mod.start_background(session_id, req.team_a, req.team_b,
                                 req.format, req.rounds, log=_noop)
    return {"session_id": session_id}


@router.get("/sessions")
def list_sessions():
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT id, team_a_id, team_b_id, format, rounds_total, rounds_done, "
            "status, started_at, finished_at, stats_json FROM battle_sessions "
            "ORDER BY started_at DESC LIMIT 50").fetchall()
        out = []
        for r in rows:
            item = {
                "id": r[0], "format": r[3], "rounds_total": r[4], "rounds_done": r[5],
                "status": r[6], "started_at": r[7], "finished_at": r[8],
            }
            if r[9]:
                try:
                    stats = json.loads(r[9])
                    item["summary"] = {
                        "team_a_display": stats.get("team_a_display"),
                        "team_b_display": stats.get("team_b_display"),
                        "team_a_wins": stats.get("team_a_wins"),
                        "team_b_wins": stats.get("team_b_wins"),
                    }
                except json.JSONDecodeError:
                    pass
            out.append(item)
        return {"sessions": out}
    finally:
        conn.close()


@router.get("/session/{session_id}")
def get_session(session_id: str):
    conn = _db()
    try:
        r = conn.execute(
            "SELECT id, team_a_id, team_b_id, format, rounds_total, rounds_done, "
            "status, error, started_at, finished_at, stats_json "
            "FROM battle_sessions WHERE id=?", (session_id,)).fetchone()
        if not r:
            raise HTTPException(404, "会话不存在")
        battles = conn.execute(
            "SELECT id, round_no, winner, end_turn FROM battles "
            "WHERE session_id=? ORDER BY round_no", (session_id,)).fetchall()
        return {
            "id": r[0], "format": r[3], "rounds_total": r[4], "rounds_done": r[5],
            "status": r[6], "error": r[7], "started_at": r[8], "finished_at": r[9],
            "stats": json.loads(r[10]) if r[10] else None,
            "battles": [{"id": b[0], "round_no": b[1], "winner": b[2],
                         "end_turn": b[3]} for b in battles],
        }
    finally:
        conn.close()


@router.get("/battle/{battle_id}")
def get_battle(battle_id: str):
    """单场逐回合明细（中文渲染：宝可梦/招式 JOIN dex）。"""
    zh = _zh_maps()
    conn = _db()
    try:
        r = conn.execute(
            "SELECT b.id, b.session_id, b.round_no, b.winner, b.end_turn, b.battle_tag "
            "FROM battles b WHERE b.id=?", (battle_id,)).fetchone()
        if not r:
            raise HTTPException(404, "对战不存在")
        turns = conn.execute(
            "SELECT turn, side, action_type, actor_species, move_id, target_species "
            "FROM battle_turns WHERE battle_id=? ORDER BY id", (battle_id,)).fetchall()
        s = conn.execute(
            "SELECT team_a_id, team_b_id FROM battle_sessions WHERE id=?",
            (r[1],)).fetchone()
        return {
            "id": r[0], "session_id": r[1], "round_no": r[2], "winner": r[3],
            "end_turn": r[4], "battle_tag": r[5],
            "team_a": _team_display(s[0]) if s else None,
            "team_b": _team_display(s[1]) if s else None,
            "turns": [{
                "turn": t[0], "side": t[1], "action_type": t[2],
                "actor_zh": zh["species"].get(t[3], t[3]),
                "move_zh": zh["moves"].get(t[4], t[4]) if t[4] else None,
                "target_zh": zh["species"].get(t[5], t[5]) if t[5] else None,
                "actor": t[3], "move": t[4], "target": t[5],
            } for t in turns],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------- helpers
def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{BATTLES_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _zh_maps() -> dict:
    conn = sqlite3.connect(f"file:{DEX_DB}?mode=ro", uri=True)
    try:
        species = {r[0]: (r[1] or r[2]) for r in conn.execute(
            "SELECT id, name_zh, name_en FROM species")}
        moves = {r[0]: (r[1] or r[2]) for r in conn.execute(
            "SELECT id, name_zh, name_en FROM moves")}
        return {"species": species, "moves": moves}
    finally:
        conn.close()


def _team_display(team_id: str) -> str:
    from ...lab.session import _team_name
    return _team_name(team_id)["display"]


def _noop(*_a, **_kw) -> None:
    """后台线程日志丢弃（进度靠轮询库，不需要流式日志）。"""
