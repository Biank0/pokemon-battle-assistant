"""阶段2 pool：蓝图角色位 → SQL 候选池（零 LLM）。

筛选策略（docs/module1_team_builder.md 第五节）：
- 属性偏好（type1/type2 拆列 IN）
- 数值门槛（种族值拆列 >=，多维度 AND）
- 强度保底（bst >= 450，防未进化宝宝污染池）
- 池大小控制：目标 5~25 只；<5 自动放宽两轮（先降门槛 20%，再去属性限制）
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .planner import slugify

# 排除特殊形态（mega/gmax/图腾等）：Gen9 不可用，污染候选池
_FORM_EXCLUDE = ("s.id NOT LIKE '%mega%' AND s.id NOT LIKE '%gmax%' "
                 "AND s.id NOT LIKE '%totem%' AND s.id NOT LIKE '%primal%'")

# 排除无可学招式数据的物种（自己与基础形态都没有 learnsets 就无法配招，不该进池）
_HAS_LEARNSETS = (
    "(EXISTS (SELECT 1 FROM learnsets l WHERE l.species_id = s.id) OR "
    "(s.base_species IS NOT NULL AND "
    "EXISTS (SELECT 1 FROM learnsets l2 WHERE l2.species_id = s.base_species)))")

ROOT = Path(__file__).resolve().parents[3]
DEX_DB = ROOT / "data" / "dex" / "dex.db"

POOL_LIMIT = 25
MIN_KEEP = 5
BST_FLOOR = 450

STAT_ZH = {"hp": "HP", "atk": "攻", "def": "防", "spa": "特攻", "spd": "特防", "spe": "速"}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DEX_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _query(conn: sqlite3.Connection, slot: dict, bst_floor: int,
           use_types: bool, stat_scale: float) -> list[sqlite3.Row]:
    where, params = [f"s.bst >= ?", _FORM_EXCLUDE, _HAS_LEARNSETS], [bst_floor]
    if use_types and slot["types"]:
        marks = ",".join("?" * len(slot["types"]))
        where.append(f"(s.type1 IN ({marks}) OR s.type2 IN ({marks}))")
        params += slot["types"] * 2
    for k, v in slot["stat_min"].items():
        where.append(f"s.{k} >= ?")
        params.append(int(v * stat_scale))
    order_keys = slot["stat_focus"] or list(slot["stat_min"]) or ["bst"]
    order = ", ".join(f"s.{k} DESC" for k in order_keys if k != "bst") or "s.bst DESC"
    if "bst" in order_keys and order != "s.bst DESC":
        order += ", s.bst DESC"
    sql = (f"SELECT s.* FROM species s WHERE {' AND '.join(where)} "
           f"ORDER BY {order} LIMIT {POOL_LIMIT}")
    return conn.execute(sql, params).fetchall()


def _top_moves(conn: sqlite3.Connection, species_id: str, limit: int = 6) -> list[tuple]:
    """该物种威力最高的代表招（攻击招），给 LLM 配招线索。

    Showdown learnsets 按基础形态存储：形态无数据时回退查基础形态。
    """
    base = conn.execute("SELECT base_species FROM species WHERE id=?",
                        (species_id,)).fetchone()
    for sid in (species_id, base[0] if base and base[0] else None):
        if not sid:
            continue
        rows = conn.execute(
            "SELECT m.id, m.name_zh, m.name_en, m.base_power FROM learnsets l "
            "JOIN moves m ON m.id = l.move_id "
            "WHERE l.species_id = ? AND m.base_power > 0 "
            "ORDER BY m.base_power DESC, m.id LIMIT ?", (sid, limit)).fetchall()
        if rows:
            return rows
    return []


def build_pool(conn: sqlite3.Connection, slot: dict) -> list[dict]:
    """单角色位 → 候选池（自动放宽）。"""
    rows = _query(conn, slot, BST_FLOOR, use_types=True, stat_scale=1.0)
    if len(rows) < MIN_KEEP:  # 第一轮放宽：门槛降 20%
        rows = _query(conn, slot, BST_FLOOR, use_types=True, stat_scale=0.8)
    if len(rows) < MIN_KEEP:  # 第二轮放宽：去掉属性限制
        rows = _query(conn, slot, BST_FLOOR, use_types=False, stat_scale=0.8)
    pool = []
    for r in rows:
        abilities = json.loads(r["abilities"]) if r["abilities"] else {}
        pool.append({
            "species": r["id"],
            "name_zh": r["name_zh"] or r["name_en"],
            "types": "/".join(t for t in (r["type1"], r["type2"]) if t),
            "stats": {k: r[k] for k in ("hp", "atk", "def", "spa", "spd", "spe")},
            "abilities": sorted({slugify(a) for a in abilities.values() if a}),
            "top_moves": [(m[0], m[1] or m[2], m[3]) for m in _top_moves(conn, r["id"])],
        })
    return pool


def render_pools(blueprint: dict, pools: list[list[dict]]) -> str:
    """候选池 → 喂 LLM 的紧凑文本。"""
    parts = []
    for i, (slot, pool) in enumerate(zip(blueprint["slots"], pools), 1):
        cond = []
        if slot["types"]:
            cond.append("偏好属性 " + "/".join(slot["types"]))
        cond += [f"{STAT_ZH[k]}≥{v}" for k, v in slot["stat_min"].items()]
        head = f"## 角色位{i}：{slot['role_zh']}" + (f"（{'，'.join(cond)}）" if cond else "")
        if slot["notes"]:
            head += f" ｜ 说明：{slot['notes']}"
        lines = [head]
        for p in pool:
            st = p["stats"]
            stats_s = "/".join(str(st[k]) for k in ("hp", "atk", "def", "spa", "spd", "spe"))
            moves_s = ", ".join(f"{s}({n},{bp})" for s, n, bp in p["top_moves"])
            lines.append(
                f"- {p['species']} {p['name_zh']} ｜ {p['types']} ｜ "
                f"种族值 HP/{stats_s} ｜ 特性: {', '.join(p['abilities'])} ｜ "
                f"代表招: {moves_s}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def build_pools(blueprint: dict) -> tuple[list[list[dict]], str]:
    """全部角色位 → (池列表, 喂 LLM 文本)。"""
    conn = _connect()
    try:
        pools = [build_pool(conn, slot) for slot in blueprint["slots"]]
    finally:
        conn.close()
    return pools, render_pools(blueprint, pools)
