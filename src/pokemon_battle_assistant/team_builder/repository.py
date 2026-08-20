"""阶段5 repository：合法队伍 → teams.db（落实写入契约，docs/teams_db_schema.md）。

契约五条：
  1. id = uuid4
  2. name = name_en slug 化，冲突自动加 -2/-3 后缀（不覆盖已有队伍）
  3. 成员 slug 已过 validator 闸门，同事务写 teams + team_members
  4. export_text 与结构化数据同事务生成
  5. 溯源字段齐全：source='ai' / requirement_prompt / skill_version / model
"""
from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .planner import slugify as _dex_slug

ROOT = Path(__file__).resolve().parents[3]
TEAMS_DB = ROOT / "data" / "teams" / "teams.db"

STAT_LABEL = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """轻量迁移：旧库补 stat_reason 列（幂等）。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(team_members)")}
    if "stat_reason" not in cols:
        conn.execute("ALTER TABLE team_members ADD COLUMN stat_reason TEXT")
        conn.commit()


def _insert_members(conn: sqlite3.Connection, team_id: str, members: list[dict]) -> None:
    for i, m in enumerate(members, 1):
        conn.execute(
            "INSERT INTO team_members (team_id,slot,species_id,level,nature,ability,"
            "item,tera_type,moves,evs,ivs,stat_reason) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (team_id, i, m["species"], m.get("level", 100),
             m.get("nature"), m.get("ability"), m.get("item"),
             m.get("tera_type"),
             json.dumps(list(m.get("moves", []))),
             json.dumps(_full_stats(m.get("evs"), 0)),
             json.dumps(_full_stats(m.get("ivs"), 31)),
             m.get("stat_reason")))


def _team_name_slug(name: str) -> str:
    """队伍文件 ID：小写英文+下划线（与 dex slug 规则不同，保留下划线）。"""
    s = re.sub(r"[^a-z0-9_]", "", name.lower().replace(" ", "_"))
    return s or f"team_{uuid.uuid4().hex[:6]}"


def _full_stats(partial: dict | None, default: int) -> dict:
    return {k: int((partial or {}).get(k, default)) for k in STAT_LABEL}


def _member_export(m: dict, level_rule: int) -> str:
    """结构化成员 → Showdown 导出块（与 build_teams_db.py 同规则）。"""
    lines = [m["species"]]
    # 物种行带道具（item 可能是 None/缺失）
    item = m.get("item")
    if item:
        lines[0] = f"{m['species']} @ {item}"
    if m.get("ability"):
        lines.append(f"Ability: {m['ability']}")
    level = m.get("level", level_rule)
    if level != 100:
        lines.append(f"Level: {level}")
    if m.get("tera_type"):
        lines.append(f"Tera Type: {m['tera_type']}")
    evs = _full_stats(m.get("evs"), 0)
    parts = [f"{evs[k]} {STAT_LABEL[k]}" for k in STAT_LABEL if evs[k]]
    if parts:
        lines.append("EVs: " + " / ".join(parts))
    if m.get("nature"):
        lines.append(f"{m['nature'].title()} Nature")
    ivs = _full_stats(m.get("ivs"), 31)
    parts = [f"{ivs[k]} {STAT_LABEL[k]}" for k in STAT_LABEL if ivs[k] != 31]
    if parts:
        lines.append("IVs: " + " / ".join(parts))
    for mv in m.get("moves", []):
        lines.append(f"- {mv}")
    return "\n".join(lines)


def _unique_name(conn: sqlite3.Connection, base: str) -> str:
    name, n = base, 1
    while conn.execute("SELECT 1 FROM teams WHERE name=?", (name,)).fetchone():
        n += 1
        name = f"{base}-{n}"
    return name


def save_team(team: dict, *, format_id: str, requirement: str,
              skill_version: str, model: str) -> dict:
    """写入 teams.db，返回 {id, name, display_name}。"""
    conn = sqlite3.connect(TEAMS_DB)
    try:
        _ensure_columns(conn)
        name = _unique_name(conn, _team_name_slug(team["name_en"]))
        team_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        level_rule = 100  # 仅用于 export_text 缺省等级；实际等级以成员值为准
        export = "\n\n".join(_member_export(m, level_rule) for m in team["members"])

        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO teams (id,name,display_name,format,source,requirement_prompt,"
            "skill_version,model,export_text,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (team_id, name, team["display_name"], format_id, "ai", requirement,
             skill_version, model, export, now, now))
        _insert_members(conn, team_id, team["members"])
        conn.commit()
        return {"id": team_id, "name": name, "display_name": team["display_name"]}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def save_manual_team(display_name: str, format_id: str, members: list[dict]) -> dict:
    """手工导入（Showdown 串解析后已过校验的成员）入库，source='manual'。"""
    conn = sqlite3.connect(TEAMS_DB)
    try:
        _ensure_columns(conn)
        name = _unique_name(conn, _team_name_slug(f"custom_{uuid.uuid4().hex[:6]}"))
        team_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        export = "\n\n".join(_member_export(m, 100) for m in members)

        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO teams (id,name,display_name,format,source,requirement_prompt,"
            "skill_version,model,export_text,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (team_id, name, display_name, format_id, "manual", None,
             None, None, export, now, now))
        _insert_members(conn, team_id, members)
        conn.commit()
        return {"id": team_id, "name": name, "display_name": display_name}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_team(team_name: str, *, display_name: str | None = None,
                members: list[dict] | None = None) -> bool:
    """调整队伍：改名 和/或 整体替换成员（成员需已过校验）。不存在返回 False。"""
    conn = sqlite3.connect(TEAMS_DB)
    try:
        _ensure_columns(conn)
        row = conn.execute("SELECT id FROM teams WHERE name=?", (team_name,)).fetchone()
        if not row:
            return False
        team_id = row[0]
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        conn.execute("BEGIN")
        if display_name:
            conn.execute("UPDATE teams SET display_name=?, updated_at=? WHERE id=?",
                         (display_name, now, team_id))
        if members is not None:
            export = "\n\n".join(_member_export(m, 100) for m in members)
            conn.execute("UPDATE teams SET export_text=?, updated_at=? WHERE id=?",
                         (export, now, team_id))
            conn.execute("DELETE FROM team_members WHERE team_id=?", (team_id,))
            _insert_members(conn, team_id, members)
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_team(team_name: str) -> bool:
    """删除队伍及其成员。不存在返回 False。"""
    conn = sqlite3.connect(TEAMS_DB)
    try:
        row = conn.execute("SELECT id FROM teams WHERE name=?", (team_name,)).fetchone()
        if not row:
            return False
        conn.execute("BEGIN")
        conn.execute("DELETE FROM team_members WHERE team_id=?", (row[0],))
        conn.execute("DELETE FROM teams WHERE id=?", (row[0],))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
