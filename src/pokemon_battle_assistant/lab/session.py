"""批量会话编排：N 轮对战 + 进度更新 + 聚合统计。

流程（docs/module2 思路第 5 节）：
  1. teams.db 取两队 export_text
  2. battles.db 建 session 行（status=running）
  3. 后台线程跑 asyncio：逐轮 run_battle，每轮完更新 rounds_done（前端轮询）
  4. 全部结束：聚合统计（胜率/回合分布/宝可梦贡献/招式热榜）存 session.stats_json，
     status=done（或 failed）
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import runner

ROOT = Path(__file__).resolve().parents[3]
TEAMS_DB = ROOT / "data" / "teams" / "teams.db"
BATTLES_DB = ROOT / "data" / "battles" / "battles.db"


def get_team(name: str) -> dict:
    conn = sqlite3.connect(f"file:{TEAMS_DB}?mode=ro", uri=True)
    try:
        r = conn.execute(
            "SELECT id, name, display_name, export_text, format FROM teams WHERE name=?",
            (name,)).fetchone()
        if not r:
            raise KeyError(f"队伍不存在: {name}")
        return {"id": r[0], "name": r[1], "display_name": r[2] or r[1],
                "export_text": r[3], "format": r[4]}
    finally:
        conn.close()


def create_session(team_a: str, team_b: str, format_id: str, rounds: int) -> str:
    a, b = get_team(team_a), get_team(team_b)
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn = sqlite3.connect(BATTLES_DB)
    try:
        conn.execute(
            "INSERT INTO battle_sessions (id,team_a_id,team_b_id,format,bot_config,"
            "rounds_total,rounds_done,status,started_at) VALUES (?,?,?,?,?,?,?,'running',?)",
            (session_id, a["id"], b["id"], format_id,
             json.dumps({"bot": "simple_heuristics", "side_a": team_a, "side_b": team_b}),
             rounds, 0, now))
        conn.commit()
        return session_id
    finally:
        conn.close()


def start_background(session_id: str, team_a: str, team_b: str, format_id: str,
                     rounds: int, log=print) -> None:
    """起后台线程跑整个会话（API 层调用后立即返回）。"""
    threading.Thread(
        target=_run_session_sync, daemon=True,
        args=(session_id, team_a, team_b, format_id, rounds, log)).start()


def _run_session_sync(session_id, team_a, team_b, format_id, rounds, log) -> None:
    asyncio.run(_run_session(session_id, team_a, team_b, format_id, rounds, log))


async def _run_session(session_id, team_a, team_b, format_id, rounds, log) -> None:
    a, b = get_team(team_a), get_team(team_b)
    log(f"[lab] 会话 {session_id[:8]} 开始：{a['display_name']} vs {b['display_name']} ×{rounds}")
    try:
        for i in range(1, rounds + 1):
            res = await runner.run_battle(session_id, i, format_id, a, b, log=log)
            _update_progress(session_id, i, res)
            log(f"[lab] 第 {i}/{rounds} 场：{'A胜' if res['winner'] == 'a' else 'B胜' if res['winner'] == 'b' else res['winner']}"
                f"（{res['end_turn']} 回合）")
        stats = _aggregate(session_id)
        _finish(session_id, "completed", stats)
        log(f"[lab] 会话完成：{stats['team_a_wins']}-{stats['team_b_wins']}"
            f"（A 胜率 {stats['team_a_win_rate']}%）")
    except Exception as e:
        _finish(session_id, "failed", None, error=str(e))
        log(f"[lab] 会话失败：{e}")
        raise


def _update_progress(session_id: str, done: int, res: dict) -> None:
    conn = sqlite3.connect(BATTLES_DB)
    try:
        conn.execute("UPDATE battle_sessions SET rounds_done=? WHERE id=?",
                     (done, session_id))
        conn.commit()
    finally:
        conn.close()


def _finish(session_id: str, status: str, stats: dict | None, error: str | None = None):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn = sqlite3.connect(BATTLES_DB)
    try:
        conn.execute(
            "UPDATE battle_sessions SET status=?, stats_json=?, error=?, finished_at=? "
            "WHERE id=?",
            (status, json.dumps(stats, ensure_ascii=False) if stats else None,
             error, now, session_id))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- 聚合统计
def _aggregate(session_id: str) -> dict:
    """会话聚合：胜率/回合分布/宝可梦贡献/招式热榜（全部中文渲染好）。"""
    dex = _dex_maps()
    conn = sqlite3.connect(BATTLES_DB)
    conn.row_factory = sqlite3.Row
    try:
        s = conn.execute("SELECT team_a_id, team_b_id, rounds_total FROM battle_sessions "
                         "WHERE id=?", (session_id,)).fetchone()
        wins = dict(conn.execute(
            "SELECT winner, COUNT(*) FROM battles WHERE session_id=? GROUP BY winner",
            (session_id,)).fetchall())

        # 招式热榜（从 battle_turns 聚合）
        moves = conn.execute(
            "SELECT bt.move_id, COUNT(*) n FROM battle_turns bt "
            "JOIN battles b ON b.id = bt.battle_id "
            "WHERE bt.move_id IS NOT NULL AND b.session_id = ? "
            "GROUP BY bt.move_id ORDER BY n DESC LIMIT 10", (session_id,)).fetchall()

        turns_dist = conn.execute(
            "SELECT b.end_turn, COUNT(*) n FROM battles b "
            "WHERE b.session_id=? AND b.winner != 'error' GROUP BY b.end_turn "
            "ORDER BY b.end_turn", (session_id,)).fetchall()

        team_a, team_b, total = s["team_a_id"], s["team_b_id"], s["rounds_total"]
        a_w, b_w = wins.get("a", 0), wins.get("b", 0)
        na, nb = _team_name(team_a), _team_name(team_b)
        return {
            "team_a": team_a, "team_b": team_b,
            "team_a_name": na["name"], "team_b_name": nb["name"],
            "team_a_display": na["display"], "team_b_display": nb["display"],
            "team_a_wins": a_w, "team_b_wins": b_w,
            "draws": wins.get("draw", 0), "errors": wins.get("error", 0),
            "team_a_win_rate": round(a_w / (a_w + b_w) * 100, 1) if (a_w + b_w) else None,
            "avg_turns": (round(sum(r["end_turn"] * r["n"] for r in turns_dist)
                                / sum(r["n"] for r in turns_dist), 1)
                          if any(r["n"] for r in turns_dist) else None),
            "top_moves": [{"move": m[0], "move_zh": dex["moves"].get(m[0], m[0]),
                           "count": m[1]} for m in moves],
        }
    finally:
        conn.close()


def _dex_maps() -> dict:
    dex_db = ROOT / "data" / "dex" / "dex.db"
    conn = sqlite3.connect(f"file:{dex_db}?mode=ro", uri=True)
    try:
        moves = {r[0]: (r[1] or r[2]) for r in
                 conn.execute("SELECT id, name_zh, name_en FROM moves")}
        return {"moves": moves}
    finally:
        conn.close()


def _team_name(team_id: str) -> dict:
    """按 uuid 查队伍名（teams.db 契约：battle_sessions.team_x_id → teams.id）。"""
    conn = sqlite3.connect(f"file:{TEAMS_DB}?mode=ro", uri=True)
    try:
        r = conn.execute("SELECT name, display_name FROM teams WHERE id=?", (team_id,)).fetchone()
        if r:
            return {"name": r[0], "display": r[1] or r[0]}
        return {"name": team_id[:8], "display": team_id[:8]}  # 已删除的队伍：退化为 id 前缀
    finally:
        conn.close()
