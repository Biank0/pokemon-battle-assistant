"""Unified CLI entry point for Pokemon Battle Assistant.

Usage:
    pba team list
    pba team show <name>
    pba team create
    pba team preview <name>
    pba team delete <name>
    pba team validate <name>
    pba env check
    pba battle <template> [--opponent <template>] [--format <format>]
    pba random-battle [--format <format>]
    pba analyze <battle_state.json> [--top N]
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

TRAINERS_DIR = PROJECT_ROOT / "data" / "trainers"
TRAINERS_DIR.mkdir(parents=True, exist_ok=True)


def available_trainer_names() -> list[str]:
    return sorted(path.stem for path in TRAINERS_DIR.glob("*.json"))


def format_trainer_suggestions(name_or_path: str) -> str:
    names = available_trainer_names()
    if not names:
        return "当前还没有队伍。可以先运行：pba team create"

    close = difflib.get_close_matches(Path(name_or_path).stem, names, n=3, cutoff=0.35)
    lines = []
    if close:
        lines.append("你是不是想用：")
        lines.extend(f"  - {name}" for name in close)
    lines.append("已有队伍：")
    lines.append("  " + ", ".join(names))
    lines.append("提示：现在可以直接用队伍名，例如：pba battle xiaobian")
    return "\n".join(lines)


def resolve_trainer_path(name_or_path: str) -> Path:
    """Resolve a trainer template from either a file path or a friendly team name.

    User-facing commands should accept all of these forms:
      - xiaobian
      - xiaobian.json
      - data/trainers/xiaobian.json
      - /absolute/path/to/xiaobian.json
    """
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


def load_trainer_template_for_cli(name_or_path: str) -> tuple[Path, dict]:
    path = resolve_trainer_path(name_or_path)
    try:
        with open(path, encoding="utf-8") as f:
            return path, json.load(f)
    except FileNotFoundError:
        print(f"队伍模版不存在：{name_or_path}")
        print(format_trainer_suggestions(name_or_path))
        raise SystemExit(1) from None
    except json.JSONDecodeError as exc:
        print(f"队伍模版 JSON 解析失败：{path}:{exc.lineno}:{exc.colno} {exc.msg}")
        print("提示：如果不想手写 JSON，可以运行：pba team create")
        raise SystemExit(1) from None


def print_validation_result(path: Path, local_result, showdown_result=None, *, battle_format: str | None = None) -> None:
    print(f"# 队伍合法性检查：{path}")
    if battle_format:
        print(f"对战格式：{battle_format}")

    if local_result.errors:
        print("\n错误：")
        for error in local_result.errors:
            print(f"❌ {error}")
    if local_result.warnings:
        print("\n警告：")
        for warning in local_result.warnings:
            print(f"⚠️ {warning}")

    if not local_result.ok:
        print("\n结果：本地基础校验失败，请先修正错误。")
        return

    print("\n✅ 本地基础校验通过。")

    if showdown_result is None:
        print("结果：未运行 Pokémon Showdown 权威规则校验。")
        return

    for warning in showdown_result.warnings:
        print(f"⚠️ {warning}")

    if not showdown_result.checked:
        print("结果：本地基础校验通过，但未完成当前规则下的权威合法性判断。")
        return

    if showdown_result.ok:
        print("✅ Pokémon Showdown 规则校验通过。")
        print("\n结果：队伍合法，可以用于当前规则对战。")
        return

    print("\nShowdown 规则问题：")
    for error in showdown_result.errors:
        print(f"❌ {humanize_showdown_error(error)}")
        print(f"   Showdown 原因：{error}")
    print("\n结果：队伍不合法，不能直接用于当前规则对战。")


def humanize_showdown_error(error: str) -> str:
    lower = error.lower()
    if "is not allowed" in lower or "is banned" in lower:
        return "当前规则不允许队伍中的某个宝可梦、道具、特性或招式。"
    if "can't learn" in lower or "cannot learn" in lower:
        return "某只宝可梦不能学习队伍中配置的某个招式。"
    if "ability" in lower:
        return "某只宝可梦的特性配置不符合当前规则。"
    if "ev" in lower:
        return "努力值配置不符合当前规则或 Showdown 期望。"
    if "species clause" in lower:
        return "队伍违反了同种宝可梦限制。"
    return "当前规则校验失败。"


def validate_template_for_cli(path: Path, template: dict, *, battle_format: str, local_only: bool = False):
    from pokemon_battle_assistant.showdown_validator import validate_showdown_team
    from pokemon_battle_assistant.team_converter import template_to_showdown_text
    from pokemon_battle_assistant.validators import validate_trainer_template

    local_result = validate_trainer_template(path)
    showdown_result = None
    if local_result.ok and not local_only:
        showdown_result = validate_showdown_team(template_to_showdown_text(template), battle_format)
    return local_result, showdown_result


def validation_ok(local_result, showdown_result) -> bool:
    if not local_result.ok:
        return False
    if showdown_result is not None and showdown_result.checked and not showdown_result.ok:
        return False
    return True


def cmd_env(args: argparse.Namespace) -> None:
    from pokemon_battle_assistant.env_check import format_env_check, run_env_check

    if args.env_action == "check":
        result = run_env_check()
        print(format_env_check(result, as_json=args.json))
    else:
        print("请使用：pba env check")


def cmd_team(args: argparse.Namespace) -> None:
    from pokemon_battle_assistant import trainer_cli as mod

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
    elif args.team_action == "validate":
        path, template = load_trainer_template_for_cli(args.name)
        battle_format = args.format or template.get("format", "gen9ou")
        local_result, showdown_result = validate_template_for_cli(
            path,
            template,
            battle_format=battle_format,
            local_only=args.local_only,
        )
        if args.json:
            print(json.dumps(
                {
                    "ok": validation_ok(local_result, showdown_result),
                    "path": str(path),
                    "format": battle_format,
                    "local": local_result.to_dict(),
                    "showdown": showdown_result.to_dict() if showdown_result else None,
                },
                ensure_ascii=False,
                indent=2,
            ))
        else:
            print_validation_result(path, local_result, showdown_result, battle_format=battle_format)
        if not validation_ok(local_result, showdown_result):
            raise SystemExit(1)



def raise_battle_error(exc: Exception) -> None:
    text = str(exc)
    exc_name = exc.__class__.__name__
    print("\n# 对战启动/运行失败")
    if isinstance(exc, ModuleNotFoundError) and getattr(exc, "name", "") == "poke_env":
        print("未找到 poke-env。")
        print("请运行：")
        print("  .venv/bin/python -m pip install -e ~/Bian-workspace/poke-env")
    elif "ConnectionRefused" in text or "Connect call failed" in text or "Errno 61" in text or "Cannot connect" in text:
        print("无法连接本地 Pokémon Showdown server。")
        print("请先运行：")
        print("  cd ~/Bian-workspace/pokemon-showdown")
        print("  node pokemon-showdown start --no-security")
    elif "Your team was rejected" in text or "team was rejected" in text:
        print("队伍被 Showdown 拒绝。请查看上方 Showdown 返回的原因，并修改队伍模版。")
        print("你也可以先运行：")
        print("  pba team validate <队伍名>")
    else:
        print(f"{exc_name}: {text}")
        print("如果不确定环境是否正常，请先运行：pba env check")
    raise SystemExit(1)


def cmd_battle(args: argparse.Namespace) -> None:
    from pokemon_battle_assistant.env_check import port_open
    from pokemon_battle_assistant.environment import BattleRunConfig, BattleRunner
    from pokemon_battle_assistant.showdown_formats import get_format_info
    from pokemon_battle_assistant.team_converter import template_to_showdown_text
    from pokemon_battle_assistant.team_selection import parse_selection, validate_selected_slots
    from pokemon_battle_assistant.translation import translate_pokemon

    p1_path, p1_template = load_trainer_template_for_cli(args.template)
    p1_team_text = template_to_showdown_text(p1_template)
    p1_source = str(p1_path)

    if args.opponent:
        p2_path, p2_template = load_trainer_template_for_cli(args.opponent)
        p2_team_text = template_to_showdown_text(p2_template)
        p2_source = str(p2_path)
    else:
        p2_team_text = p1_team_text
        p2_source = p1_source

    battle_format = args.format or p1_template.get("format", "gen9ou")
    format_info = get_format_info(battle_format)
    expected_selection_size = format_info.picked_team_size
    try:
        p1_selection = parse_selection(args.select)
        p2_selection = parse_selection(args.opponent_select)
        if expected_selection_size:
            if p1_selection.mode == "fixed":
                validate_selected_slots(
                    p1_selection.fixed_order,
                    required_count=expected_selection_size,
                    team_size=len(p1_template.get("team", [])),
                )
            if p2_selection.mode == "fixed":
                validate_selected_slots(
                    p2_selection.fixed_order,
                    required_count=expected_selection_size,
                    team_size=len((p2_template if args.opponent else p1_template).get("team", [])),
                )
    except ValueError as exc:
        print(f"队伍选出参数错误：{exc}")
        raise SystemExit(1) from None

    if not args.skip_validation:
        p1_local, p1_showdown = validate_template_for_cli(p1_path, p1_template, battle_format=battle_format)
        if not validation_ok(p1_local, p1_showdown):
            print_validation_result(p1_path, p1_local, p1_showdown, battle_format=battle_format)
            raise SystemExit(1)
        if args.opponent:
            p2_local, p2_showdown = validate_template_for_cli(p2_path, p2_template, battle_format=battle_format)
            if not validation_ok(p2_local, p2_showdown):
                print_validation_result(p2_path, p2_local, p2_showdown, battle_format=battle_format)
                raise SystemExit(1)

    if not port_open("127.0.0.1", 8000):
        print("# 对战启动前检查失败")
        print("队伍合法性检查已通过，但无法连接本地 Pokémon Showdown server。")
        print("请先在另一个终端运行：")
        print("  cd ~/Bian-workspace/pokemon-showdown")
        print("  node pokemon-showdown start --no-security")
        raise SystemExit(1)

    async def run() -> None:
        print("# 对战运行前配置")
        print(f"battle_format: {battle_format}")
        print("server: local Pokémon Showdown, ws://localhost:8000/showdown/websocket")
        print(f"player_1_template: {p1_source}")
        print(f"player_2_template: {p2_source}")
        print(f"player_1_control: {args.player1_control}")
        print(f"player_2_control: {args.player2_control}")
        print(f"output_root: {args.output_root}")
        if expected_selection_size:
            print(f"team_preview: 需要选出 {expected_selection_size} 只；player_1={p1_selection.to_dict()} player_2={p2_selection.to_dict()}")
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
            player_1_selection=p1_selection,
            player_2_selection=p2_selection,
            expected_selection_size=expected_selection_size,
            output_root=Path(args.output_root),
            metadata={"entrypoint": "pba battle"},
        )
        try:
            result = await BattleRunner().run(config)
        except Exception as exc:
            raise_battle_error(exc)
        battle = result.record["battle"]

        print("# 对战结束摘要")
        print(f"battle_tag: {battle['battle_tag']}")
        print(f"format: {battle['format']}")
        print(f"turns: {battle['turns']}")
        print(f"winner_side: {'player_1' if battle['won'] else 'player_2'}")
        print("player_1_team:", [translate_pokemon(mon["species"]) for mon in battle["team"]])
        print("player_2_team:", [translate_pokemon(mon["species"]) for mon in battle["opponent_team"]])
        print(f"environment_steps: {len(result.record.get('steps', []))}")
        team_preview = result.record.get("team_preview") or {}
        if team_preview.get("player_1"):
            print("player_1_selected_slots:", team_preview["player_1"].get("selected_slots"))
        if team_preview.get("player_2"):
            print("player_2_selected_slots:", team_preview["player_2"].get("selected_slots"))
        print()
        print("# 文件已导出")
        print(f"replay_html: {result.replay_path}")
        print(f"record_json: {result.record_path}")
        print(f"report_md: {result.report_path}")
        print(f"steps_jsonl: {result.steps_path}")

    asyncio.run(run())


def cmd_random_battle(args: argparse.Namespace) -> None:
    from pokemon_battle_assistant.env_check import port_open
    from pokemon_battle_assistant.environment import BattleRunConfig, BattleRunner
    from pokemon_battle_assistant.translation import translate_pokemon

    battle_format = args.format

    if not port_open("127.0.0.1", 8000):
        print("# 对战启动前检查失败")
        print("无法连接本地 Pokémon Showdown server。")
        print("请先在另一个终端运行：")
        print("  cd ~/Bian-workspace/pokemon-showdown")
        print("  node pokemon-showdown start --no-security")
        raise SystemExit(1)

    async def run() -> None:
        print("# 随机对战运行前配置")
        print(f"battle_format: {battle_format}")
        print("server: local Pokémon Showdown, ws://localhost:8000/showdown/websocket")
        print("team_source: Showdown random battle generator")
        print(f"player_1_control: {args.player1_control}")
        print(f"player_2_control: {args.player2_control}")
        print(f"output_root: {args.output_root}")
        print("note: 第一阶段只运行和记录环境，不开发助手或策略。")
        print()

        config = BattleRunConfig(
            battle_format=battle_format,
            player_1_source="Showdown random battle generator",
            player_2_source="Showdown random battle generator",
            player_1_control=args.player1_control,
            player_2_control=args.player2_control,
            output_root=Path(args.output_root),
            metadata={"entrypoint": "pba random-battle"},
        )
        try:
            result = await BattleRunner().run(config)
        except Exception as exc:
            raise_battle_error(exc)
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

    validate_p = team_sub.add_parser("validate", help="检查队伍在当前规则下是否合法")
    validate_p.add_argument("name", help="模版名或 JSON 路径")
    validate_p.add_argument("--format", help="对战格式（默认读取队伍模版里的 format）")
    validate_p.add_argument("--local-only", action="store_true", help="只做本地基础检查，跳过 Showdown 规则校验")
    validate_p.add_argument("--json", action="store_true", help="输出 JSON 格式结果")

    delete_p = team_sub.add_parser("delete", help="删除队伍")
    delete_p.add_argument("name", help="模版名（不含 .json）")

    # --- pba env ---
    env_parser = sub.add_parser("env", help="环境检查工具")
    env_sub = env_parser.add_subparsers(dest="env_action")
    env_check = env_sub.add_parser("check", help="检查 Python、依赖、Showdown 和数据文件")
    env_check.add_argument("--json", action="store_true", help="输出 JSON 格式")

    # --- pba doctor ---
    sub.add_parser("doctor", help="一键检查环境（等同于 pba env check）")

    # --- pba battle ---
    battle_parser = sub.add_parser("battle", help="使用训练家模版进行对战")
    battle_parser.add_argument("template", help="玩家 1 的队伍名或 JSON 路径，例如 xiaobian")
    battle_parser.add_argument("--opponent", help="玩家 2 的队伍名或 JSON 路径（默认与玩家 1 相同）")
    battle_parser.add_argument("--format", help="对战格式（默认从模版读取）")
    battle_parser.add_argument("--player1-control", choices=["random", "manual"], default="random", help="玩家 1 控制方式")
    battle_parser.add_argument("--player2-control", choices=["random", "manual"], default="random", help="玩家 2 控制方式")
    battle_parser.add_argument("--manual", action="store_true", help="快捷方式：等同于 --player1-control manual")
    battle_parser.add_argument("--skip-validation", action="store_true", help="跳过开战前队伍合法性检查")
    battle_parser.add_argument("--output-root", default="battle_outputs", help="对战记录输出目录，默认 battle_outputs")
    battle_parser.add_argument(
        "--select",
        default="auto",
        help="玩家 1 队伍选出：auto/manual/random 或编号列表，如 1,2,3,4（VGC 默认选前 4 只）",
    )
    battle_parser.add_argument(
        "--opponent-select",
        default="auto",
        help="玩家 2 队伍选出：auto/manual/random 或编号列表，如 1,2,3,4",
    )

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
    random_parser.add_argument("--output-root", default="battle_outputs", help="对战记录输出目录，默认 battle_outputs")

    # --- pba analyze ---
    analyze_parser = sub.add_parser("analyze", help="离线局面分析")
    analyze_parser.add_argument("input", help="对战局面 JSON 文件路径")
    analyze_parser.add_argument("--top", type=int, default=3, help="显示前 N 个推荐操作")

    args = parser.parse_args()

    if getattr(args, "manual", False):
        args.player1_control = "manual"

    if args.command == "env":
        if not args.env_action:
            env_parser.print_help()
        else:
            cmd_env(args)
    elif args.command == "doctor":
        args.env_action = "check"
        args.json = False
        cmd_env(args)
    elif args.command == "team":
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
        print_friendly_help(parser)


def print_friendly_help(parser: argparse.ArgumentParser) -> None:
    """Print a task-oriented landing page instead of only argparse syntax."""
    print("Pokemon Battle Assistant — 宝可梦对战助手")
    print()
    print("常用命令：")
    print("  pba doctor                         检查环境是否能跑对战")
    print("  pba team list                      查看已有队伍")
    print("  pba team create                    用交互向导创建队伍")
    print("  pba team show xiaobian             查看某个队伍")
    print("  pba battle xiaobian                用队伍名直接开始本地对战")
    print("  pba random-battle --manual         随机队伍，玩家 1 手动操作")
    print("  pba analyze examples/simple_battle.json --top 5")
    print()
    print("新手建议顺序：")
    print("  1. pba doctor")
    print("  2. pba team list")
    print("  3. pba battle <队伍名>")
    print()
    print("完整参数：")
    parser.print_help()


if __name__ == "__main__":
    main()
