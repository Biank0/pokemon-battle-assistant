"""阶段4 validator：合法性校验五道闸门（纯本地，零 LLM）。

闸门清单（docs/module1_team_builder.md 第六节）：
  1 结构      字段齐全、成员数、招式数、EV/IV 边界
  2 存在性    species/ability/item/nature/move 全在 dex
  3 归属      ability ∈ 该物种特性列表
  4 可学习    每一招都在该物种 learnsets 里（反幻觉核心）
  5 赛制      等级、道具不重复、物种不重复

返回中文错误清单（空列表 = 通过），格式："槽位N：..."，可直接回喂 LLM 修复。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .planner import slugify

ROOT = Path(__file__).resolve().parents[3]
DEX_DB = ROOT / "data" / "dex" / "dex.db"

TYPES_18 = {
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
}
STAT_KEYS = ("hp", "atk", "def", "spa", "spd", "spe")
MOVE_COUNT_RANGE = (1, 4)
EV_MAX_SINGLE, EV_MAX_TOTAL = 252, 510
IV_MAX = 31


def _dex_sets(conn: sqlite3.Connection) -> dict:
    return {t: {r[0] for r in conn.execute(f"SELECT id FROM {t}")}
            for t in ("species", "abilities", "items", "natures", "moves")}


def validate(team: dict, format_id: str, skill) -> list[str]:
    """校验队伍 dict，返回错误清单。"""
    c = skill.constraints(format_id)
    errors: list[str] = []
    members = team.get("members")

    # ---------- 闸门1：结构 ----------
    if not isinstance(members, list):
        return ["结构错误：缺少 members 数组"]
    if len(members) != c["team_size"]:
        errors.append(f"结构错误：成员数 {len(members)}，赛制要求 {c['team_size']} 只")
    if not team.get("display_name"):
        errors.append("结构错误：缺少中文队名 display_name")
    name_en = team.get("name_en")
    if not name_en or not isinstance(name_en, str):
        errors.append("结构错误：缺少英文标识 name_en")

    for i, m in enumerate(members, 1):
        tag = f"槽位{i}"
        moves = m.get("moves")
        if not isinstance(moves, list) or not (MOVE_COUNT_RANGE[0] <= len(moves) <= MOVE_COUNT_RANGE[1]):
            errors.append(f"{tag}：招式数应为 1~4 个，当前 {len(moves) if isinstance(moves, list) else '缺失'}")
        evs, ivs = m.get("evs") or {}, m.get("ivs") or {}
        if evs:
            total = 0
            for k, v in evs.items():
                if k not in STAT_KEYS or not isinstance(v, int) or not 0 <= v <= EV_MAX_SINGLE:
                    errors.append(f"{tag}：EV 非法 {k}={v}（应六维小写键、0~{EV_MAX_SINGLE}）")
                else:
                    total += v
            if total > EV_MAX_TOTAL:
                errors.append(f"{tag}：EV 总和 {total} 超过 {EV_MAX_TOTAL}")
        if ivs:
            for k, v in ivs.items():
                if k not in STAT_KEYS or not isinstance(v, int) or not 0 <= v <= IV_MAX:
                    errors.append(f"{tag}：IV 非法 {k}={v}（应六维小写键、0~{IV_MAX}）")

    # ---------- 后续闸门 ----------
    conn = sqlite3.connect(f"file:{DEX_DB}?mode=ro", uri=True)
    try:
        dex = _dex_sets(conn)
        seen_species, seen_items = [], []
        for i, m in enumerate(members, 1):
            tag = f"槽位{i}"
            sp = m.get("species")
            sp_display = sp or "?"

            # 闸门2：存在性
            if not sp or sp not in dex["species"]:
                errors.append(f"{tag}：宝可梦 {sp!r} 不在图鉴中（必须从候选池选）")
                continue
            zh = conn.execute(
                "SELECT name_zh, name_en, abilities, base_species FROM species WHERE id=?",
                (sp,)).fetchone()
            sp_name = zh[0] or zh[1]

            for mv in m.get("moves") or []:
                if mv not in dex["moves"]:
                    errors.append(f"{tag}：招式 {mv!r} 不在招式库中")
            if m.get("ability") and m["ability"] not in dex["abilities"]:
                errors.append(f"{tag}：特性 {m['ability']!r} 不在特性库中")
            if m.get("item") is not None and m["item"] not in dex["items"]:
                errors.append(f"{tag}：道具 {m['item']!r} 不在道具库中")
            if m.get("nature") and m["nature"] not in dex["natures"]:
                errors.append(f"{tag}：性格 {m['nature']!r} 不在 25 性格表中")
            if m.get("tera_type") and m["tera_type"] not in TYPES_18:
                errors.append(f"{tag}：太晶属性 {m['tera_type']!r} 非法（18 属性英文首字母大写）")

            # 闸门3：特性归属（species.abilities 存显示名，统一 slug 后比对）
            if m.get("ability"):
                legal = {slugify(a) for a in
                         (json.loads(zh[2]).values() if zh[2] else []) if a}
                if m["ability"] not in legal:
                    errors.append(f"{tag}：{sp_name} 没有特性 {m['ability']!r}"
                                  f"（可选：{', '.join(sorted(legal))}）")

            # 闸门4：可学习（Showdown learnsets 按基础形态存：先查自己，miss 回退基础形态）
            base_sp = zh[3] if len(zh) > 3 else None
            for mv in m.get("moves") or []:
                if mv in dex["moves"]:
                    ok = conn.execute(
                        "SELECT 1 FROM learnsets WHERE species_id=? AND move_id=?",
                        (sp, mv)).fetchone()
                    if not ok and base_sp:
                        ok = conn.execute(
                            "SELECT 1 FROM learnsets WHERE species_id=? AND move_id=?",
                            (base_sp, mv)).fetchone()
                    if not ok:
                        mv_zh = conn.execute(
                            "SELECT name_zh, name_en FROM moves WHERE id=?", (mv,)).fetchone()
                        mv_name = (mv_zh[0] or mv_zh[1]) if mv_zh else mv
                        errors.append(f"{tag}：{sp_name} 学不会招式 {mv_name}（{mv}）")

            # 闸门5：赛制
            if m.get("level") is not None and m["level"] != c["level"]:
                errors.append(f"{tag}：等级 {m['level']} 应为 {c['level']}（{c['display_name']}）")
            if not c["allow_dup_species"]:
                if sp in seen_species:
                    errors.append(f"{tag}：物种重复 {sp_name}（赛制禁止同族）")
                seen_species.append(sp)
            if not c["allow_dup_items"] and m.get("item"):
                if m["item"] in seen_items:
                    it_zh = conn.execute("SELECT name_zh, name_en FROM items WHERE id=?",
                                         (m["item"],)).fetchone()
                    it_name = (it_zh[0] or it_zh[1]) if it_zh else m["item"]
                    errors.append(f"{tag}：道具重复 {it_name}（赛制禁止道具重复）")
                seen_items.append(m["item"])
    finally:
        conn.close()
    return errors
