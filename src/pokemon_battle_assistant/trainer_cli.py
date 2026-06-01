"""Trainer template creation and management.

Provides the implementation behind `pba team ...`. Kept as an importable package
module so the unified CLI can call it directly instead of loading it from the
scripts directory at runtime.
"""

from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path

from .showdown_db import (
    get_learnable_moves,
    get_natures,
    get_pokemon_abilities,
    search_items,
    search_moves,
    search_pokemon,
)
from .team_converter import template_to_showdown_text
from .translation import (
    translate_ability,
    translate_item,
    translate_move,
    translate_pokemon,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRAINERS_DIR = PROJECT_ROOT / "data" / "trainers"
TRAINERS_DIR.mkdir(parents=True, exist_ok=True)

STAT_NAMES = {"hp": "HP", "atk": "攻击", "def": "防御", "spa": "特攻", "spd": "特防", "spe": "速度"}
STAT_ORDER = ["hp", "atk", "def", "spa", "spd", "spe"]
TYPE_LIST = [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison",
    "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
]
DEFAULT_VGC_FORMAT = "gen9vgc2026regi"
FORMAT_PRESETS = [
    (DEFAULT_VGC_FORMAT, "VGC 2026 Regulation I（推荐，双打 6 选 4，50 级，公开队表）"),
    ("gen9doublesou", "Gen 9 Doubles OU（Smogon 双打 6v6）"),
    ("gen9ou", "Gen 9 OU（单打 6v6，兼容旧队伍）"),
]


def available_trainer_names() -> list[str]:
    return sorted(path.stem for path in TRAINERS_DIR.glob("*.json"))


def resolve_trainer_path(name_or_path: str) -> Path:
    """Accept either a friendly team name or a JSON path."""
    candidate = Path(name_or_path)
    if candidate.exists():
        return candidate
    if candidate.suffix == ".json" and len(candidate.parts) == 1:
        trainer_candidate = TRAINERS_DIR / candidate.name
        if trainer_candidate.exists():
            return trainer_candidate
    if candidate.suffix == ".json":
        return candidate
    return TRAINERS_DIR / f"{name_or_path}.json"


def print_missing_template(name_or_path: str) -> None:
    print(f"模版不存在：{name_or_path}")
    names = available_trainer_names()
    if not names:
        print("当前还没有队伍。可以先运行：pba team create")
        return

    close = difflib.get_close_matches(Path(name_or_path).stem, names, n=3, cutoff=0.35)
    if close:
        print("你是不是想用：")
        for name in close:
            print(f"  - {name}")
    print("已有队伍：")
    print("  " + ", ".join(names))


def cmd_list(args: argparse.Namespace) -> None:
    files = sorted(TRAINERS_DIR.glob("*.json"))
    if not files:
        print("没有找到训练家模版。使用 create 子命令创建。")
        return
    print(f"{'名称':<25} {'队伍名':<25} {'格式':<15} {'宝可梦数'}")
    print("-" * 75)
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            team_name = data.get("name", "?")
            fmt = data.get("format", "?")
            count = len(data.get("team", []))
            print(f"{f.stem:<25} {team_name:<25} {fmt:<15} {count}")
        except (json.JSONDecodeError, KeyError):
            print(f"{f.stem:<25} (读取失败)")


def cmd_show(args: argparse.Namespace) -> None:
    path = resolve_trainer_path(args.name)
    if not path.exists():
        print_missing_template(args.name)
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"队伍名：{data.get('name', '?')}")
    print(f"对战格式：{data.get('format', '?')}")
    print(f"宝可梦数：{len(data.get('team', []))}")
    print()

    for i, mon in enumerate(data.get("team", []), 1):
        species = mon["species"]
        zh_name = translate_pokemon(species)
        label = f"{zh_name}（{species}）" if zh_name != species else species
        print(f"--- {i}. {label} ---")

        if mon.get("nickname"):
            print(f"  昵称：{mon['nickname']}")
        if mon.get("item"):
            zh_item = translate_item(mon["item"])
            print(f"  道具：{zh_item}（{mon['item']}）")
        if mon.get("ability"):
            zh_ability = translate_ability(mon["ability"])
            print(f"  特性：{zh_ability}（{mon['ability']}）")
        if mon.get("nature"):
            print(f"  性格：{mon['nature']}")
        if mon.get("tera_type"):
            print(f"  太晶属性：{mon['tera_type']}")
        print(f"  等级：{mon.get('level', 100)}")

        evs = mon.get("evs", {})
        ev_parts = [f"{STAT_NAMES[k]}:{evs.get(k, 0)}" for k in STAT_ORDER if evs.get(k, 0) != 0]
        if ev_parts:
            ev_total = sum(evs.get(k, 0) for k in STAT_ORDER)
            print(f"  努力值：{', '.join(ev_parts)}（合计 {ev_total}）")

        ivs = mon.get("ivs", {})
        iv_parts = [f"{STAT_NAMES[k]}:{ivs.get(k, 31)}" for k in STAT_ORDER if ivs.get(k, 31) != 31]
        if iv_parts:
            print(f"  个体值：{', '.join(iv_parts)}")

        moves = mon.get("moves", [])
        if moves:
            move_strs = [f"{translate_move(m)}（{m}）" for m in moves]
            print(f"  招式：{', '.join(move_strs)}")
        print()


