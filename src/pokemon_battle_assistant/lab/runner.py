"""单场对战执行：两队 export_text → poke-env 本地对战 → 写 battles.db。

写库三层（docs/battles_db_schema.md 契约）：
  battles        winner(a/b/draw/error) + end_turn + battle_tag + record_json
  battle_turns   双方 records 拆行（side='a'/'b'）
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import bot as bot_mod
from . import server

ROOT = Path(__file__).resolve().parents[3]
BATTLES_DB = ROOT / "data" / "battles" / "battles.db"


async def run_battle(session_id: str, round_no: int, format_id: str,
                     team_a: dict, team_b: dict, log=print) -> dict:
    """跑一场对战并写库。team/team_b: {name, display_name, export_text}。

    返回 {battle_id, winner, end_turn}。异常向上抛（session 层记 error）。
    """
    server.ensure_server(log=log)

    # 用户名加随机后缀：避免 showdown 上的名字冲突（连续场次复用连接名）
    suffix = uuid.uuid4().hex[:6]
    bot_a = bot_mod.CollectorBot(f"pba{suffix}a", team_a["export_text"], format_id)
    bot_b = bot_mod.CollectorBot(f"pba{suffix}b", team_b["export_text"], format_id)
    try:
        await bot_a.battle_against(bot_b, n_battles=1)
    finally:
        await _stop_bots(bot_a, bot_b)

    # ---- 收集结果 ----
    winner = _winner_of(bot_a, bot_b)
    end_turn, battle_tag = _battle_meta(bot_a, bot_b)

    # 双方动作记录：a 为先手方（challenger）
    records_a, records_b = bot_a.records, bot_b.records
    result = {
        "session_id": session_id, "round_no": round_no,
        "teams": {"a": team_a["name"], "b": team_b["name"]},
        "winner": winner, "end_turn": end_turn,
        "turns": {"a": records_a, "b": records_b},
    }
    battle_id = _save(session_id, round_no, winner, end_turn, battle_tag, result)
    return {"battle_id": battle_id, "winner": winner, "end_turn": end_turn}


async def _stop_bots(*bots) -> None:
    for b in bots:
        try:
            await b.stop_listening()
        except Exception:
            pass  # 停止失败不影响结果采集


def _winner_of(bot_a, bot_b) -> str:
    """从 battle.won/.lost 判定胜负 → 'a'/'b'/'draw'。"""
    for battle in bot_a.battles.values():
        if battle.won:
            return "a"
        if battle.lost:
            return "b"
    for battle in bot_b.battles.values():
        if battle.won:
            return "b"
        if battle.lost:
            return "a"
    return "draw"


def _battle_meta(bot_a, bot_b) -> tuple[int, str | None]:
    for bot in (bot_a, bot_b):
        for battle in bot.battles.values():
            return getattr(battle, "turn", 0), getattr(battle, "battle_tag", None)
    return 0, None


def _save(session_id: str, round_no: int, winner: str, end_turn: int,
          battle_tag: str | None, result: dict) -> str:
    """battles + battle_turns 同事务写入，返回 battle_id。"""
    battle_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn = sqlite3.connect(BATTLES_DB)
    try:
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO battles (id,session_id,round_no,winner,end_turn,battle_tag,"
            "record_json,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (battle_id, session_id, round_no, winner, end_turn, battle_tag,
             json.dumps(result, ensure_ascii=False), now))
        for side, recs in (("a", result["turns"]["a"]), ("b", result["turns"]["b"])):
            conn.executemany(
                "INSERT INTO battle_turns (battle_id,turn,side,action_type,"
                "actor_species,move_id,target_species,raw_label) VALUES (?,?,?,?,?,?,?,?)",
                [(battle_id, r["turn"], side,
                  "switch" if r["action_type"] == "switch" else r["action_type"],
                  r["actor_species"],
                  r["action"] if r["action_type"] == "move" else None,
                  r["action"] if r["action_type"] == "switch" else r["opponent_species"],
                  f"{r['action_type']}:{r['action']}")
                 for r in recs])
        conn.commit()
        return battle_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
