"""Run one local poke-env battle and export its configuration and record.

Prerequisite:
    cd ~/Bian-workspace/pokemon-showdown
    node pokemon-showdown start --no-security

Run:
    cd ~/Bian-workspace/pokemon-battle-assistant
    .venv/bin/python scripts/poke_env_smoke_battle.py

Output:
    battle_outputs/<battle_tag>/replay.html
    battle_outputs/<battle_tag>/record.json
    battle_outputs/<battle_tag>/report.md
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from poke_env.battle import AbstractBattle
from poke_env.player import RandomPlayer
from poke_env.player.battle_order import BattleOrder

# Allow running this script directly without installing the package.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pokemon_battle_assistant.translation import (
    translate_ability,
    translate_item,
    translate_move,
    translate_pokemon,
)

BATTLE_FORMAT = "gen9randombattle"
OUTPUT_ROOT = Path("battle_outputs")

TYPE_ZH = {
    "NORMAL": "一般", "FIRE": "火", "WATER": "水", "ELECTRIC": "电", "GRASS": "草",
    "ICE": "冰", "FIGHTING": "格斗", "POISON": "毒", "GROUND": "地面", "FLYING": "飞行",
    "PSYCHIC": "超能力", "BUG": "虫", "ROCK": "岩石", "GHOST": "幽灵", "DRAGON": "龙",
    "DARK": "恶", "STEEL": "钢", "FAIRY": "妖精",
}

CATEGORY_ZH = {"PHYSICAL": "物理", "SPECIAL": "特殊", "STATUS": "变化"}

STATUS_ZH = {
    "FNT": "濒死", "BRN": "灼伤", "PAR": "麻痹", "SLP": "睡眠",
    "FRZ": "冰冻", "PSN": "中毒", "TOX": "剧毒",
}


def enum_name(value: Any) -> str | None:
    if value is None:
        return None
    name = getattr(value, "name", None)
    if name:
        return str(name)
    text = str(value)
    if " " in text and text.split(" ", 1)[0].isupper():
        return text.split(" ", 1)[0]
    return text


def translate_type(value: Any) -> str:
    name = enum_name(value)
    if not name:
        return "未知"
    return TYPE_ZH.get(name.upper(), name)


def translate_category(value: Any) -> str:
    name = enum_name(value)
    if not name:
        return "未知"
    return CATEGORY_ZH.get(name.upper(), name)


def translate_status(value: Any) -> str | None:
    name = enum_name(value)
    if not name or name == "None":
        return None
    return STATUS_ZH.get(name.upper(), name)


class RecordingRandomPlayer(RandomPlayer):
    """RandomPlayer that records every decision point it sees."""

    def __init__(self, *args: Any, label: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.label = label
        self.observations: dict[str, list[dict[str, Any]]] = {}

    def choose_move(self, battle: AbstractBattle) -> BattleOrder:
        history = self.observations.setdefault(battle.battle_tag, [])
        history.append(snapshot_battle(battle, observer=self.label))
        return super().choose_move(battle)


def pokemon_to_dict(mon: Any) -> dict[str, Any] | None:
    """Convert a poke-env Pokemon object to JSON-friendly data."""

    if mon is None:
        return None

    moves = getattr(mon, "moves", {}) or {}
    stats = getattr(mon, "stats", {}) or {}

    return {
        "species": getattr(mon, "species", None),
        "base_species": getattr(mon, "base_species", None),
        "types": [translate_type(t) for t in (getattr(mon, "types", []) or [])],
        "hp_fraction": getattr(mon, "current_hp_fraction", None),
        "status": translate_status(getattr(mon, "status", None)),
        "item": getattr(mon, "item", None),
        "ability": getattr(mon, "ability", None),
        "stats": {str(k): v for k, v in stats.items()} if isinstance(stats, dict) else {},
        "moves": [str(k) for k in moves.keys()] if isinstance(moves, dict) else [],
        "fainted": getattr(mon, "fainted", None),
        "active": getattr(mon, "active", None),
    }


def move_to_dict(move: Any) -> dict[str, Any]:
    return {
        "id": getattr(move, "id", None),
        "name": getattr(move, "name", None),
        "type": translate_type(getattr(move, "type", None)),
        "base_power": getattr(move, "base_power", None),
        "accuracy": getattr(move, "accuracy", None),
        "category": translate_category(getattr(move, "category", None)),
        "priority": getattr(move, "priority", None),
        "target": str(getattr(move, "target", None)),
    }


def team_to_dict(team: Any) -> list[dict[str, Any]]:
    if not team:
        return []
    return [pokemon_to_dict(mon) for mon in team.values()]


def snapshot_battle(battle: AbstractBattle, observer: str) -> dict[str, Any]:
    """Record the battle state visible to one player at a decision point."""

    return {
        "observer": observer,
        "battle_tag": battle.battle_tag,
        "turn": battle.turn,
        "format": battle.format,
        "player_username": battle.player_username,
        "opponent_username": battle.opponent_username,
        "active_pokemon": pokemon_to_dict(getattr(battle, "active_pokemon", None)),
        "opponent_active_pokemon": pokemon_to_dict(getattr(battle, "opponent_active_pokemon", None)),
        "team": team_to_dict(battle.team),
        "opponent_team": team_to_dict(battle.opponent_team),
        "available_moves": [move_to_dict(move) for move in (getattr(battle, "available_moves", []) or [])],
        "available_switches": [pokemon_to_dict(mon) for mon in (getattr(battle, "available_switches", []) or [])],
        "weather": [str(k) for k in battle.weather.keys()],
        "fields": [str(k) for k in battle.fields.keys()],
        "side_conditions": [str(k) for k in battle.side_conditions.keys()],
        "opponent_side_conditions": [str(k) for k in battle.opponent_side_conditions.keys()],
    }


def battle_summary(battle: AbstractBattle) -> dict[str, Any]:
    """Record final battle information after the battle finishes."""

    return {
        "battle_tag": battle.battle_tag,
        "format": battle.format,
        "gen": battle.gen,
        "turns": battle.turn,
        "finished": battle.finished,
        "won": battle.won,
        "lost": battle.lost,
        "player_username": battle.player_username,
        "opponent_username": battle.opponent_username,
        "players": list(battle.players),
        "team": team_to_dict(battle.team),
        "opponent_team": team_to_dict(battle.opponent_team),
        "raw_replay_events": getattr(battle, "_replay_data", []),
    }


def label_or_unknown(value: Any) -> str:
    """Convert empty values to a readable Chinese placeholder."""

    if value is None or value == "" or value == "None":
        return "未知"
    return str(value)


def percent(value: Any) -> str:
    if value is None:
        return "未知"
    try:
        return f"{float(value) * 100:.0f}%"
    except (TypeError, ValueError):
        return "未知"


def translate_battle_pokemon_label(value: Any) -> str:
    """Translate labels like 'p1a: Wo-Chien' while keeping the side prefix."""

    if value is None:
        return "未知"
    text = str(value)
    if ":" in text:
        prefix, name = text.split(":", 1)
        return f"{prefix}: {translate_pokemon(name.strip())}"
    return translate_pokemon(text)


def translate_details_species(details: Any) -> str:
    """Translate the first species part in Showdown details strings."""

    if details is None:
        return "未知"
    text = str(details)
    if not text:
        return "未知"
    first, *rest = text.split(",")
    translated = translate_pokemon(first.strip())
    return ",".join([translated, *rest]) if rest else translated


def pokemon_line(mon: dict[str, Any] | None) -> str:
    if not mon:
        return "未知宝可梦"
    species = translate_pokemon(mon.get("species"))
    types = "/".join(mon.get("types") or []) or "未知属性"
    hp = percent(mon.get("hp_fraction"))
    item = translate_item(mon.get("item"))
    ability = translate_ability(mon.get("ability"))
    status = label_or_unknown(mon.get("status"))
    moves = ", ".join(translate_move(move) for move in (mon.get("moves") or [])) or "未知招式"
    fainted = "，已倒下" if mon.get("fainted") else ""
    return f"**{species}**（{types}，HP {hp}，道具：{item}，特性：{ability}，状态：{status}{fainted}）\n  - 招式：{moves}"


def move_line(move: dict[str, Any]) -> str:
    return (
        f"{translate_move(move.get('id') or move.get('name'))}"
        f"（属性：{label_or_unknown(move.get('type'))}，威力：{label_or_unknown(move.get('base_power'))}，"
        f"命中：{label_or_unknown(move.get('accuracy'))}，分类：{label_or_unknown(move.get('category'))}）"
    )


def replay_event_to_chinese(event: list[Any]) -> str | None:
    """Translate a small subset of Showdown replay events into Chinese."""

    if len(event) < 2:
        return None
    tag = event[1]
    try:
        if tag == "turn" and len(event) >= 3:
            return f"### 第 {event[2]} 回合"
        if tag == "switch" and len(event) >= 5:
            return f"- 换人：{translate_battle_pokemon_label(event[2])} 登场（{translate_details_species(event[3])}，HP：{event[4]}）。"
        if tag == "drag" and len(event) >= 5:
            return f"- 被强制换入：{translate_battle_pokemon_label(event[2])} 登场（{translate_details_species(event[3])}，HP：{event[4]}）。"
        if tag == "move" and len(event) >= 4:
            target = f"，目标：{translate_battle_pokemon_label(event[4])}" if len(event) >= 5 and event[4] else ""
            return f"- 出招：{translate_battle_pokemon_label(event[2])} 使用了 **{translate_move(event[3])}**{target}。"
        if tag == "-damage" and len(event) >= 4:
            return f"- 伤害：{translate_battle_pokemon_label(event[2])} 当前 HP 变为 {event[3]}。"
        if tag == "-heal" and len(event) >= 4:
            return f"- 回复：{translate_battle_pokemon_label(event[2])} 当前 HP 变为 {event[3]}。"
        if tag == "faint" and len(event) >= 3:
            return f"- 倒下：{translate_battle_pokemon_label(event[2])} 失去战斗能力。"
        if tag == "win" and len(event) >= 3:
            return f"## 胜者：{event[2]}"
        if tag == "tie":
            return "## 平局"
        if tag == "-status" and len(event) >= 4:
            return f"- 异常状态：{translate_battle_pokemon_label(event[2])} 陷入 {event[3]}。"
        if tag == "-curestatus" and len(event) >= 4:
            return f"- 状态解除：{translate_battle_pokemon_label(event[2])} 解除了 {event[3]}。"
        if tag == "-boost" and len(event) >= 5:
            return f"- 能力提升：{translate_battle_pokemon_label(event[2])} 的 {event[3]} 提升 {event[4]} 级。"
        if tag == "-unboost" and len(event) >= 5:
            return f"- 能力下降：{translate_battle_pokemon_label(event[2])} 的 {event[3]} 下降 {event[4]} 级。"
        if tag == "-weather" and len(event) >= 3:
            return f"- 天气变化：{event[2]}。"
        if tag == "-fieldstart" and len(event) >= 3:
            return f"- 场地/全场效果开始：{event[2]}。"
        if tag == "-fieldend" and len(event) >= 3:
            return f"- 场地/全场效果结束：{event[2]}。"
        if tag == "-sidestart" and len(event) >= 4:
            return f"- 场地状态开始：{event[2]} 一侧出现 {event[3]}。"
        if tag == "-sideend" and len(event) >= 4:
            return f"- 场地状态结束：{event[2]} 一侧的 {event[3]} 消失。"
    except Exception:
        return None
    return None


def build_markdown_report(record: dict[str, Any]) -> str:
    """Build a Chinese Markdown battle report."""

    battle = record["battle"]
    config = record["pre_battle_config"]
    winner = "玩家 1" if battle["won"] else "玩家 2"

    lines: list[str] = []
    lines.append(f"# 宝可梦本地模拟对战报告：{battle['battle_tag']}")
    lines.append("")
    lines.append("## 1. 对战运行前配置")
    lines.append("")
    lines.append(f"- 对战格式：`{config['battle_format']}`")
    lines.append(f"- 对战服务器：{config['server']}")
    lines.append(f"- 玩家 1：{config['players'][0]}（随机行动）")
    lines.append(f"- 玩家 2：{config['players'][1]}（随机行动）")
    lines.append(f"- 队伍来源：{config['team_source']}。随机对战的队伍由 Showdown 开局时生成。")
    lines.append("")

    lines.append("## 2. 对战结果摘要")
    lines.append("")
    lines.append(f"- 对战编号：`{battle['battle_tag']}`")
    lines.append(f"- 规则格式：`{battle['format']}`")
    lines.append(f"- 世代：Gen {battle['gen']}")
    lines.append(f"- 总回合数：{battle['turns']}")
    lines.append(f"- 胜者：**{winner}**")
    lines.append(f"- 玩家 1 用户名：{battle['player_username']}")
    lines.append(f"- 玩家 2 用户名：{battle['opponent_username']}")
    lines.append("")

    lines.append("## 3. 玩家 1 队伍")
    lines.append("")
    for i, mon in enumerate(battle["team"], start=1):
        lines.append(f"{i}. {pokemon_line(mon)}")
    lines.append("")

    lines.append("## 4. 玩家 2 队伍")
    lines.append("")
    for i, mon in enumerate(battle["opponent_team"], start=1):
        lines.append(f"{i}. {pokemon_line(mon)}")
    lines.append("")

    lines.append("## 5. 决策点记录摘要")
    lines.append("")
    lines.append(f"- 玩家 1 决策快照数：{len(record['player_1_observations'])}")
    lines.append(f"- 玩家 2 决策快照数：{len(record['player_2_observations'])}")
    lines.append("")
    lines.append("下面展示玩家 1 视角前 10 个决策点，完整数据见 `record.json`。")
    lines.append("")
    for obs in record["player_1_observations"][:10]:
        active = obs.get("active_pokemon") or {}
        opp = obs.get("opponent_active_pokemon") or {}
        moves = obs.get("available_moves") or []
        move_text = "；".join(move_line(m) for m in moves) or "无可用招式"
        lines.append(f"### 决策点：第 {obs.get('turn')} 回合")
        lines.append(f"- 我方在场：{translate_pokemon(active.get('species'))}（HP {percent(active.get('hp_fraction'))}）")
        lines.append(f"- 对方在场：{translate_pokemon(opp.get('species'))}（HP {percent(opp.get('hp_fraction'))}）")
        lines.append(f"- 可用招式：{move_text}")
        lines.append("")

    lines.append("## 6. 中文对战事件记录")
    lines.append("")
    translated_count = 0
    for event in battle["raw_replay_events"]:
        text = replay_event_to_chinese(event)
        if text:
            lines.append(text)
            translated_count += 1
    if translated_count == 0:
        lines.append("未能从 replay events 中提取可读事件。请查看 `record.json` 或 `replay.html`。")
    lines.append("")

    lines.append("## 7. 导出文件")
    lines.append("")
    lines.append(f"- 可视化 replay：`{record['files']['replay_html']}`")
    lines.append(f"- 完整 JSON 记录：`{record['files']['record_json']}`")
    lines.append(f"- 中文 Markdown 报告：`{record['files']['report_md']}`")
    lines.append("")
    return "\n".join(lines)


def print_pre_battle_config() -> None:
    print("# 对战运行前配置")
    print(f"battle_format: {BATTLE_FORMAT}")
    print("server: local Pokémon Showdown, ws://localhost:8000/showdown/websocket")
    print("player_1: RecordingRandomPlayer / random moves")
    print("player_2: RecordingRandomPlayer / random moves")
    print("team_source: Showdown random battle generator")
    print("note: 随机对战的具体队伍由 Showdown 开局时生成，所以真正队伍会在对战后导出。")
    print()


def print_post_battle_summary(record: dict[str, Any]) -> None:
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

    player_1 = RecordingRandomPlayer(
        label="player_1",
        battle_format=BATTLE_FORMAT,
        max_concurrent_battles=1,
        save_replays=False,
    )
    player_2 = RecordingRandomPlayer(
        label="player_2",
        battle_format=BATTLE_FORMAT,
        max_concurrent_battles=1,
        save_replays=False,
    )

    try:
        await player_1.battle_against(player_2, n_battles=1)

        battle_tag = next(iter(player_1.battles))
        battle = player_1.battles[battle_tag]
        output_dir = OUTPUT_ROOT / battle_tag
        output_dir.mkdir(parents=True, exist_ok=True)

        replay_path = battle.save_replay(output_dir / "replay.html")
        record = {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "pre_battle_config": {
                "battle_format": BATTLE_FORMAT,
                "server": "local Pokémon Showdown / localhost:8000",
                "players": ["RecordingRandomPlayer", "RecordingRandomPlayer"],
                "team_source": "Showdown random battle generator",
            },
            "battle": battle_summary(battle),
            "player_1_observations": player_1.observations.get(battle_tag, []),
            "player_2_observations": player_2.observations.get(battle_tag, []),
            "files": {
                "replay_html": str(replay_path),
                "record_json": str(output_dir / "record.json"),
                "report_md": str(output_dir / "report.md"),
            },
        }

        record_path = output_dir / "record.json"
        report_path = output_dir / "report.md"
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path.write_text(build_markdown_report(record), encoding="utf-8")

        print_post_battle_summary(record)
        print()
        print("# 文件已导出")
        print(f"replay_html: {replay_path}")
        print(f"record_json: {record_path}")
        print(f"report_md: {report_path}")
    finally:
        await player_1.ps_client.stop_listening()
        await player_2.ps_client.stop_listening()


if __name__ == "__main__":
    asyncio.run(main())
