#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建 battles.db —— 对战记录库（纯运行时活库）的初始化 + 冒烟测试

本库无种子数据（内容由模块二运行时写入），脚本做三件事：
  1. 建表（库已存在则跳过建表，幂等）
  2. 写入 meta
  3. 冒烟测试：借用 teams.db 的真实队伍 id，合成一场"3 轮任务"数据，
     跑文档承诺的分析查询（胜率聚合 / 招式统计 / 回合时间线 / 跨库中文渲染），
     然后 ROLLBACK —— 测完不留脏数据，库保持干净待用

用法：
  python scripts/build_battles_db.py              # 幂等建库（已存在则补齐表）
  python scripts/build_battles_db.py --rebuild    # 删库重建（schema 变更后用，会清空对战记录）
"""
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "battles"
DB_PATH = DATA_DIR / "battles.db"
SCHEMA_PATH = DATA_DIR / "schema.sql"
TEAMS_DB = ROOT / "data" / "teams" / "teams.db"
DEX_DB = ROOT / "data" / "dex" / "dex.db"

SCHEMA_VERSION = "1"


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if "--rebuild" in sys.argv:
        if DB_PATH.exists():
            DB_PATH.unlink()
            print(f"[重建] 已删除旧库 {DB_PATH}")

    for p, hint in ((SCHEMA_PATH, "schema"), (TEAMS_DB, "teams.db（先跑 build_teams_db.py）"),
                    (DEX_DB, "dex.db（先跑 build_dex_db.py）")):
        if not p.exists():
            print(f"[错误] 缺少{hint}: {p}")
            return 1

    DATA_DIR.mkdir(exist_ok=True)
    existed = DB_PATH.exists()
    conn = sqlite3.connect(DB_PATH)
    if existed:
        # 已有库：幂等补建表（CREATE TABLE IF NOT EXISTS）并刷新 meta
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        print(f"[增量] {DB_PATH} 已存在，补齐表结构")
    else:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        print(f"[建库] {DB_PATH} 已创建")

    conn.execute("INSERT OR REPLACE INTO meta (key,value) VALUES ('schema_version',?)",
                 (SCHEMA_VERSION,))
    teams_ver = None
    if TEAMS_DB.exists():
        tc = sqlite3.connect(f"file:{TEAMS_DB}?mode=ro", uri=True)
        row = tc.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        teams_ver = row[0] if row else "unknown"
        tc.close()
    conn.execute("INSERT OR REPLACE INTO meta (key,value) VALUES ('teams_schema_version',?)",
                 (teams_ver or "unknown",))
    conn.commit()

    # ============ 冒烟测试（合成数据 → 查询验证 → ROLLBACK） ============
    print("\n========== 冒烟测试（事务内合成数据，结束回滚） ==========")
    conn.execute("ATTACH DATABASE ? AS teams", (str(TEAMS_DB),))
    conn.execute("ATTACH DATABASE ? AS dex", (str(DEX_DB),))

    # 取两支真实队伍（xiaobian vs bss_balance）
    ta = conn.execute("SELECT id,display_name FROM teams.teams WHERE name='xiaobian'").fetchone()
    tb = conn.execute("SELECT id,display_name FROM teams.teams WHERE name='bss_balance'").fetchone()
    if not (ta and tb):
        print("[跳过] teams.db 中未找到测试队伍，跳过冒烟测试")
        conn.close()
        return 0
    print(f"  参战队伍: A={ta[1]} vs B={tb[1]}")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    session_id = str(uuid.uuid4())

    try:
        conn.execute("BEGIN")
        # --- session ---
        conn.execute(
            "INSERT INTO battle_sessions "
            "(id,team_a_id,team_b_id,format,bot_config,rounds_total,rounds_done,status,"
            "started_at,finished_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (session_id, ta[0], tb[0], "gen9ou",
             json.dumps({"a": {"type": "heuristic"}, "b": {"type": "heuristic"}}),
             3, 3, "completed", now, now),
        )

        # --- 3 场对战（A 胜/胜/B 胜），每场几条回合明细 ---
        script = [
            # (round_no, winner, end_turn, turns[(turn, side, type, actor, move, target, raw)])
            (1, "a", 18, [
                (0, "a", "team_order", None, None, None, "/team 123456"),
                (0, "b", "team_order", None, None, None, "/team 654321"),
                (1, "a", "move", "ninetales", "weatherball", "squawkabilly", "move weatherball"),
                (1, "b", "switch", "squawkabilly", None, "garchomp", "switch garchomp"),
                (2, "a", "move", "ninetales", "willowisp", "garchomp", "move willowisp"),
                (2, "b", "move", "garchomp", "earthquake", "ninetales", "move earthquake"),
            ]),
            (2, "a", 25, [
                (1, "a", "move", "walkingwake", "hydrosteam", "squawkabilly", "move hydrosteam"),
                (1, "b", "move", "squawkabilly", "boomburst", "walkingwake", "move boomburst"),
            ]),
            (3, "b", 31, [
                (1, "a", "move", "lilliganthisui", "victorydance", "lilliganthisui", "move victorydance"),
                (1, "b", "move", "garchomp", "scale shot", None, "move scaleshot"),
            ]),
        ]
        for round_no, winner, end_turn, turns in script:
            battle_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO battles (id,session_id,round_no,battle_tag,winner,end_turn,"
                "record_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (battle_id, session_id, round_no, f"battle-gen9ou-smoke-{round_no}",
                 winner, end_turn, json.dumps({"smoke": True}), now),
            )
            for (turn, side, atype, actor, move, target, raw) in turns:
                conn.execute(
                    "INSERT INTO battle_turns "
                    "(battle_id,turn,side,action_type,actor_species,move_id,target_species,raw_label) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (battle_id, turn, side, atype, actor, move, target, raw),
                )

        # --- 查询 1：战绩聚合 ---
        rows = conn.execute(
            "SELECT winner, COUNT(*) FROM battles WHERE session_id=? GROUP BY winner",
            (session_id,)).fetchall()
        print(f"\n  [查询1] 战绩聚合: {dict(rows)}  (期望 a:2, b:1)")

        # --- 查询 2：胜率 ---
        rate = conn.execute(
            "SELECT SUM(winner='a')*1.0/COUNT(*) FROM battles "
            "WHERE session_id=? AND winner!='error'", (session_id,)).fetchone()[0]
        print(f"  [查询2] A 队胜率: {rate:.0%}  (期望 67%)")

        # --- 查询 3：招式使用统计（跨库 JOIN dex 中文） ---
        print("  [查询3] 招式统计（中文渲染）:")
        for mid, zh, en, c in conn.execute(
                "SELECT t.move_id, m.name_zh, m.name_en, COUNT(*) c FROM battle_turns t "
                "LEFT JOIN dex.moves m ON m.id=t.move_id "
                "WHERE t.action_type='move' GROUP BY t.move_id ORDER BY c DESC LIMIT 3"):
            print(f"           {zh or en}（{mid}）× {c}")

        # --- 查询 4：单场逐回合时间线 ---
        bid = conn.execute(
            "SELECT id FROM battles WHERE session_id=? AND round_no=1", (session_id,)).fetchone()[0]
        sp_zh = {r[0]: (r[1] or r[2]) for r in conn.execute(
            "SELECT id,name_zh,name_en FROM dex.species")}
        print("  [查询4] 第 1 场时间线:")
        for turn, side, atype, actor, move, target in conn.execute(
                "SELECT turn,side,action_type,actor_species,move_id,target_species "
                "FROM battle_turns WHERE battle_id=? ORDER BY id", (bid,)):
            zh_name = sp_zh.get(actor, actor) if actor else ""
            tgt = sp_zh.get(target, target) if target else ""
            print(f"           回合{turn:<2} {'己方' if side == 'a' else '对手'} "
                  f"{atype:<10} {zh_name} → {tgt or (move or '')}")

        # --- 唯一约束验证：同 session 同 round_no 不允许重复 ---
        try:
            conn.execute("INSERT INTO battles (id,session_id,round_no,winner,record_json,created_at) "
                         "VALUES (?,?,?,?,?,?)", (str(uuid.uuid4()), session_id, 1, "a", "{}", now))
            print("\n  [约束] 唯一索引未生效！（不应出现）")
            return 1
        except sqlite3.IntegrityError:
            print("\n  [约束] (session_id, round_no) 唯一索引生效 ✓")

        conn.execute("ROLLBACK")
        print("\n  [回滚] 合成数据已清除")

    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"[错误] 冒烟测试失败: {e}")
        return 1
    finally:
        # 确认库内无残留
        n = conn.execute("SELECT COUNT(*) FROM battle_sessions").fetchone()[0]
        print(f"  [验证] battle_sessions 剩余行数: {n}  (期望 0)")

    conn.commit()
    conn.close()
    print(f"\n[完成] {DB_PATH} 就绪 ({DB_PATH.stat().st_size / 1024:.1f} KB)，等待模块二写入")
    return 0


if __name__ == "__main__":
    sys.exit(main())
