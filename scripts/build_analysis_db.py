#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建 analysis.db —— 分析文档库（索引库）的初始化 + 冒烟测试

核心设计"索引在库、本体在文件"的落地验证：
  1. 建表（幂等）+ 写 meta
  2. 冒烟测试：合成一份 session 分析——写临时文档文件 + 库内索引/高光，
     验证列表页查询、高光跳转 battle_turns、跨库中文渲染，然后回滚并删除临时文件
  3. 库与 data/analysis/docs/ 目录保持干净，等待模块三写入

用法：
  python scripts/build_analysis_db.py
"""
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "analysis"
DB_PATH = DATA_DIR / "analysis.db"
SCHEMA_PATH = DATA_DIR / "schema.sql"
DOCS_DIR = DATA_DIR / "docs"
TEAMS_DB = ROOT / "data" / "teams" / "teams.db"
BATTLES_DB = ROOT / "data" / "battles" / "battles.db"
DEX_DB = ROOT / "data" / "dex" / "dex.db"

SCHEMA_VERSION = "1"


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    deps = ((SCHEMA_PATH, "schema"), (TEAMS_DB, "teams.db"), (BATTLES_DB, "battles.db"),
            (DEX_DB, "dex.db"))
    for p, hint in deps:
        if not p.exists():
            print(f"[错误] 缺少{hint}: {p}")
            return 1

    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)
    gitkeep = DOCS_DIR / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.write_text("", encoding="utf-8")

    existed = DB_PATH.exists()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    print(f"[{'增量' if existed else '建库'}] {DB_PATH}")

    # meta：记录关联库版本
    def db_version(path: Path) -> str:
        c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        row = c.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        c.close()
        return row[0] if row else "unknown"

    conn.execute("INSERT OR REPLACE INTO meta (key,value) VALUES ('schema_version',?)",
                 (SCHEMA_VERSION,))
    conn.execute("INSERT OR REPLACE INTO meta (key,value) VALUES ('battles_schema_version',?)",
                 (db_version(BATTLES_DB),))
    conn.execute("INSERT OR REPLACE INTO meta (key,value) VALUES ('teams_schema_version',?)",
                 (db_version(TEAMS_DB),))
    conn.commit()

    # ============ 冒烟测试 ============
    print("\n========== 冒烟测试（合成分析 → 查询验证 → 回滚+删临时文件） ===========")
    conn.execute("ATTACH DATABASE ? AS teams", (str(TEAMS_DB),))
    conn.execute("ATTACH DATABASE ? AS battles", (str(BATTLES_DB),))
    conn.execute("ATTACH DATABASE ? AS dex", (str(DEX_DB),))

    ta = conn.execute("SELECT id,display_name FROM teams.teams WHERE name='xiaobian'").fetchone()
    tb = conn.execute("SELECT id,display_name FROM teams.teams WHERE name='bss_balance'").fetchone()
    if not (ta and tb):
        print("[跳过] 未找到测试队伍")
        conn.close()
        return 0

    analysis_id = str(uuid.uuid4())
    doc_json = DOCS_DIR / f"{analysis_id}.json"
    doc_md = DOCS_DIR / f"{analysis_id}.md"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    try:
        # --- 写入契约演练：先文件后库 ---
        doc = {
            "id": analysis_id, "scope_type": "session", "scope_id": "smoke-session",
            "title": f"{ta[1]} vs {tb[1]} · 冒烟测试", "summary": "晴天轴运转顺畅",
            "rating": "B+", "sections": [
                {"heading": "整体战绩", "body": "33胜17负"},
                {"heading": "改进建议", "body": "补一只钢系应对"},
            ],
            "highlights": [
                {"seq": 1, "battle_id": "smoke-battle-1", "round_no": 1, "turn": 2,
                 "side": "b", "description": "换上烈咬陆鲨规避鬼火"},
            ],
        }
        doc_json.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        doc_md.write_text(f"# {doc['title']}\n\n{doc['summary']}\n", encoding="utf-8")
        print(f"  文档文件已写入: {doc_json.name} / {doc_md.name}")

        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO analyses (id,scope_type,scope_id,title,summary,rating,win_rate,"
            "stats_json,model,skill_version,doc_json_path,doc_md_path,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (analysis_id, "session", "smoke-session", doc["title"], doc["summary"], "B+",
             0.66, json.dumps({"battles": 50, "avg_turns": 24.3}),
             "deepseek-v4-flash", "1",
             f"data/analysis/docs/{analysis_id}.json", f"data/analysis/docs/{analysis_id}.md", now),
        )
        for h in doc["highlights"]:
            conn.execute(
                "INSERT INTO analysis_highlights "
                "(analysis_id,seq,battle_id,round_no,turn,side,description) VALUES (?,?,?,?,?,?,?)",
                (analysis_id, h["seq"], h["battle_id"], h["round_no"], h["turn"],
                 h["side"], h["description"]),
            )

        # --- 查询 1：列表页查询（零文件 IO） ---
        rows = conn.execute(
            "SELECT title,summary,rating,win_rate,created_at FROM analyses "
            "ORDER BY created_at DESC").fetchall()
        r = rows[0]
        print(f"\n  [查询1] 列表页: {r[0]} ｜ {r[1]} ｜ 评级 {r[2]} ｜ 胜率 {r[3]:.0%}")

        # --- 查询 2：高光跳转 battle_turns（跨三库） ---
        print("  [查询2] 高光回合（JOIN battle_turns + dex 中文）:")
        sp_zh = {x[0]: (x[1] or x[2]) for x in conn.execute(
            "SELECT id,name_zh,name_en FROM dex.species")}
        mv_zh = {x[0]: (x[1] or x[2]) for x in conn.execute(
            "SELECT id,name_zh,name_en FROM dex.moves")}
        for desc, turn, side, actor, move in conn.execute(
                "SELECT h.description,h.turn,h.side,t.actor_species,t.move_id "
                "FROM analysis_highlights h "
                "LEFT JOIN battles.battle_turns t "
                "ON t.battle_id=h.battle_id AND t.turn=h.turn AND t.side=h.side "
                "WHERE h.analysis_id=?", (analysis_id,)):
            actor_zh = sp_zh.get(actor, "-") if actor else "-"
            move_zh = mv_zh.get(move, "-") if move else "-"
            print(f"           回合{turn} {'己方' if side == 'a' else '对手'} "
                  f"{actor_zh}·{move_zh} ｜ 点评: {desc}")

        # --- 查询 3：文档文件与索引一致性 ---
        j = json.loads(doc_json.read_text(encoding="utf-8"))
        match = (j["id"] == analysis_id and j["highlights"][0]["description"] ==
                 conn.execute("SELECT description FROM analysis_highlights WHERE analysis_id=?",
                              (analysis_id,)).fetchone()[0])
        print(f"  [查询3] 文档文件与库内索引一致: {'✓' if match else '✗'}")

        conn.execute("ROLLBACK")
        doc_json.unlink()
        doc_md.unlink()
        print("\n  [回滚] 索引已回滚，临时文档文件已删除")

    except Exception as e:
        conn.execute("ROLLBACK")
        for f in (doc_json, doc_md):
            f.unlink(missing_ok=True)
        print(f"[错误] 冒烟测试失败: {e}")
        return 1
    finally:
        n = conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        files = list(DOCS_DIR.glob("*.json")) + list(DOCS_DIR.glob("*.md"))
        print(f"  [验证] analyses 剩余 {n} 行 / docs 剩余 {len(files)} 个文档  (期望 0 / 0)")

    conn.commit()
    conn.close()
    print(f"\n[完成] {DB_PATH} 就绪 ({DB_PATH.stat().st_size / 1024:.1f} KB)，等待模块三写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