def cmd_preview(args: argparse.Namespace) -> None:
    path = resolve_trainer_path(args.name)
    if not path.exists():
        print_missing_template(args.name)
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    print(template_to_showdown_text(data))


def input_with_default(prompt: str, default: str = "") -> str:
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()


def print_vgc_builder_intro() -> None:
    print("VGC 双打建队提示：")
    print("- 当前默认规则是 gen9vgc2026regi：带 4-6 只，实战 6 选 4，前两只是首发。")
    print("- VGC 有 Item Clause：道具不能重复。")
    print("- 大多数宝可梦建议考虑 Protect / 速度控制 / 支援动作，不要直接照搬单打队。")
    print("- 建完后请运行：pba team validate <队伍名> --format gen9vgc2026regi")
    print()


def input_battle_format() -> str:
    print("选择对战规则：")
    for idx, (fmt, desc) in enumerate(FORMAT_PRESETS, 1):
        print(f"  {idx}. {fmt} - {desc}")
    raw = input_with_default("规则编号或直接输入 format", "1").strip()
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(FORMAT_PRESETS):
            return FORMAT_PRESETS[idx][0]
    return raw or DEFAULT_VGC_FORMAT


def input_search_select(category: str, search_fn, prompt: str) -> str | None:
    zh_category_map = {"宝可梦": "pokemon", "招式": "moves", "道具": "items"}
    zh_cat = zh_category_map.get(category, "")
    while True:
        query = input(f"{prompt}（输入中英文关键词搜索，留空跳过）: ").strip()
        if not query:
            return None
        results = search_fn(query, limit=10)
        if not results:
            print(f"  未找到匹配的{category}，请重新输入。")
            continue
        print(f"  搜索结果：")
        for idx, r in enumerate(results, 1):
            zh_name = ""
            if zh_cat == "pokemon":
                zh_name = translate_pokemon(r.get("id", r["name"]))
            elif zh_cat == "moves":
                zh_name = translate_move(r.get("id", r["name"]))
            elif zh_cat == "items":
                zh_name = translate_item(r.get("id", r["name"]))
            zh_label = f"（{zh_name}）" if zh_name and zh_name != r["name"] else ""
            extra = ""
            if category == "招式":
                extra = f" [{r.get('type', '?')}, 威力:{r.get('basePower', '?')}, {r.get('category', '?')}]"
            elif category == "宝可梦":
                types = "/".join(r.get("types", []))
                stats = r.get("baseStats", {})
                bst = sum(stats.values()) if stats else 0
                extra = f" [{types}, 种族值:{bst}]"
            print(f"    {idx}. {r['name']}{zh_label}{extra}")
        choice = input(f"  选择编号（1-{len(results)}），或直接输入名称: ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                return results[idx]["name"]
        elif choice:
            return choice
        print("  无效选择，请重新操作。")


def input_evs() -> dict[str, int]:
    print("  输入努力值（每项 0-252，总和 ≤ 510）。留空 = 0。")
    evs: dict[str, int] = {}
    total = 0
    for stat in STAT_ORDER:
        val_str = input(f"    {STAT_NAMES[stat]} EV: ").strip()
        val = int(val_str) if val_str else 0
        val = max(0, min(252, val))
        if total + val > 510:
            val = 510 - total
            print(f"    已达上限，自动调整为 {val}")
        evs[stat] = val
        total += val
    print(f"  努力值合计：{total}/510")
    return evs


def input_ivs() -> dict[str, int]:
    print("  输入个体值（每项 0-31）。留空 = 31。")
    ivs: dict[str, int] = {}
    for stat in STAT_ORDER:
        val_str = input(f"    {STAT_NAMES[stat]} IV: ").strip()
        val = int(val_str) if val_str else 31
        ivs[stat] = max(0, min(31, val))
    return ivs


def create_one_pokemon(index: int, *, battle_format: str = DEFAULT_VGC_FORMAT, used_items: set[str] | None = None) -> dict | None:
    print(f"\n=== 添加第 {index} 只宝可梦 ===")
    is_vgc = "vgc" in battle_format.lower()

    species = input_search_select("宝可梦", search_pokemon, "宝可梦名称")
    if not species:
        return None

    nickname = input("  昵称（留空跳过）: ").strip()

    abilities = get_pokemon_abilities(species.lower().replace(" ", "").replace("-", ""))
    ability = ""
    if abilities:
        print(f"  可用特性：")
        for idx, ab in enumerate(abilities, 1):
            zh = translate_ability(ab)
            print(f"    {idx}. {ab}（{zh}）")
        choice = input(f"  选择编号（1-{len(abilities)}），或直接输入: ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(abilities):
                ability = abilities[idx]
        elif choice:
            ability = choice
    else:
        ability = input("  特性（直接输入名称）: ").strip()

    item = input_search_select("道具", search_items, "道具")
    if item is None:
        item = ""
    if is_vgc and item and used_items is not None and item in used_items:
        print(f"  ⚠️ VGC 通常不允许重复道具：{item} 已经被队伍中其他宝可梦使用。")
        print("  建议更换道具；如果继续保存，validate 时 Showdown 会判定是否合法。")

    natures = get_natures()
    print("  可用性格：")
    nature_list = list(natures.values())
    for idx, n in enumerate(nature_list, 1):
        plus = n.get("plus", "-")
        minus = n.get("minus", "-")
        desc = f"+{STAT_NAMES.get(plus, plus)}/-{STAT_NAMES.get(minus, minus)}" if plus != "-" else "无增减"
        print(f"    {idx:2}. {n['name']:<10} {desc}")
    nature_choice = input("  选择编号或输入性格名: ").strip()
    nature = ""
    if nature_choice.isdigit():
        idx = int(nature_choice) - 1
        if 0 <= idx < len(nature_list):
            nature = nature_list[idx]["name"]
    elif nature_choice:
        nature = nature_choice

    print(f"  可用属性：{', '.join(TYPE_LIST)}")
    tera_type = input("  太晶属性（留空跳过）: ").strip()

    level_str = input_with_default("  等级", "100")
    level = int(level_str) if level_str.isdigit() else 100

    species_id = species.lower().replace(" ", "").replace("-", "")
    learnable = get_learnable_moves(species_id)
    if learnable:
        print(f"  该宝可梦 Gen9 可学招式共 {len(learnable)} 个。")
        show = input("  是否显示可学招式列表？(y/n) [n]: ").strip().lower()
        if show == "y":
            for i in range(0, len(learnable), 4):
                row = learnable[i : i + 4]
                print(f"    {'  '.join(f'{m:<20}' for m in row)}")

    moves: list[str] = []
    for mi in range(1, 5):
        move = input_search_select("招式", search_moves, f"第 {mi} 个招式")
        if move:
            moves.append(move)
        else:
            break

    evs = input_evs()
    ivs = input_ivs()

    mon = {
        "species": species,
        "item": item,
        "ability": ability,
        "nature": nature,
        "tera_type": tera_type,
        "level": level,
        "evs": evs,
        "ivs": ivs,
        "moves": moves,
    }
    if nickname:
        mon["nickname"] = nickname
    if is_vgc and moves and not any(m.lower().replace(" ", "").replace("-", "") == "protect" for m in moves):
        print("  提醒：这只宝可梦没有 Protect。VGC 不一定必须带，但建议确认你有明确理由。")
    return mon


def cmd_create(args: argparse.Namespace) -> None:
    print("=== 创建训练家模版 ===\n")
    print_vgc_builder_intro()
    team_name = input("队伍名称: ").strip()
    if not team_name:
        print("名称不能为空。")
        return

    file_name = input_with_default("文件名（不含 .json）", team_name.lower().replace(" ", "_"))
    battle_format = input_battle_format()

    team: list[dict] = []
    used_items: set[str] = set()
    for i in range(1, 7):
        mon = create_one_pokemon(i, battle_format=battle_format, used_items=used_items)
        if mon:
            team.append(mon)
            if mon.get("item"):
                used_items.add(mon["item"])
        if i < 6 and mon:
            default_more = "y" if len(team) < 4 else "n"
            prompt = "继续添加宝可梦？"
            if "vgc" in battle_format.lower() and len(team) < 4:
                prompt += "（VGC 至少建议先满 4 只）"
            more = input(f"\n{prompt}(y/n) [{default_more}]: ").strip().lower() or default_more
            if more == "n":
                break

    if not team:
        print("未添加任何宝可梦，放弃创建。")
        return

    template = {"name": team_name, "format": battle_format, "team": team}

    out_path = TRAINERS_DIR / f"{file_name}.json"
    if out_path.exists():
        overwrite = input(f"\n文件已存在：{out_path.name}，是否覆盖？(y/n) [n]: ").strip().lower()
        if overwrite != "y":
            print("取消保存。")
            return
    out_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n模版已保存到：{out_path}")
    print(f"包含 {len(team)} 只宝可梦。")
    if "vgc" in battle_format.lower():
        print("\n下一步建议：")
        print(f"  pba team validate {out_path.stem} --format {battle_format}")
        print(f"  pba battle {out_path.stem} --format {battle_format} --select manual")
    print(f"\n预览 Showdown 格式：")
    print(template_to_showdown_text(template))


def cmd_delete(args: argparse.Namespace) -> None:
    path = resolve_trainer_path(args.name)
    if not path.exists():
        print_missing_template(args.name)
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    team_name = data.get("name", args.name)
    count = len(data.get("team", []))
    print(f"即将删除：{team_name}（{count} 只宝可梦）")
    confirm = input("确认删除？(y/n) [n]: ").strip().lower()
    if confirm == "y":
        path.unlink()
        print(f"已删除：{path}")
    else:
        print("取消删除。")


def main() -> None:
    parser = argparse.ArgumentParser(description="训练家模版管理工具")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="列出所有训练家模版")

    show_p = sub.add_parser("show", help="显示模版详情")
    show_p.add_argument("name", help="模版名或 JSON 路径")

    preview_p = sub.add_parser("preview", help="输出 Showdown 文本格式")
    preview_p.add_argument("name", help="模版名或 JSON 路径")

    sub.add_parser("create", help="交互式创建新模版")

    delete_p = sub.add_parser("delete", help="删除训练家模版")
    delete_p.add_argument("name", help="模版名或 JSON 路径")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "preview":
        cmd_preview(args)
    elif args.command == "create":
        cmd_create(args)
    elif args.command == "delete":
        cmd_delete(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
