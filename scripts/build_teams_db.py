#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建 teams.db —— 队伍库（可写活库）的初始化 + 种子导入

与 build_dex_db.py（整库重建）不同，本脚本管理的是累积式活库：
  1. 库不存在        → 建表 + 导入全部 JSON 种子
  2. 库已存在        → 增量补种（name 已存在的队伍跳过，不动库内数据）
  3. --rebuild 参数   → 删库重建（仅开发期使用，AI 生成数据会丢失）

种子来源：
  data/teams/lab/*.json        → source='preset'（实验室预设）
  data/teams/generated/*.json  → source='ai'（旧系统 AI 生成）

用法：
  python scripts/build_teams_db.py             # 初始化/增量补种
  python scripts/build_teams_db.py --rebuild   # 删库重建
"""
import json
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEAMS_DIR = ROOT / "data" / "teams"
DB_PATH = TEAMS_DIR / "teams.db"
SCHEMA_PATH = TEAMS_DIR / "schema.sql"
DEX_DB = ROOT / "data" / "dex" / "dex.db"

SCHEMA_VERSION = "1"

TYPES_18 = {
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
}

STAT_ORDER = ["hp", "atk", "def", "spa", "spd", "spe"]
STAT_LABEL = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}


def to_slug(name: str) -> str:
    """显示名 → dex 官方 slug：小写 + 去掉所有非字母数字字符。

    Will-O-Wisp → willowisp；Lilligant-Hisui → lilliganthisui；Heavy-Duty Boots → heavydutyboots
    """
    return re.sub(r"[^a-z0-9]", "", name.lower())


def member_export(m: dict) -> str:
    """单个成员 → Showdown 导出块"""
    lines = [f"{m['species']} @ {m['item']}" if m.get("item") else m["species"]]
    if m.get("ability"):
        lines.append(f"Ability: {m['ability']}")
    if m.get("level") and m["level"] != 100:
        lines.append(f"Level: {m['level']}")
    if m.get("tera_type"):
        lines.append(f"Tera Type: {m['tera_type']}")
    evs = m.get("evs") or {}
    parts = [f"{evs[k]} {STAT_LABEL[k]}" for k in STAT_ORDER if evs.get(k)]
    if parts:
        lines.append("EVs: " + " / ".join(parts))
    if m.get("nature"):
        lines.append(f"{m['nature']} Nature")
    ivs = m.get("ivs") or {}
    parts = [f"{ivs[k]} {STAT_LABEL[k]}" for k in STAT_ORDER if k in ivs and ivs[k] != 31]
    if parts:
        lines.append("IVs: " + " / ".join(parts))
    for mv in m.get("moves", []):
        lines.append(f"- {mv}")
    return "\n".join(lines)


def team_export(members: list[dict]) -> str:
    return "\n\n".join(member_export(m) for m in members)


def load_dex_index() -> dict:
    """从 dex.db 读出全部合法 id 集合，供种子校验"""
    conn = sqlite3.connect(f"file:{DEX_DB}?mode=ro", uri=True)
    sets = {}
    for table in ("species", "moves", "abilities", "items", "natures"):
        sets[table] = {r[0] for r in conn.execute(f"SELECT id FROM {table}")}
    ver = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
    conn.close()
    sets["dex_schema_version"] = ver[0] if ver else "unknown"
    return sets


def validate_members(team_name: str, members: list[dict], dex: dict, warnings: list) -> None:
    """成员 slug 与 dex 逐一比对，解析失败记警告（不阻断导入）"""
    for i, m in enumerate(members, 1):
        where = f"[{team_name}] 槽位{i}"
        sp = to_slug(m["species"])
        if sp not in dex["species"]:
            warnings.append(f"{where} 物种无法解析: {m['species']!r} -> {sp}")
        for mv in m.get("moves", []):
            s = to_slug(mv)
            if s not in dex["moves"]:
                warnings.append(f"{where} 招式无法解析: {mv!r} -> {s}")
        if m.get("ability") and to_slug(m["ability"]) not in dex["abilities"]:
            warnings.append(f"{where} 特性无法解析: {m['ability']!r}")
        if m.get("item") and to_slug(m["item"]) not in dex["items"]:
            warnings.append(f"{where} 道具无法解析: {m['item']!r}")
        if m.get("nature") and to_slug(m["nature"]) not in dex["natures"]:
            warnings.append(f"{where} 性格无法解析: {m['nature']!r}")
        if m.get("tera_type") and m["tera_type"] not in TYPES_18:
            warnings.append(f"{where} 太晶属性非法: {m['tera_type']!r}")


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    rebuild = "--rebuild" in sys.argv

    if not DEX_DB.exists():
        print(f"[错误] 依赖 dex.db 不存在，请先运行 scripts/build_dex_db.py")
        return 1
    if not SCHEMA_PATH.exists():
        print(f"[错误] 缺少 schema 文件: {SCHEMA_PATH}")
        return 1

    dex = load_dex_index()
    print(f"[依赖] dex.db 就绪 (schema v{dex['dex_schema_version']}, "
          f"species={len(dex['species'])} moves={len(dex['moves'])})")

    # ---------- 建库 / 重建 ----------
    if DB_PATH.exists() and rebuild:
        print(f"[重建] 删除已有 {DB_PATH}")
        DB_PATH.unlink()
    existed = DB_PATH.exists()

    conn = sqlite3.connect(DB_PATH)
    if not existed:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        print(f"[建库] {DB_PATH} 已创建")
    else:
        print(f"[增量] {DB_PATH} 已存在，按 name 去重补种")

    # ---------- 种子导入 ----------
    warnings: list[str] = []
    imported, skipped = 0, 0
    for subdir, source in (("lab", "preset"), ("generated", "ai")):
        d = TEAMS_DIR / subdir
        if not d.exists():
            continue
        for jf in sorted(d.glob("*.json")):
            data = json.loads(jf.read_text(encoding="utf-8"))
            # name 用文件名 slug（稳定英文 ID，跨文件系统唯一）；
            # JSON 内 name 字段是英文显示名（如 'BSS Balance'），不参与标识
            name = jf.stem
            display = data.get("display_name") or data.get("name") or name
            fmt = data.get("format") or "gen9ou"
            members = data.get("team", [])
            ts = datetime.fromtimestamp(jf.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")

            validate_members(name, members, dex, warnings)

            team_id = str(uuid.uuid4())
            cur = conn.execute(
                "INSERT OR IGNORE INTO teams "
                "(id,name,display_name,format,source,requirement_prompt,skill_version,model,"
                "export_text,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (team_id, name, display, fmt, source, None, None, None,
                 team_export(members), ts, ts),
            )
            if cur.rowcount == 0:
                skipped += 1
                continue

            for i, m in enumerate(members, 1):
                conn.execute(
                    "INSERT INTO team_members "
                    "(team_id,slot,species_id,level,nature,ability,item,tera_type,moves,evs,ivs) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        team_id, i, to_slug(m["species"]), m.get("level", 100),
                        to_slug(m["nature"]) if m.get("nature") else None,
                        to_slug(m["ability"]) if m.get("ability") else None,
                        to_slug(m["item"]) if m.get("item") else None,
                        m.get("tera_type"),
                        json.dumps([to_slug(x) for x in m.get("moves", [])]),
                        json.dumps(m.get("evs")) if m.get("evs") else None,
                        json.dumps(m.get("ivs")) if m.get("ivs") else None,
                    ),
                )
            imported += 1

    conn.execute(
        "INSERT OR REPLACE INTO meta (key,value) VALUES ('schema_version',?)", (SCHEMA_VERSION,))
    conn.execute(
        "INSERT OR REPLACE INTO meta (key,value) VALUES ('dex_schema_version',?)",
        (dex["dex_schema_version"],))
    conn.execute(
        "INSERT OR REPLACE INTO meta (key,value) VALUES ('seeded_at',?)",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"),))
    conn.commit()

    # ---------- 校验 ----------
    print("\n========== 导入结果 ==========")
    print(f"  新导入 {imported} 支 / 跳过已存在 {skipped} 支")
    for row in conn.execute(
            "SELECT source, COUNT(*) FROM teams GROUP BY source ORDER BY source"):
        print(f"  teams[{row[0]:<6}] {row[1]} 支")
    print(f"  team_members    {conn.execute('SELECT COUNT(*) FROM team_members').fetchone()[0]} 行")

    if warnings:
        print(f"\n---------- 警告 {len(warnings)} 条 ----------")
        for w in warnings:
            print(f"  {w}")
    else:
        print("\n---------- dex 校验 ----------\n  全部 slug 解析通过，无警告")

    # ---------- 跨库 JOIN 演示：全中文渲染一支队伍 ----------
    print("\n---------- 中文渲染示例（ATTACH dex 跨库 JOIN）----------")
    conn.execute("ATTACH DATABASE ? AS dex", (str(DEX_DB),))
    row = conn.execute("SELECT display_name,format,source FROM teams WHERE name='xiaobian'").fetchone()
    if row:
        print(f"  [{row[0]}] {row[1]} · {row[2]}")
        # 招式中文名映射
        move_zh = {r[0]: (r[1] or r[2]) for r in conn.execute(
            "SELECT id,name_zh,name_en FROM dex.moves")}
        for r in conn.execute(
                "SELECT m.slot, s.name_zh, s.name_en, s.type1, s.type2, m.level, "
                "n.name_zh, ab.name_zh, ab.name_en, it.name_zh, it.name_en, m.tera_type, m.moves "
                "FROM team_members m "
                "JOIN dex.species s ON s.id=m.species_id "
                "LEFT JOIN dex.natures n ON n.id=m.nature "
                "LEFT JOIN dex.abilities ab ON ab.id=m.ability "
                "LEFT JOIN dex.items it ON it.id=m.item "
                "WHERE m.team_id=(SELECT id FROM teams WHERE name='xiaobian') "
                "ORDER BY m.slot"):
            sp_disp = r[1] or r[2]
            ab_disp = r[7] or r[8] or "未指定"
            item_disp = r[9] or r[10] or "无道具"
            moves_zh = " / ".join(move_zh.get(s, s) for s in json.loads(r[12]))
            print(f"    #{r[0]} {sp_disp} Lv{r[5]} ｜ {r[3]}{'/'+r[4] if r[4] else ''}"
                  f" ｜ 性格 {r[6]} ｜ 特性 {ab_disp} ｜ 道具 {item_disp} ｜ 太晶 {r[11]}")
            print(f"       招式：{moves_zh}")

    # export_text 抽样
    et = conn.execute("SELECT export_text FROM teams WHERE name='xiaobian'").fetchone()
    if et:
        print("\n---------- export_text 抽样（第一个成员块）----------")
        print("  " + et[0].split("\n\n")[0].replace("\n", "\n  "))

    conn.commit()
    conn.close()
    print(f"\n[完成] {DB_PATH} ({DB_PATH.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
