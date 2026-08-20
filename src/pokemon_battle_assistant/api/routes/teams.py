"""队伍 API：查询（JOIN dex 全中文）+ 管理（导入/调整/删除）。"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...team_builder import importer, repository as team_repo, validator
from ...skills.team_building import skill as skill_pkg

ROOT = Path(__file__).resolve().parents[4]
TEAMS_DB = ROOT / "data" / "teams" / "teams.db"
DEX_DB = ROOT / "data" / "dex" / "dex.db"

router = APIRouter()

TYPE_ZH = {
    "Normal": "一般", "Fire": "火", "Water": "水", "Electric": "电", "Grass": "草",
    "Ice": "冰", "Fighting": "格斗", "Poison": "毒", "Ground": "地面", "Flying": "飞行",
    "Psychic": "超能力", "Bug": "虫", "Rock": "岩石", "Ghost": "幽灵", "Dragon": "龙",
    "Dark": "恶", "Steel": "钢", "Fairy": "妖精",
}
FORMAT_ZH = {
    "gen9bssregi": "BSS（6选3单打 Lv50）",
    "gen9vgc2026regi": "VGC（6选4双打 Lv50）",
    "gen9ou": "OU（6v6 单打 Lv100）",
}
SOURCE_ZH = {"preset": "预设", "ai": "AI 生成", "manual": "手工"}

_SKILL_VERSION = "v1"


def _migrate() -> None:
    """启动时幂等补列：team_members.stat_reason（repository 写路径同样兜底）。"""
    try:
        conn = sqlite3.connect(TEAMS_DB)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(team_members)")}
        if "stat_reason" not in cols:
            conn.execute("ALTER TABLE team_members ADD COLUMN stat_reason TEXT")
            conn.commit()
        conn.close()
    except sqlite3.Error:
        pass


_migrate()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{TEAMS_DB}?mode=ro", uri=True)
    conn.execute("ATTACH DATABASE ? AS dex", (str(DEX_DB),))
    return conn


@router.get("/teams")
def list_teams():
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT t.id, t.name, t.display_name, t.format, t.source, "
            "t.requirement_prompt, t.created_at, t.updated_at, "
            "(SELECT m.species_id FROM team_members m "
            " WHERE m.team_id = t.id ORDER BY m.slot LIMIT 1) AS ace "
            "FROM teams t ORDER BY t.created_at DESC, t.name"
        ).fetchall()
        return [{
            "id": r[0], "name": r[1], "display_name": r[2],
            "format": r[3], "format_zh": FORMAT_ZH.get(r[3], r[3]),
            "source": r[4], "source_zh": SOURCE_ZH.get(r[4], r[4]),
            "requirement_prompt": r[5], "created_at": r[6], "updated_at": r[7],
            "ace_sprite": r[8],   # 首发位精灵 slug（前端列表/选人预览图）
        } for r in rows]
    finally:
        conn.close()


@router.get("/teams/{name}")
def team_detail(name: str):
    conn = _conn()
    try:
        t = conn.execute(
            "SELECT id, name, display_name, format, source, requirement_prompt, "
            "skill_version, model, export_text, created_at FROM teams WHERE name=?",
            (name,)).fetchone()
        if not t:
            raise HTTPException(404, f"队伍不存在: {name}")

        # 中文渲染所需的映射表
        move_zh = {r[0]: (r[1] or r[2]) for r in conn.execute(
            "SELECT id, name_zh, name_en FROM dex.moves")}

        members = []
        for r in conn.execute(
                "SELECT m.slot, m.species_id, s.name_zh, s.name_en, s.type1, s.type2, "
                "m.level, m.nature, n.name_zh, m.ability, ab.name_zh, "
                "m.item, it.name_zh, it.name_en, m.tera_type, m.moves, m.evs, m.ivs, "
                "m.stat_reason, s.hp, s.atk, s.def, s.spa, s.spd, s.spe, s.bst "
                "FROM team_members m "
                "JOIN dex.species s ON s.id = m.species_id "
                "LEFT JOIN dex.natures n ON n.id = m.nature "
                "LEFT JOIN dex.abilities ab ON ab.id = m.ability "
                "LEFT JOIN dex.items it ON it.id = m.item "
                "WHERE m.team_id = ? ORDER BY m.slot", (t[0],)):
            moves = [{"slug": s, "zh": move_zh.get(s, s)} for s in json.loads(r[15])]
            types = [{"en": x, "zh": TYPE_ZH.get(x, x)}
                     for x in (r[4], r[5]) if x]
            members.append({
                "slot": r[0], "species": r[1],
                "name_zh": r[2] or r[3], "name_en": r[3],
                "types": types, "level": r[6] or 100,
                "nature": r[7], "nature_zh": r[8] or (r[7] or "-"),
                "ability": r[9], "ability_zh": r[10] or r[9] or "-",
                "item": r[11],
                "item_zh": (r[12] or r[13]) if r[11] else None,
                "tera_type": r[14],
                "tera_zh": TYPE_ZH.get(r[14], r[14]) if r[14] else None,
                "moves": moves,
                "evs": json.loads(r[16]) if r[16] else None,
                "ivs": json.loads(r[17]) if r[17] else None,
                "stat_reason": r[18],
                "stats": {"hp": r[19], "atk": r[20], "def": r[21],
                          "spa": r[22], "spd": r[23], "spe": r[24], "bst": r[25]},
            })

        return {
            "id": t[0], "name": t[1], "display_name": t[2],
            "format": t[3], "format_zh": FORMAT_ZH.get(t[3], t[3]),
            "source": t[4], "source_zh": SOURCE_ZH.get(t[4], t[4]),
            "requirement_prompt": t[5], "skill_version": t[6], "model": t[7],
            "export_text": t[8], "created_at": t[9],
            "members": members,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------
# 队伍管理：导入（Showdown 串）/ 调整 / 删除
# ---------------------------------------------------------------

class TeamCreateIn(BaseModel):
    display_name: str
    format: str
    export_text: str


class TeamUpdateIn(BaseModel):
    display_name: str | None = None
    export_text: str | None = None


def _parse_and_validate(export_text: str, format_id: str) -> list[dict]:
    """导出串 → 成员（解析 400 / 赛制校验 422，错误中文可直接展示）。"""
    skill = skill_pkg.load(_SKILL_VERSION)
    try:
        c = skill.constraints(format_id)
    except KeyError as e:
        raise HTTPException(400, str(e))
    try:
        members = importer.parse_paste(export_text, default_level=c["level"])
    except importer.ImportParseError as e:
        raise HTTPException(400, str(e))
    errors = validator.validate(
        {"display_name": "临时队伍", "name_en": "manual_team", "members": members},
        format_id, skill)
    if errors:
        raise HTTPException(422, "校验未通过：\n- " + "\n- ".join(errors))
    return members


@router.post("/teams", status_code=201)
def create_team(body: TeamCreateIn):
    display_name = body.display_name.strip()
    if not display_name:
        raise HTTPException(400, "队伍名不能为空")
    if not body.export_text.strip():
        raise HTTPException(400, "请粘贴 Showdown 队伍导出串")
    members = _parse_and_validate(body.export_text, body.format)
    return team_repo.save_manual_team(display_name, body.format, members)


@router.put("/teams/{name}")
def update_team(name: str, body: TeamUpdateIn):
    members = None
    if body.export_text is not None:
        conn = _conn()
        try:
            row = conn.execute("SELECT format FROM teams WHERE name=?", (name,)).fetchone()
        finally:
            conn.close()
        if not row:
            raise HTTPException(404, f"队伍不存在: {name}")
        members = _parse_and_validate(body.export_text, row[0])
    display_name = (body.display_name or "").strip() or None
    if display_name is None and members is None:
        raise HTTPException(400, "没有要修改的内容")
    if not team_repo.update_team(name, display_name=display_name, members=members):
        raise HTTPException(404, f"队伍不存在: {name}")
    return {"ok": True}


@router.delete("/teams/{name}")
def remove_team(name: str):
    if not team_repo.delete_team(name):
        raise HTTPException(404, f"队伍不存在: {name}")
    return {"ok": True}
