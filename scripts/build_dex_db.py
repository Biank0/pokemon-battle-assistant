#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建 dex.db —— 基础信息库（只读）

数据源：
  1. data/dex/showdown_db.json          宝可梦/招式/特性/道具/可学招式/性格
  2. data/dex/translations/zh_cn_names.json   中文名
  3. pokemon-showdown/data/typechart.ts  属性相克表（从引擎本体解析，权威源）

产出：data/dex/dex.db（表结构见 data/dex/schema.sql，字段讲解见 docs/dex_db_schema.md）

用法：
  python scripts/build_dex_db.py            # 构建（已存在则整库重建）
"""
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEX_DIR = ROOT / "data" / "dex"
DB_PATH = DEX_DIR / "dex.db"
SCHEMA_PATH = DEX_DIR / "schema.sql"
SHOWDOWN_DB = DEX_DIR / "showdown_db.json"
TRANSLATIONS = DEX_DIR / "translations" / "zh_cn_names.json"
TYPECHART_TS = ROOT / "pokemon-showdown" / "data" / "typechart.ts"

SCHEMA_VERSION = "2"


def slugify(name: str) -> str:
    """显示名 → dex 官方 slug（小写+去非字母数字）。"""
    return re.sub(r"[^a-z0-9]", "", name.lower())

# 18 个标准属性（Gen9）
TYPES_18 = {
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
}

# 25 性格中文名 —— 官方译名（翻译数据源无性格条目，固定映射）
NATURE_ZH = {
    "hardy": "勤奋", "lonely": "怕寂寞", "brave": "勇敢", "adamant": "固执",
    "naughty": "顽皮", "bold": "大胆", "docile": "温顺", "relaxed": "悠闲",
    "impish": "淘气", "lax": "乐天", "timid": "胆小", "hasty": "急躁",
    "serious": "认真", "jolly": "爽朗", "naive": "天真", "modest": "内敛",
    "mild": "马虎", "quiet": "安静", "rash": "浮躁", "calm": "冷静",
    "gentle": "温和", "sassy": "自大", "careful": "慎重", "quirky": "无谋",
    "bashful": "害羞",
}

# Showdown damageTaken 编码 → 实际倍率
# 0=1倍 1=2倍(克制) 2=0.5倍(抵抗) 3=0(免疫)
CODE_TO_MULT = {0: 1.0, 1: 2.0, 2: 0.5, 3: 0.0}


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_typechart(ts_text: str) -> list[tuple[str, str, float]]:
    """解析 typechart.ts，返回 [(atk_type, def_type, multiplier)] 非 1 倍组合。

    源格式（防御属性为小写 key，damageTaken 内为 攻击属性: 编码）：
        bug: {
            damageTaken: { Fighting: 1, Fire: 1, Grass: 2, ... },
        }
    过滤：prankster（非属性）、Stellar（对相克无信息量）。
    """
    # 匹配每个 "防御属性: { damageTaken: {...} }" 块
    block_re = re.compile(r"(\w+):\s*\{\s*damageTaken:\s*\{([^}]*)\}", re.S)
    rows: list[tuple[str, str, float]] = []
    for def_key, body in block_re.findall(ts_text):
        def_type = def_key.capitalize()  # bug -> Bug
        for atk_type, code in re.findall(r"(\w+):\s*(\d)", body):
            if atk_type not in TYPES_18:
                continue  # 跳过 prankster / Stellar
            mult = CODE_TO_MULT[int(code)]
            if mult != 1.0:  # 只存非 1 倍组合（查不到即 1 倍）
                rows.append((atk_type, def_type, mult))
    return rows


def main() -> int:
    # Windows 控制台中文输出防乱码
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # ---------- 读源 ----------
    for p in (SCHEMA_PATH, SHOWDOWN_DB, TRANSLATIONS, TYPECHART_TS):
        if not p.exists():
            print(f"[错误] 缺少数据源: {p}")
            return 1

    db = load_json(SHOWDOWN_DB)
    zh = load_json(TRANSLATIONS)  # metadata + pokemon/moves/items/abilities 四个中文名字典

    pokedex = db["pokedex"]
    moves_src = db["moves"]
    items_src = db["items"]
    abilities_src = db["abilities"]
    learnsets_src = db["learnsets"]
    natures_src = db["natures"]

    zh_pokemon = zh.get("pokemon", {})
    zh_moves = zh.get("moves", {})
    zh_items = zh.get("items", {})
    zh_abilities = zh.get("abilities", {})

    print(f"[源] pokedex={len(pokedex)} moves={len(moves_src)} items={len(items_src)} "
          f"abilities={len(abilities_src)} learnsets={len(learnsets_src)} natures={len(natures_src)}")
    print(f"[源] 中文翻译: pokemon={len(zh_pokemon)} moves={len(zh_moves)} "
          f"items={len(zh_items)} abilities={len(zh_abilities)}")

    # ---------- 建库 ----------
    if DB_PATH.exists():
        print(f"[建库] {DB_PATH} 已存在，整库重建")
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    # ---------- species ----------
    species_rows = []
    skipped = []
    for sid, d in pokedex.items():
        stats = d.get("baseStats")
        if not stats or not d.get("types"):
            skipped.append(sid)  # 无种族值/属性的占位形态，不可对战，跳过
            continue
        t = d["types"]
        bst = sum(stats[k] for k in ("hp", "atk", "def", "spa", "spd", "spe"))
        species_rows.append((
            sid, d.get("num"), d.get("name"), zh_pokemon.get(sid),
            t[0], t[1] if len(t) > 1 else None,
            stats["hp"], stats["atk"], stats["def"], stats["spa"], stats["spd"], stats["spe"], bst,
            d.get("weightkg"), d.get("heightm"),
            json.dumps(d.get("abilities", {}), ensure_ascii=False),
            d.get("prevo"),
            json.dumps(d.get("evos", []), ensure_ascii=False),
            json.dumps(d["genderRatio"], ensure_ascii=False) if d.get("genderRatio") else None,
            slugify(d["baseSpecies"]) if d.get("baseSpecies") else None,  # 形态→基础（learnsets 回退用）
        ))
    conn.executemany(
        "INSERT INTO species (id,num,name_en,name_zh,type1,type2,hp,atk,def,spa,spd,spe,bst,"
        "weight_kg,height_m,abilities,prevo,evos,gender_ratio,base_species) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        species_rows,
    )
    if skipped:
        print(f"[species] 跳过 {len(skipped)} 条无种族值条目: {skipped[:5]}{'...' if len(skipped) > 5 else ''}")

    # ---------- moves ----------
    move_rows = []
    for mid, d in moves_src.items():
        acc = d.get("accuracy")
        if acc is True:      # Showdown 用 true 表示必中
            acc = None
        elif isinstance(acc, (int, float)):
            acc = int(acc)
        flags = d.get("flags")
        move_rows.append((
            mid, d.get("num"), d.get("name"), zh_moves.get(mid),
            d.get("type"), d.get("category"), int(d.get("basePower", 0) or 0),
            acc, d.get("pp"), int(d.get("priority", 0) or 0),
            d.get("target"),
            json.dumps(flags, ensure_ascii=False) if flags else None,
        ))
    conn.executemany(
        "INSERT INTO moves (id,num,name_en,name_zh,type,category,base_power,accuracy,pp,priority,target,flags) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        move_rows,
    )

    # ---------- abilities ----------
    conn.executemany(
        "INSERT INTO abilities (id,num,name_en,name_zh,rating) VALUES (?,?,?,?,?)",
        [(aid, d.get("num"), d.get("name"), zh_abilities.get(aid), d.get("rating"))
         for aid, d in abilities_src.items()],
    )

    # ---------- items ----------
    conn.executemany(
        "INSERT INTO items (id,num,name_en,name_zh,gen,fling_power) VALUES (?,?,?,?,?,?)",
        [(iid, d.get("num"), d.get("name"), zh_items.get(iid), d.get("gen"),
          (d.get("fling") or {}).get("basePower"))
         for iid, d in items_src.items()],
    )

    # ---------- learnsets ----------
    learnset_rows = []
    for sid, d in learnsets_src.items():
        for mid, methods in d.get("learnset", {}).items():
            learnset_rows.append((sid, mid, json.dumps(methods, ensure_ascii=False)))
    conn.executemany(
        "INSERT OR IGNORE INTO learnsets (species_id,move_id,methods) VALUES (?,?,?)",
        learnset_rows,
    )

    # ---------- natures ----------
    conn.executemany(
        "INSERT INTO natures (id,name_en,name_zh,plus_stat,minus_stat) VALUES (?,?,?,?,?)",
        [(nid, d.get("name"), NATURE_ZH.get(nid), d.get("plus"), d.get("minus"))
         for nid, d in natures_src.items()],
    )

    # ---------- type_chart ----------
    tc_rows = parse_typechart(TYPECHART_TS.read_text(encoding="utf-8"))
    conn.executemany(
        "INSERT INTO type_chart (atk_type,def_type,multiplier) VALUES (?,?,?)",
        tc_rows,
    )

    # ---------- meta ----------
    meta_rows = [
        ("schema_version", SCHEMA_VERSION),
        ("source_db_generated_at", db.get("metadata", {}).get("generated_at", "unknown")),
        ("translation_source", zh.get("metadata", {}).get("source", "unknown")),
        ("imported_at", datetime.now(timezone.utc).isoformat(timespec="seconds")),
    ]
    conn.executemany("INSERT INTO meta (key,value) VALUES (?,?)", meta_rows)

    conn.commit()

    # ---------- 校验对账 ----------
    print("\n========== 构建结果 ==========")
    counts = {}
    for table in ("species", "moves", "abilities", "items", "learnsets", "natures", "type_chart"):
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<12} {counts[table]:>7} 行")

    def coverage(table: str) -> str:
        total, has_zh = conn.execute(
            f"SELECT COUNT(*), COUNT(name_zh) FROM {table}").fetchone()
        return f"{has_zh}/{total} ({has_zh * 100 // total}%)"

    print("\n---------- 中文名覆盖率 ----------")
    for table in ("species", "moves", "abilities", "items"):
        print(f"  {table:<12} {coverage(table)}")

    print("\n---------- 抽样核对 ----------")
    sample = conn.execute(
        "SELECT id,name_zh,type1,type2,spa,spe,bst FROM species WHERE id='charizard'").fetchone()
    print(f"  species  喷火龙: {sample}")
    sample = conn.execute(
        "SELECT id,name_zh,type,category,base_power FROM moves WHERE id='flamethrower'").fetchone()
    print(f"  moves    喷射火焰: {sample}")
    sample = conn.execute(
        "SELECT id,name_zh FROM abilities WHERE id='intimidate'").fetchone()
    print(f"  abilities 威吓: {sample}")
    sample = conn.execute(
        "SELECT id,name_zh FROM items WHERE id='leftovers'").fetchone()
    print(f"  items    吃剩的东西: {sample}")
    sample = conn.execute(
        "SELECT id,name_zh,plus_stat,minus_stat FROM natures WHERE id='adamant'").fetchone()
    print(f"  natures  固执: {sample}")
    q = lambda sql: conn.execute(sql).fetchone()
    can_learn = q("SELECT 1 FROM learnsets WHERE species_id='charizard' AND move_id='flamethrower'") is not None
    fire_grass = q("SELECT multiplier FROM type_chart WHERE atk_type='Fire' AND def_type='Grass'")[0]
    gnd_fly = q("SELECT multiplier FROM type_chart WHERE atk_type='Ground' AND def_type='Flying'")[0]
    nrm_steel = q("SELECT multiplier FROM type_chart WHERE atk_type='Normal' AND def_type='Steel'")[0]
    immune_cnt = conn.execute("SELECT COUNT(*) FROM type_chart WHERE multiplier=0").fetchone()[0]
    print(f"  learnset 喷火龙会喷射火焰: {can_learn}")
    print(f"  相克     火攻草(克制): {fire_grass}")
    print(f"  相克     地面攻飞行(免疫): {gnd_fly}")
    print(f"  相克     一般攻钢(抵抗): {nrm_steel}")
    print(f"  相克     免疫组合总数: {immune_cnt} (Gen6+ 标准值 8)")

    # ---------- 收尾：单文件交付 ----------
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.commit()
    conn.close()
    print(f"\n[完成] {DB_PATH} ({DB_PATH.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
