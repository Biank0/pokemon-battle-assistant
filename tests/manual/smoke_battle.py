"""集成冒烟：真实跑 2 场对战（xiaobian vs bss_balance，gen9ou）。

验证链路：Showdown 自动拉起 → poke-env bot → 数据采集 → battles.db 三层写入。
"""
import asyncio
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pokemon_battle_assistant.lab import runner, session


def main():
    a = session.get_team("xiaobian")
    b = session.get_team("bss_balance")
    print(f"A: {a['display_name']} | B: {b['display_name']}")

    sid = session.create_session("xiaobian", "bss_balance", "gen9bssregi", 2)
    print(f"session: {sid[:8]}")

    async def go():
        for i in (1, 2):
            res = await runner.run_battle(sid, i, "gen9bssregi", a, b)
            print(f"第{i}场: winner={res['winner']} turns={res['end_turn']} battle={res['battle_id'][:8]}")
    asyncio.run(go())

    conn = sqlite3.connect(ROOT / "data" / "battles" / "battles.db")
    n_battles = conn.execute("SELECT COUNT(*) FROM battles WHERE session_id=?", (sid,)).fetchone()[0]
    n_turns = conn.execute(
        "SELECT COUNT(*) FROM battle_turns bt JOIN battles b ON b.id=bt.battle_id "
        "WHERE b.session_id=?", (sid,)).fetchone()[0]
    sample = conn.execute(
        "SELECT turn, side, action_type, actor_species, move_id, target_species "
        "FROM battle_turns bt JOIN battles b ON b.id=bt.battle_id "
        "WHERE b.session_id=? ORDER BY bt.rowid LIMIT 6", (sid,)).fetchall()
    print(f"\n[库] battles={n_battles} battle_turns={n_turns}")
    print("[库] 采样:")
    for r in sample:
        print("  ", r)
    # 清理冒烟数据（保持库干净）
    conn.execute("DELETE FROM battle_turns WHERE battle_id IN "
                 "(SELECT id FROM battles WHERE session_id=?)", (sid,))
    conn.execute("DELETE FROM battles WHERE session_id=?", (sid,))
    conn.execute("DELETE FROM battle_sessions WHERE id=?", (sid,))
    conn.commit()
    print("\n[清理] 冒烟数据已回滚")
    conn.close()


if __name__ == "__main__":
    main()
