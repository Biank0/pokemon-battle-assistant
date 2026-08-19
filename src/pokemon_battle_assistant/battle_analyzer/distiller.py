"""蒸馏器：battles.db 原始对战数据 → 喂 LLM 的紧凑结构化摘要。

50 轮 ≈ 800 条动作记录不能全喂（token 爆炸），蒸馏成四块：
  session_meta       比分/胜率/回合分布
  pokemon_profiles   每只出场宝可梦档案（出场场数/招式频次/换上下次数）
  matchup_matrix     攻防对位计数（actor 出招 × 对面在场），top N
  sample_timelines   采样场次（最短/最长/中间各 1，3 轮以内全量）逐回合动作

诚实边界：battle_turns 无击倒事件，v1 不统计"谁完成击倒"（模块二后续增强）。
所有名字 JOIN dex 出中文（缺中文回退英文），LLM 直接产出可展示文本。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BATTLES_DB = ROOT / "data" / "battles" / "battles.db"
DEX_DB = ROOT / "data" / "dex" / "dex.db"
TEAMS_DB = ROOT / "data" / "teams" / "teams.db"

MAX_MATCHUPS = 15        # 对位矩阵最多保留的组合数
MAX_TIMELINE_BATTLES = 3  # 采样场数上限（3 轮以内全量）


def distill_session(session_id: str) -> dict:
    """蒸馏一个跑量会话。session 不存在抛 KeyError。"""
    conn = sqlite3.connect(f"file:{BATTLES_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        meta = _session_meta(conn, session_id)
        if meta is None:
            raise KeyError(f"会话不存在: {session_id}")
        battles = conn.execute(
            "SELECT id, round_no, winner, end_turn FROM battles "
            "WHERE session_id=? AND winner != 'error' ORDER BY round_no",
            (session_id,)).fetchall()
        if not battles:
            raise ValueError("该会话没有有效对战数据（全部异常或未开跑）")
        zh = _zh_maps()
        return {
            "session_meta": meta,
            "pokemon_profiles": _profiles(conn, session_id, battles, zh),
            "matchup_matrix": _matchups(conn, session_id, zh),
            "sample_timelines": _timelines(conn, battles, zh),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------- 四块蒸馏
def _session_meta(conn, session_id) -> dict | None:
    s = conn.execute(
        "SELECT team_a_id, team_b_id, format, rounds_total, rounds_done, status "
        "FROM battle_sessions WHERE id=?", (session_id,)).fetchone()
    if not s:
        return None
    wins = dict(conn.execute(
        "SELECT winner, COUNT(*) FROM battles WHERE session_id=? GROUP BY winner",
        (session_id,)).fetchall())
    turns = [r["end_turn"] or 0 for r in conn.execute(
        "SELECT end_turn FROM battles WHERE session_id=? AND winner != 'error'",
        (session_id,)).fetchall()]
    a, b = _team_names(s["team_a_id"]), _team_names(s["team_b_id"])
    a_w, b_w = wins.get("a", 0), wins.get("b", 0)
    return {
        "session_id": session_id,
        "team_a": a["display"], "team_b": b["display"],
        "format": s["format"], "rounds": s["rounds_total"],
        "score": f"{a_w}-{b_w}" + (f"（平 {wins.get('draw', 0)}）" if wins.get("draw") else ""),
        "team_a_wins": a_w, "team_b_wins": b_w,
        "team_a_win_rate": round(a_w / (a_w + b_w) * 100, 1) if (a_w + b_w) else None,
        "avg_turns": round(sum(turns) / len(turns), 1) if turns else None,
        "min_turns": min(turns) if turns else None,
        "max_turns": max(turns) if turns else None,
    }


def _profiles(conn, session_id, battles, zh) -> list[dict]:
    """每只出场过的宝可梦一条档案。出场场数 = 出现过的 distinct battle。"""
    rows = conn.execute(
        "SELECT bt.battle_id, bt.side, bt.action_type, bt.actor_species, "
        "bt.move_id, bt.target_species FROM battle_turns bt "
        "JOIN battles b ON b.id = bt.battle_id WHERE b.session_id=?",
        (session_id,)).fetchall()
    battle_ids = {b["id"] for b in battles}
    stats: dict[str, dict] = {}  # key: side|species

    def entry(side, species):
        k = f"{side}|{species}"
        if k not in stats:
            stats[k] = {"side": side, "species": species,
                        "species_zh": zh["species"].get(species, species),
                        "battles": set(), "moves": {}, "switched_in": 0, "switched_out": 0}
        return stats[k]

    for r in rows:
        if r["action_type"] == "move" and r["actor_species"] and r["battle_id"] in battle_ids:
            e = entry(r["side"], r["actor_species"])
            e["battles"].add(r["battle_id"])
            if r["move_id"]:
                e["moves"][r["move_id"]] = e["moves"].get(r["move_id"], 0) + 1
        elif r["action_type"] == "switch":
            if r["target_species"]:  # 换上者
                e = entry(r["side"], r["target_species"])
                e["battles"].add(r["battle_id"])
                e["switched_in"] += 1
            if r["actor_species"]:   # 换下者
                entry(r["side"], r["actor_species"])["switched_out"] += 1

    total = len(battles)
    out = []
    for e in sorted(stats.values(), key=lambda x: (-len(x["battles"]), x["side"])):
        out.append({
            "side": e["side"], "species_zh": e["species_zh"],
            "appearance": len(e["battles"]),
            "appearance_rate": f"{round(len(e['battles']) / total * 100)}%",
            "switched_in": e["switched_in"], "switched_out": e["switched_out"],
            "moves_used": [{"move_zh": zh["moves"].get(m, m), "count": n}
                           for m, n in sorted(e["moves"].items(), key=lambda kv: -kv[1])],
        })
    return out


def _matchups(conn, session_id, zh) -> list[dict]:
    """攻防对位：谁对谁出招多少次（攻=actor 出招，守=当时对面在场）。"""
    rows = conn.execute(
        "SELECT bt.actor_species, bt.target_species, COUNT(*) n FROM battle_turns bt "
        "JOIN battles b ON b.id = bt.battle_id "
        "WHERE b.session_id=? AND bt.action_type='move' "
        "AND bt.actor_species IS NOT NULL AND bt.target_species IS NOT NULL "
        "GROUP BY bt.actor_species, bt.target_species ORDER BY n DESC LIMIT ?",
        (session_id, MAX_MATCHUPS)).fetchall()
    return [{"attacker_zh": zh["species"].get(r[0], r[0]),
             "defender_zh": zh["species"].get(r[1], r[1]), "attacks": r[2]}
            for r in rows]


def _timelines(conn, battles, zh) -> list[dict]:
    """采样场次：最短/最长/中间各 1；总场数 ≤3 全量。"""
    picked = battles if len(battles) <= MAX_TIMELINE_BATTLES else _pick_samples(battles)
    out = []
    for b in picked:
        turns = conn.execute(
            "SELECT turn, side, action_type, actor_species, move_id, target_species "
            "FROM battle_turns WHERE battle_id=? ORDER BY id", (b["id"],)).fetchall()
        actions = []
        for t in turns:
            if t["action_type"] == "move":
                act = f"{zh['species'].get(t['actor_species'], t['actor_species'])} 使用 " \
                      f"{zh['moves'].get(t['move_id'], t['move_id'])} → " \
                      f"{zh['species'].get(t['target_species'], t['target_species'])}"
            elif t["action_type"] == "switch":
                act = f"{zh['species'].get(t['actor_species'], t['actor_species'])} 换下，" \
                      f"换上 {zh['species'].get(t['target_species'], t['target_species'])}"
            else:
                act = "选择出场顺序"
            actions.append({"turn": t["turn"], "side": t["side"], "action": act})
        out.append({"round_no": b["round_no"],
                    "winner": b["winner"], "end_turn": b["end_turn"],
                    "battle_id": b["id"], "actions": actions})
    return out


def _pick_samples(battles) -> list:
    """最短 / 中间 / 最长三场（按 end_turn 排序去重）。"""
    s = sorted(battles, key=lambda b: b["end_turn"] or 0)
    picks = [s[0], s[len(s) // 2], s[-1]]
    seen, out = set(), []
    for p in picks:
        if p["id"] not in seen:
            seen.add(p["id"])
            out.append(p)
    return out


# ---------------------------------------------------------------- 字典
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


def _team_names(team_id: str) -> dict:
    conn = sqlite3.connect(f"file:{TEAMS_DB}?mode=ro", uri=True)
    try:
        r = conn.execute("SELECT name, display_name FROM teams WHERE id=?",
                         (team_id,)).fetchone()
        if r:
            return {"name": r[0], "display": r[1] or r[0]}
        return {"name": team_id[:8], "display": team_id[:8]}
    finally:
        conn.close()


def to_prompt_text(distilled: dict) -> str:
    """蒸馏 dict → 喂 LLM 的 JSON 文本（set 已在上层转为普通结构）。"""
    return json.dumps(distilled, ensure_ascii=False, indent=1)
