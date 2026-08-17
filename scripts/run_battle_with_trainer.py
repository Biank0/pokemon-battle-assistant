"""Run a local poke-env battle using trainer template(s).

Prerequisite:
    cd ~/path/to/pokemon-showdown
    node pokemon-showdown start --no-security

Run:
    cd ~/path/to/pokemon-battle-assistant
    .venv/bin/python scripts/run_battle_with_trainer.py data/teams/lab/example_team.json

    # Two different templates (player 1 vs player 2):
    .venv/bin/python scripts/run_battle_with_trainer.py data/teams/lab/team_a.json --opponent data/teams/lab/team_b.json

Output:
    battle_outputs/<battle_tag>/replay.html
    battle_outputs/<battle_tag>/record.json
    battle_outputs/<battle_tag>/report.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pokemon_battle_assistant.environment import BattleRunConfig, BattleRunner
from pokemon_battle_assistant.team_converter import template_to_showdown_text
from pokemon_battle_assistant.translation import translate_pokemon


def load_template(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def print_pre_battle_config(
    battle_format: str,
    p1_source: str,
    p2_source: str,
    p1_text: str,
    p2_text: str,
) -> None:
    print("# 对战运行前配置")
    print(f"battle_format: {battle_format}")
    print("server: local Pokémon Showdown, ws://localhost:8000/showdown/websocket")
    print(f"player_1_template: {p1_source}")
    print(f"player_2_template: {p2_source}")
    print("decision_mode: environment baseline / random legal actions")
    print("note: 第一阶段只运行和记录环境，不开发助手或策略。")
    print()
    print("--- Player 1 Team (Showdown format) ---")
    print(p1_text)
    print()
    print("--- Player 2 Team (Showdown format) ---")
    print(p2_text)
    print()


def print_post_battle_summary(record: dict) -> None:
    battle = record["battle"]
    print("# 对战结束摘要")
    print(f"battle_tag: {battle['battle_tag']}")
    print(f"format: {battle['format']}")
    print(f"turns: {battle['turns']}")
    print(f"winner_side: {'player_1' if battle['won'] else 'player_2'}")
    print(f"player_1_username: {battle['player_username']}")
    print(f"player_2_username: {battle['opponent_username']}")
    print("player_1_team:", [translate_pokemon(mon["species"]) for mon in battle["team"]])
    print("player_2_team:", [translate_pokemon(mon["species"]) for mon in battle["opponent_team"]])
    print(f"raw_replay_events: {len(battle['raw_replay_events'])}")
    print(f"decision_snapshots_player_1: {len(record['player_1_observations'])}")
    print(f"decision_snapshots_player_2: {len(record['player_2_observations'])}")


async def run_battle(
    battle_format: str,
    p1_team_text: str,
    p2_team_text: str,
    p1_source: str,
    p2_source: str,
) -> None:
    print_pre_battle_config(battle_format, p1_source, p2_source, p1_team_text, p2_team_text)

    config = BattleRunConfig(
        battle_format=battle_format,
        player_1_team=p1_team_text,
        player_2_team=p2_team_text,
        player_1_source=p1_source,
        player_2_source=p2_source,
        metadata={"entrypoint": "scripts/run_battle_with_trainer.py"},
    )
    result = await BattleRunner().run(config)

    print_post_battle_summary(result.record)
    print(f"environment_steps: {len(result.record.get('steps', []))}")
    print()
    print("# 文件已导出")
    print(f"replay_html: {result.replay_path}")
    print(f"record_json: {result.record_path}")
    print(f"report_md: {result.report_path}")
    print(f"steps_jsonl: {result.steps_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="使用训练家模版进行本地对战")
    parser.add_argument("template", help="玩家 1 的训练家模版 JSON 路径")
    parser.add_argument("--opponent", help="玩家 2 的训练家模版 JSON 路径（默认与玩家 1 相同）")
    parser.add_argument("--format", help="对战格式（默认从模版读取）")
    args = parser.parse_args()

    p1_template = load_template(args.template)
    p1_team_text = template_to_showdown_text(p1_template)

    if args.opponent:
        p2_template = load_template(args.opponent)
        p2_team_text = template_to_showdown_text(p2_template)
        p2_source = args.opponent
    else:
        p2_team_text = p1_team_text
        p2_source = args.template

    battle_format = args.format or p1_template.get("format", "gen9ou")

    asyncio.run(run_battle(
        battle_format=battle_format,
        p1_team_text=p1_team_text,
        p2_team_text=p2_team_text,
        p1_source=args.template,
        p2_source=p2_source,
    ))


if __name__ == "__main__":
    main()
