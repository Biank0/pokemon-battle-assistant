"""首页总览 API：GET /api/overview 聚合跨库统计。

一个请求拼好首页看板所需全部数据（避免前端连发 4 个请求）：
- 队伍总数 / 最近 AI 建队
- 对战场次总数 / 最近完成会话（含比分与胜率）
- 分析报告数 / 最近报告标题
- 图中鉴宝可梦总数（供图鉴感展示）
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter

from .lab import _team_ace

ROOT = Path(__file__).resolve().parents[4]
TEAMS_DB = ROOT / "data" / "teams" / "teams.db"
BATTLES_DB = ROOT / "data" / "battles" / "battles.db"
ANALYSIS_DB = ROOT / "data" / "analysis" / "analysis.db"
DEX_DB = ROOT / "data" / "dex" / "dex.db"

router = APIRouter()


def _ro(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/overview")
def overview():
    out: dict = {}

    # ---- 队伍 ----
    conn = _ro(TEAMS_DB)
    total = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    latest = conn.execute(
        "SELECT display_name, name, source, created_at FROM teams "
        "ORDER BY created_at DESC LIMIT 1").fetchone()
    conn.close()
    out["teams"] = {
        "total": total,
        "latest": dict(latest) if latest else None,
    }

    # ---- 对战 ----
    conn = _ro(BATTLES_DB)
    battles_total = conn.execute("SELECT COUNT(*) FROM battles").fetchone()[0]
    sess = conn.execute(
        "SELECT id, format, rounds_done, rounds_total, stats_json, "
        "team_a_id, team_b_id "
        "FROM battle_sessions WHERE status='completed' "
        "ORDER BY finished_at DESC LIMIT 1").fetchone()
    conn.close()
    out["battles"] = {"total": battles_total, "latest_session": None}
    if sess:
        s = dict(sess)
        team_a_id, team_b_id = s.pop("team_a_id"), s.pop("team_b_id")
        stats = json.loads(s.pop("stats_json") or "{}")
        out["battles"]["latest_session"] = {
            **s,
            # 队伍显示名/比分在 stats_json（与 lab 会话接口同源）
            "team_a": stats.get("team_a_display", "A 队"),
            "team_b": stats.get("team_b_display", "B 队"),
            "score": f"{stats.get('team_a_wins', 0)}:{stats.get('team_b_wins', 0)}",
            "team_a_win_rate": stats.get("team_a_win_rate", 0),
            # 两队首发位精灵 slug（首页迷你对阵图）
            "team_a_sprite": _team_ace(team_a_id),
            "team_b_sprite": _team_ace(team_b_id),
        }

    # ---- 分析报告 ----
    conn = _ro(ANALYSIS_DB)
    atotal = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    la = conn.execute(
        "SELECT id, title, rating, created_at FROM analyses "
        "ORDER BY created_at DESC LIMIT 1").fetchone()
    conn.close()
    out["analyses"] = {"total": atotal, "latest": dict(la) if la else None}

    # ---- 图鉴 ----
    conn = _ro(DEX_DB)
    out["dex_species"] = conn.execute("SELECT COUNT(*) FROM species").fetchone()[0]
    conn.close()

    # ---- 随机“遭遇”（首页 Hero：从队伍在册物种抽一只，保证本地有图） ----
    conn = _ro(TEAMS_DB)
    row = conn.execute(
        "SELECT species_id FROM team_members GROUP BY species_id "
        "ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close()
    featured = None
    if row:
        conn = _ro(DEX_DB)
        zh = conn.execute(
            "SELECT name_zh, name_en FROM species WHERE id=?",
            (row[0],)).fetchone()
        conn.close()
        featured = {"slug": row[0],
                    "name_zh": (zh[0] or zh[1]) if zh else row[0]}
    out["featured"] = featured
    return out
