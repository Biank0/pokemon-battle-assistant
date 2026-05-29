"""Unified CLI entry point for Pokemon Battle Assistant.

Usage:
    pba team list
    pba team show <name>
    pba team create
    pba team preview <name>
    pba team delete <name>
    pba battle <template> [--opponent <template>] [--format <format>]
    pba random-battle [--format <format>]
    pba analyze <battle_state.json> [--top N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

TRAINERS_DIR = PROJECT_ROOT / "data" / "trainers"
TRAINERS_DIR.mkdir(parents=True, exist_ok=True)


def cmd_team(args: argparse.Namespace) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("trainer_cli", PROJECT_ROOT / "scripts" / "trainer_cli.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if args.team_action == "list":
        mod.cmd_list(args)
    elif args.team_action == "show":
        mod.cmd_show(args)
    elif args.team_action == "preview":
        mod.cmd_preview(args)
    elif args.team_action == "create":
        mod.cmd_create(args)
    elif args.team_action == "delete":
        mod.cmd_delete(args)


def cmd_battle(args: argparse.Namespace) -> None:
    from pokemon_battle_assistant.environment import BattleRunConfig, BattleRunner
    from pokemon_battle_assistant.team_converter import template_to_showdown_text
    from pokemon_battle_assistant.translation import translate_pokemon

    def load_template(path: str) -> dict:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    p1_template = load_template(args.template)
    p1_team_text = template_to_showdown_text(p1_template)
    p1_source = args.template

    if args.opponent:
        p2_template = load_template(args.opponent)
        p2_team_text = template_to_showdown_text(p2_template)
        p2_source = args.opponent
    else:
        p2_team_text = p1_team_text
        p2_source = p1_source

    battle_format = args.format or p1_template.get("format", "gen9ou")

    async def run() -> None:
        print("# 对战运行前配置")
        print(f"battle_format: {battle_format}")
        print("server: local Pokémon Showdown, ws://localhost:8000/showdown/websocket")
        print(f"player_1_template: {p1_source}")
        print(f"player_2_template: {p2_source}")
        print(f"player_1_control: {args.player1_control}")
        print(f"player_2_control: {args.player2_control}")
        print("note: 第一阶段只运行和记录环境，不开发助手或策略。")
        print()

        config = BattleRunConfig(
            battle_format=battle_format,
            player_1_team=p1_team_text,
            player_2_team=p2_team_text,
            player_1_source=p1_source,
            player_2_source=p2_source,
            player_1_control=args.player1_control,
            player_2_control=args.player2_control,
            metadata={"entrypoint": "pba battle"},
        )
        result = await BattleRunner().run(config)
        battle = result.record["battle"]

        print("# 对战结束摘要")
        print(f"battle_tag: {battle['battle_tag']}")
        print(f"format: {battle['format']}")
        print(f"turns: {battle['turns']}")
        print(f"winner_side: {'player_1' if battle['won'] else 'player_2'}")
        print("player_1_team:", [translate_pokemon(mon["species"]) for mon in battle["team"]])
        print("player_2_team:", [translate_pokemon(mon["species"]) for mon in battle["opponent_team"]])
        print(f"environment_steps: {len(result.record.get('steps', []))}")
        print()
        print("# 文件已导出")
        print(f"replay_html: {result.replay_path}")
        print(f"record_json: {result.record_path}")
        print(f"report_md: {result.report_path}")
        print(f"steps_jsonl: {result.steps_path}")

    asyncio.run(run())


def cmd_random_battle(args: argparse.Namespace) -> None:
    from pokemon_battle_assistant.environment import BattleRunConfig, BattleRunner
    from pokemon_battle_assistant.translation import translate_pokemon

    battle_format = args.format

    async def run() -> None:
        print("# 随机对战运行前配置")
        print(f"battle_format: {battle_format}")
        print("server: local Pokémon Showdown, ws://localhost:8000/showdown/websocket")
        print("team_source: Showdown random battle generator")
        print(f"player_1_control: {args.player1_control}")
        print(f"player_2_control: {args.player2_control}")
        print("note: 第一阶段只运行和记录环境，不开发助手或策略。")
        print()

        config = BattleRunConfig(
            battle_format=battle_format,
            player_1_source="Showdown random battle generator",
            player_2_source="Showdown random battle generator",
            player_1_control=args.player1_control,
            player_2_control=args.player2_control,
            metadata={"entrypoint": "pba random-battle"},
        )
        result = await BattleRunner().run(config)
        battle = result.record["battle"]

        print("# 对战结束摘要")
        print(f"battle_tag: {battle['battle_tag']}")
        print(f"format: {battle['format']}")
        print(f"turns: {battle['turns']}")
        print(f"winner_side: {'player_1' if battle['won'] else 'player_2'}")
        print("player_1_team:", [translate_pokemon(mon["species"]) for mon in battle["team"]])
        print("player_2_seen_team:", [translate_pokemon(mon["species"]) for mon in battle["opponent_team"]])
        print(f"environment_steps: {len(result.record.get('steps', []))}")
        print()
        print("# 文件已导出")
        print(f"replay_html: {result.replay_path}")
        print(f"record_json: {result.record_path}")
        print(f"report_md: {result.report_path}")
        print(f"steps_jsonl: {result.steps_path}")

    asyncio.run(run())


def cmd_analyze(args: argparse.Namespace) -> None:
    from pokemon_battle_assistant.evaluator import evaluate_battle
    from pokemon_battle_assistant.explanation import format_analysis
    from pokemon_battle_assistant.models import BattleState

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)
    state = BattleState.from_dict(data)
    evaluations = evaluate_battle(state)
    print(format_analysis(state, evaluations, top_n=args.top))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pba",
        description="Pokemon Battle Assistant — 宝可梦对战助手",
    )
    sub = parser.add_subparsers(dest="command")

    # --- pba team ---
    team_parser = sub.add_parser("team", help="训练家队伍管理")
    team_sub = team_parser.add_subparsers(dest="team_action")

    team_sub.add_parser("list", help="列出所有队伍模版")

    show_p = team_sub.add_parser("show", help="显示队伍详情")
    show_p.add_argument("name", help="模版名（不含 .json）")

    preview_p = team_sub.add_parser("preview", help="预览 Showdown 格式")
    preview_p.add_argument("name", help="模版名（不含 .json）")

    team_sub.add_parser("create", help="交互式创建队伍")

    delete_p = team_sub.add_parser("delete", help="删除队伍")
    delete_p.add_argument("name", help="模版名（不含 .json）")

    # --- pba battle ---
    battle_parser = sub.add_parser("battle", help="使用训练家模版进行对战")
    battle_parser.add_argument("template", help="玩家 1 的模版路径")
    battle_parser.add_argument("--opponent", help="玩家 2 的模版路径（默认与玩家 1 相同）")
    battle_parser.add_argument("--format", help="对战格式（默认从模版读取）")
    battle_parser.add_argument("--player1-control", choices=["random", "manual"], default="random", help="玩家 1 控制方式")
    battle_parser.add_argument("--player2-control", choices=["random", "manual"], default="random", help="玩家 2 控制方式")
    battle_parser.add_argument("--manual", action="store_true", help="快捷方式：等同于 --player1-control manual")

    # --- pba random-battle ---
    random_parser = sub.add_parser("random-battle", help="使用 Showdown 随机队伍进行环境对战")
    random_parser.add_argument(
        "--format",
        default="gen9randombattle",
        help="随机对战格式；双打随机用 gen9randomdoublesbattle",
    )
    random_parser.add_argument("--player1-control", choices=["random", "manual"], default="random", help="玩家 1 控制方式")
    random_parser.add_argument("--player2-control", choices=["random", "manual"], default="random", help="玩家 2 控制方式")
    random_parser.add_argument("--manual", action="store_true", help="快捷方式：等同于 --player1-control manual")

    # --- pba analyze ---
    analyze_parser = sub.add_parser("analyze", help="离线局面分析")
    analyze_parser.add_argument("input", help="对战局面 JSON 文件路径")
    analyze_parser.add_argument("--top", type=int, default=3, help="显示前 N 个推荐操作")

    args = parser.parse_args()

    if getattr(args, "manual", False):
        args.player1_control = "manual"

    if args.command == "team":
        if not args.team_action:
            team_parser.print_help()
        else:
            cmd_team(args)
    elif args.command == "battle":
        cmd_battle(args)
    elif args.command == "random-battle":
        cmd_random_battle(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
