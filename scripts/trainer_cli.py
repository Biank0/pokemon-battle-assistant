"""CLI tool for creating and managing trainer templates.

Usage:
    PYTHONPATH=src python scripts/trainer_cli.py list
    PYTHONPATH=src python scripts/trainer_cli.py show example_team
    PYTHONPATH=src python scripts/trainer_cli.py preview example_team
    PYTHONPATH=src python scripts/trainer_cli.py create
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pokemon_battle_assistant.showdown_db import (
    get_learnable_moves,
    get_natures,
    get_pokemon_abilities,
    search_items,
    search_moves,
    search_pokemon,
)
from pokemon_battle_assistant.team_converter import template_to_showdown_text
from pokemon_battle_assistant.translation import (
    translate_ability,
    translate_item,
    translate_move,
    translate_pokemon,
)

TRAINERS_DIR = PROJECT_ROOT / "data" / "trainers"
TRAINERS_DIR.mkdir(parents=True, exist_ok=True)

STAT_NAMES = {"hp": "HP", "atk": "攻击", "def": "防御", "spa": "特攻", "spd": "特防", "spe": "速度"}
STAT_ORDER = ["hp", "atk", "def", "spa", "spd", "spe"]
TYPE_LIST = [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison",
    "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
]


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
    path = TRAINERS_DIR / f"{args.name}.json"
    if not path.exists():
        print(f"模版不存在：{path}")
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
    path = TRAINERS_DIR / f"{args.name}.json"
    if not path.exists():
        print(f"模版不存在：{path}")
        return

    data = json.loads(path.read_text(encoding="utf-8"))
    print(template_to_showdown_text(data))


def input_with_default(prompt: str, default: str = "") -> str:
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()


def input_search_select(category: str, search_fn, prompt: str) -> str | None:
    while True:
        query = input(f"{prompt}（输入关键词搜索，留空跳过）: ").strip()
        if not query:
            return None
        results = search_fn(query, limit=10)
        if not results:
            print(f"  未找到匹配的{category}，请重新输入。")
            continue
        print(f"  搜索结果：")
        for idx, r in enumerate(results, 1):
            extra = ""
            if category == "招式":
                extra = f" ({r.get('type', '?')}, 威力:{r.get('basePower', '?')}, {r.get('category', '?')})"
            elif category == "宝可梦":
                types = "/".join(r.get("types", []))
                stats = r.get("baseStats", {})
                bst = sum(stats.values()) if stats else 0
                extra = f" ({types}, 种族值:{bst})"
            print(f"    {idx}. {r['name']}{extra}")
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


def create_one_pokemon(index: int) -> dict | None:
    print(f"\n=== 添加第 {index} 只宝可梦 ===")

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
    return mon


def cmd_create(args: argparse.Namespace) -> None:
    print("=== 创建训练家模版 ===\n")
    team_name = input("队伍名称: ").strip()
    if not team_name:
        print("名称不能为空。")
        return

    file_name = input_with_default("文件名（不含 .json）", team_name.lower().replace(" ", "_"))
    battle_format = input_with_default("对战格式", "gen9ou")

    team: list[dict] = []
    for i in range(1, 7):
        mon = create_one_pokemon(i)
        if mon:
            team.append(mon)
        if i < 6 and mon:
            more = input(f"\n继续添加宝可梦？(y/n) [y]: ").strip().lower()
            if more == "n":
                break

    if not team:
        print("未添加任何宝可梦，放弃创建。")
        return

    template = {"name": team_name, "format": battle_format, "team": team}

    out_path = TRAINERS_DIR / f"{file_name}.json"
    out_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n模版已保存到：{out_path}")
    print(f"包含 {len(team)} 只宝可梦。")
    print(f"\n预览 Showdown 格式：")
    print(template_to_showdown_text(template))


def main() -> None:
    parser = argparse.ArgumentParser(description="训练家模版管理工具")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="列出所有训练家模版")

    show_p = sub.add_parser("show", help="显示模版详情")
    show_p.add_argument("name", help="模版文件名（不含 .json）")

    preview_p = sub.add_parser("preview", help="输出 Showdown 文本格式")
    preview_p.add_argument("name", help="模版文件名（不含 .json）")

    sub.add_parser("create", help="交互式创建新模版")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "preview":
        cmd_preview(args)
    elif args.command == "create":
        cmd_create(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
