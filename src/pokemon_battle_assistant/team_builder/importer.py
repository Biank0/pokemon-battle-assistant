"""Showdown 导出串 → 结构化成员（手工建队/调整队伍的入口）。

解析规则（标准 Showdown paste 格式，成员间空行分隔）：
    Urshifu-Rapid-Strike @ Choice Scarf     或  Nickname (Species) @ Item
    Ability: Unseen Fist
    Level: 50
    Tera Type: Water
    EVs: 252 Atk / 4 SpD / 252 Spe
    Jolly Nature
    IVs: 0 SpA
    - Surging Strikes

名称解析：统一 slugify 后查 dex.id；miss 时回退 name_en / name_zh 精确匹配；
♀/♂ 形态（如 Nidoran）做 f/m 后缀变体尝试。解析失败抛 ImportParseError（中文，
逐条列出），由 API 层转 400。
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .planner import slugify

ROOT = Path(__file__).resolve().parents[3]
DEX_DB = ROOT / "data" / "dex" / "dex.db"

_STAT_NAME = {"hp": "hp", "atk": "atk", "def": "def",
              "spa": "spa", "spd": "spd", "spe": "spe"}
_KNOWN_PREFIX = ("ability:", "level:", "tera type:", "evs:", "ivs:",
                 "shiny:", "happiness:", "dynamax level:", "gigantamax:",
                 "hidden power:")


class ImportParseError(Exception):
    """导出串无法解析/名称无法识别，message 为中文错误清单（\\n 分隔）。"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{DEX_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _resolve(conn: sqlite3.Connection, table: str, name: str) -> str | None:
    """显示名 → dex slug：id 直中 → ♀/♂ 变体 → name_en → name_zh。"""
    cands = [slugify(name)]
    if "♀" in name:
        cands.append(slugify(name.replace("♀", "f")))
    if "♂" in name:
        cands.append(slugify(name.replace("♂", "m")))
    for c in dict.fromkeys(cands):
        if c and conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (c,)).fetchone():
            return c
    cols = "name_en" if table == "natures" else "name_en, name_zh"
    rows = conn.execute(f"SELECT id, {cols} FROM {table}").fetchall()
    low = name.strip().lower()
    for r in rows:
        names = [r["name_en"]] + ([r["name_zh"]] if "name_zh" in r.keys() else [])
        if any(n and n.strip().lower() == low for n in names):
            return r["id"]
    return None


def _parse_stats(text: str, tag: str, errors: list[str]) -> dict:
    """'252 Atk / 4 SpD / 252 Spe' → {atk:252, spd:4, spe:252}"""
    out: dict = {}
    for part in text.split("/"):
        m = re.match(r"\s*(\d+)\s+([A-Za-z. ]+?)\s*$", part)
        if not m or m.group(2).lower().replace(".", "").replace(" ", "") not in _STAT_NAME:
            errors.append(f"{tag}：无法解析数值项 {part.strip()!r}")
            continue
        key = _STAT_NAME[m.group(2).lower().replace(".", "").replace(" ", "")]
        out[key] = int(m.group(1))
    return out


def _split_species_line(line: str) -> tuple[str, str | None]:
    """首行 → (物种显示名, 道具显示名|None)。兼容昵称与性别标注。"""
    species, _, item = line.partition(" @ ")
    item = item.strip() or None
    s = species.strip()
    while True:  # 逐层剥括号："Nick (Pikachu) (M)" → "Pikachu"
        m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", s)
        if not m:
            break
        head, inner = m.group(1), m.group(2).strip()
        if inner in ("M", "F"):
            s = head            # 性别标注，丢弃
        elif head:
            s = inner           # 昵称 (Species) → 取括号内物种名
        else:
            break
    return s.strip(), item


def parse_paste(text: str, *, default_level: int = 100) -> list[dict]:
    """整段导出串 → members（slug 化、未过 validator）。失败抛 ImportParseError。"""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text.strip()) if b.strip()]
    if not blocks:
        raise ImportParseError("内容为空：请粘贴 Showdown 队伍导出串")

    conn = _connect()
    errors: list[str] = []
    members: list[dict] = []
    try:
        for bi, block in enumerate(blocks, 1):
            tag = f"第{bi}只"
            lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
            if not lines:
                continue
            sp_name, item_name = _split_species_line(lines[0])
            sp = _resolve(conn, "species", sp_name)
            if not sp:
                errors.append(f"{tag}：不认识的宝可梦 {sp_name!r}")
                continue
            m: dict = {"species": sp, "level": default_level,
                       "moves": [], "evs": {}, "ivs": {}}
            if item_name:
                it = _resolve(conn, "items", item_name)
                if it:
                    m["item"] = it
                else:
                    errors.append(f"{tag}：不认识的道具 {item_name!r}")
            for ln in lines[1:]:
                low = ln.lower()
                if ln.startswith("- "):
                    mv = _resolve(conn, "moves", ln[2:].strip())
                    if mv:
                        m["moves"].append(mv)
                    else:
                        errors.append(f"{tag}：不认识的招式 {ln[2:].strip()!r}")
                elif low.startswith("ability:"):
                    ab = _resolve(conn, "abilities", ln.split(":", 1)[1].strip())
                    if ab:
                        m["ability"] = ab
                    else:
                        errors.append(f"{tag}：不认识的特性 {ln.split(':', 1)[1].strip()!r}")
                elif low.startswith("level:"):
                    try:
                        m["level"] = int(ln.split(":", 1)[1].strip())
                    except ValueError:
                        errors.append(f"{tag}：等级无法解析 {ln!r}")
                elif low.startswith("tera type:"):
                    m["tera_type"] = ln.split(":", 1)[1].strip().title()
                elif low.startswith("evs:"):
                    m["evs"] = _parse_stats(ln.split(":", 1)[1], tag + " EV", errors)
                elif low.startswith("ivs:"):
                    m["ivs"] = _parse_stats(ln.split(":", 1)[1], tag + " IV", errors)
                elif low.endswith(" nature"):
                    na = _resolve(conn, "natures", ln[:-7].strip())
                    if na:
                        m["nature"] = na
                    else:
                        errors.append(f"{tag}：不认识的性格 {ln[:-7].strip()!r}")
                elif low.startswith(_KNOWN_PREFIX):
                    pass  # shiny/happiness 等无关注释行
                else:
                    errors.append(f"{tag}：无法识别的行 {ln!r}")
            members.append(m)
    finally:
        conn.close()

    if errors:
        raise ImportParseError("\n".join(errors))
    if len(members) > 6:
        raise ImportParseError(f"解析出 {len(members)} 只，超过队伍上限 6 只")
    return members
