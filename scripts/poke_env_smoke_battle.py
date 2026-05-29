"""Run one local poke-env battle and export its configuration and record.

Prerequisite:
    cd ~/path/to/pokemon-showdown
    node pokemon-showdown start --no-security

Run:
    cd ~/path/to/pokemon-battle-assistant
    .venv/bin/python scripts/poke_env_smoke_battle.py

Output:
    battle_outputs/<battle_tag>/replay.html
    battle_outputs/<battle_tag>/record.json
    battle_outputs/<battle_tag>/report.md
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pokemon_battle_assistant.environment import BattleRunConfig, BattleRunner
from pokemon_battle_assistant.translation import translate_pokemon

BATTLE_FORMAT = "gen9randombattle"


def print_pre_battle_config() -> None:
    print("# 对战运行前配置")
    print(f"battle_format: {BATTLE_FORMAT}")
    print("server: local Pokémon Showdown, ws://localhost:8000/showdown/websocket")
    print("player_1: RecordingRandomPlayer / environment baseline random legal actions")
    print("player_2: RecordingRandomPlayer / environment baseline random legal actions")
    print("team_source: Showdown random battle generator")
    print("note: 第一阶段只运行和记录环境；随机队伍由 Showdown 开局时生成。")
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
    print("player_2_seen_team:", [translate_pokemon(mon["species"]) for mon in battle["opponent_team"]])
    print(f"raw_replay_events: {len(battle['raw_replay_events'])}")
    print(f"decision_snapshots_player_1: {len(record['player_1_observations'])}")
    print(f"decision_snapshots_player_2: {len(record['player_2_observations'])}")


async def main() -> None:
    print_pre_battle_config()

    config = BattleRunConfig(
        battle_format=BATTLE_FORMAT,
        metadata={"entrypoint": "scripts/poke_env_smoke_battle.py", "team_source_note": "Showdown random battle generator"},
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


if __name__ == "__main__":
    asyncio.run(main())
