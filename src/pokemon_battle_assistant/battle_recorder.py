"""Shared battle recording utilities.

Extracted from scripts/poke_env_smoke_battle.py to allow reuse in other
battle scripts (e.g., trainer template battles).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pokemon_battle_assistant.team_selection import (
    TeamSelectionConfig,
    TeamSelectionRecord,
    choose_slots,
    validate_selected_slots,
)

from poke_env.battle import AbstractBattle
from poke_env.player import RandomPlayer
from poke_env.player.battle_order import BattleOrder, DoubleBattleOrder

from .showdown_formats import is_doubles_format
from .translation import (
    translate_ability,
    translate_item,
    translate_move,
    translate_pokemon,
)

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

    def __init__(
        self,
        *args: Any,
        label: str,
        selection_config: TeamSelectionConfig | None = None,
        expected_selection_size: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.label = label
        self.observations: dict[str, list[dict[str, Any]]] = {}
        self.selection_config = selection_config or TeamSelectionConfig()
        self.expected_selection_size = expected_selection_size
        self.team_selections: dict[str, dict[str, Any]] = {}

    def teampreview(self, battle: AbstractBattle) -> str:
        command, record = choose_teampreview_order(
            battle,
            label=self.label,
            selection_config=self.selection_config,
            expected_selection_size=self.expected_selection_size,
        )
        self.team_selections[battle.battle_tag] = record.to_dict()
        return command

    def choose_move(self, battle: AbstractBattle) -> BattleOrder:
        history = self.observations.setdefault(battle.battle_tag, [])
        snapshot = snapshot_battle(battle, observer=self.label)
        order = super().choose_move(battle)
        snapshot["chosen_order_message"] = getattr(order, "message", str(order))
        history.append(snapshot)
        return order


class RecordingManualPlayer(RandomPlayer):
    """Player that asks the terminal user to choose from legal orders."""

    def __init__(
        self,
        *args: Any,
        label: str,
        selection_config: TeamSelectionConfig | None = None,
        expected_selection_size: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.label = label
        self.observations: dict[str, list[dict[str, Any]]] = {}
        self.selection_config = selection_config or TeamSelectionConfig()
        self.expected_selection_size = expected_selection_size
        self.team_selections: dict[str, dict[str, Any]] = {}

    def teampreview(self, battle: AbstractBattle) -> str:
        command, record = choose_teampreview_order(
            battle,
            label=self.label,
            selection_config=self.selection_config,
            expected_selection_size=self.expected_selection_size,
        )
        self.team_selections[battle.battle_tag] = record.to_dict()
        return command

    def choose_move(self, battle: AbstractBattle) -> BattleOrder:
        history = self.observations.setdefault(battle.battle_tag, [])
        snapshot = snapshot_battle(battle, observer=self.label)
        orders = legal_orders(battle)
        if not orders:
            order = self.choose_default_move()
            snapshot["chosen_order_message"] = getattr(order, "message", str(order))
            history.append(snapshot)
            return order

        self._print_manual_prompt(snapshot, orders)
        while True:
            raw = input(f"请选择 {self.label} 的动作编号 (1-{len(orders)}): ").strip()
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(orders):
                    order = orders[idx]
                    snapshot["chosen_order_message"] = getattr(order, "message", str(order))
                    history.append(snapshot)
                    return order
            print("输入无效，请重新输入编号。")

    def _print_manual_prompt(self, snapshot: dict[str, Any], orders: list[BattleOrder]) -> None:
        active = snapshot.get("active_pokemon")
        opponent = snapshot.get("opponent_active_pokemon")
        print("\n# 手动操作决策点")
        print(f"player: {self.label}")
        print(f"battle_tag: {snapshot.get('battle_tag')}")
        print(f"turn: {snapshot.get('turn')}")
        print(f"game_type: {snapshot.get('game_type')}")
        print(f"我方在场: {manual_pokemon_label(active)}")
        print(f"对方在场: {manual_pokemon_label(opponent)}")
        print("合法动作:")
        for idx, order in enumerate(orders, 1):
            print(f"  {idx:2}. {getattr(order, 'message', str(order))}")


def teampreview_pokemon_to_dict(mon: Any, slot: int) -> dict[str, Any]:
    data = pokemon_to_dict(mon) or {}
    data["slot"] = slot
    data["display_name"] = translate_pokemon(data.get("species"))
    return data


def teampreview_team_to_list(team: Any) -> list[dict[str, Any]]:
    return [teampreview_pokemon_to_dict(mon, idx) for idx, mon in enumerate(team or [], start=1)]


def infer_teampreview_required_count(battle: AbstractBattle, expected_selection_size: int | None = None) -> int:
    if expected_selection_size:
        return expected_selection_size
    max_team_size = getattr(battle, "max_team_size", None)
    if max_team_size:
        return int(max_team_size)
    battle_format = (getattr(battle, "format", None) or "").lower()
    if "vgc" in battle_format:
        return 4
    if "bss" in battle_format or "battlestadium" in battle_format:
        return 3
    return len(getattr(battle, "team", {}) or {})


def choose_teampreview_order(
    battle: AbstractBattle,
    *,
    label: str,
    selection_config: TeamSelectionConfig,
    expected_selection_size: int | None = None,
) -> tuple[str, TeamSelectionRecord]:
    team_values = list((getattr(battle, "team", {}) or {}).values())
    required_count = infer_teampreview_required_count(battle, expected_selection_size)
    team_size = len(team_values)

    if selection_config.mode == "manual":
        selected = prompt_manual_teampreview(battle, label=label, required_count=required_count)
    else:
        selected = choose_slots(selection_config, required_count=required_count, team_size=team_size)
    selected = validate_selected_slots(selected, required_count=required_count, team_size=team_size)

    for slot in selected:
        team_values[slot - 1]._selected_in_teampreview = True

    command = "/team " + "".join(str(slot) for slot in selected)
    game_type = "doubles" if is_doubles_format(getattr(battle, "format", "")) or required_count == 4 else "singles"
    record = TeamSelectionRecord(
        player=label,
        battle_tag=battle.battle_tag,
        format=getattr(battle, "format", None),
        game_type=game_type,
        mode=selection_config.mode,
        required_count=required_count,
        selected_slots=selected,
        command=command,
        team_preview=teampreview_team_to_list(getattr(battle, "teampreview_team", []) or team_values),
        opponent_preview=teampreview_team_to_list(getattr(battle, "teampreview_opponent_team", [])),
    )
    return command, record


def prompt_manual_teampreview(battle: AbstractBattle, *, label: str, required_count: int) -> list[int]:
    team_preview = teampreview_team_to_list(getattr(battle, "teampreview_team", []) or list(battle.team.values()))
    opponent_preview = teampreview_team_to_list(getattr(battle, "teampreview_opponent_team", []))
    print("\n# 队伍选出")
    print(f"player: {label}")
    print(f"battle_tag: {battle.battle_tag}")
    print(f"format: {battle.format}")
    print(f"需要选择：{required_count} 只。双打/VGC 中前 2 只是首发。")
    print("我方队伍：")
    for mon in team_preview:
        print(f"  {mon['slot']}. {mon.get('display_name') or mon.get('species')}")
    if opponent_preview:
        print("对方队伍预览：")
        for mon in opponent_preview:
            print(f"  {mon['slot']}. {mon.get('display_name') or mon.get('species')}")
    while True:
        raw = input(f"请输入 {required_count} 个编号，例如 1,2,3,4: ").strip()
        try:
            slots = [int(part.strip()) for part in raw.replace("，", ",").split(",") if part.strip()]
            return validate_selected_slots(slots, required_count=required_count, team_size=len(team_preview))
        except ValueError as exc:
            print(f"输入无效：{exc}")


def manual_pokemon_label(value: Any) -> str:
    if isinstance(value, list):
        return " / ".join(manual_pokemon_label(item) for item in value if item) or "未知"
    if isinstance(value, dict):
        species = translate_pokemon(value.get("species"))
        hp = percent(value.get("hp_fraction"))
        status = value.get("status") or "正常"
        return f"{species}(HP {hp}, {status})"
    return "未知"


def is_sequence(value: Any) -> bool:
    return isinstance(value, (list, tuple))


def pokemon_slot_to_record(value: Any) -> Any:
    if is_sequence(value):
        return [pokemon_to_dict(mon) for mon in value]
    return pokemon_to_dict(value)


def moves_slot_to_record(value: Any) -> list[Any]:
    if not value:
        return []
    if is_sequence(value) and value and is_sequence(value[0]):
        return [[move_to_dict(move) for move in slot] for slot in value]
    return [move_to_dict(move) for move in value]


def switches_slot_to_record(value: Any) -> list[Any]:
    if not value:
        return []
    if is_sequence(value) and value and is_sequence(value[0]):
        return [[pokemon_to_dict(mon) for mon in slot] for slot in value]
    return [pokemon_to_dict(mon) for mon in value]


def legal_orders(battle: AbstractBattle) -> list[BattleOrder]:
    """Return legal complete battle orders for singles or doubles."""

    orders = getattr(battle, "valid_orders", []) or []
    if not orders:
        return []
    if is_sequence(orders) and orders and is_sequence(orders[0]):
        try:
            return list(DoubleBattleOrder.join_orders(*orders))
        except Exception:
            return [order for slot in orders for order in (slot or [])]
    return list(orders)


def legal_order_messages(battle: AbstractBattle) -> list[str]:
    return [getattr(order, "message", str(order)) for order in legal_orders(battle)]


def pokemon_to_dict(mon: Any) -> dict[str, Any] | None:
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
    return {
        "observer": observer,
        "battle_tag": battle.battle_tag,
        "turn": battle.turn,
        "format": battle.format,
        "player_username": battle.player_username,
        "opponent_username": battle.opponent_username,
        "game_type": "doubles" if is_sequence(getattr(battle, "active_pokemon", None)) else "singles",
        "active_pokemon": pokemon_slot_to_record(getattr(battle, "active_pokemon", None)),
        "opponent_active_pokemon": pokemon_slot_to_record(getattr(battle, "opponent_active_pokemon", None)),
        "team": team_to_dict(battle.team),
        "opponent_team": team_to_dict(battle.opponent_team),
        "available_moves": moves_slot_to_record(getattr(battle, "available_moves", []) or []),
        "available_switches": switches_slot_to_record(getattr(battle, "available_switches", []) or []),
        "legal_order_messages": legal_order_messages(battle),
        "chosen_order_message": None,
        "weather": [str(k) for k in battle.weather.keys()],
        "fields": [str(k) for k in battle.fields.keys()],
        "side_conditions": [str(k) for k in battle.side_conditions.keys()],
        "opponent_side_conditions": [str(k) for k in battle.opponent_side_conditions.keys()],
    }


def battle_summary(battle: AbstractBattle) -> dict[str, Any]:
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
    if value is None:
        return "未知"
    text = str(value)
    if ":" in text:
        prefix, name = text.split(":", 1)
        return f"{prefix}: {translate_pokemon(name.strip())}"
    return translate_pokemon(text)


def translate_details_species(details: Any) -> str:
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


def first_pokemon_record(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("species"):
                return item
    return {}


def flatten_move_records(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    flattened: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                flattened.append(item)
            elif isinstance(item, list):
                flattened.extend(m for m in item if isinstance(m, dict))
    return flattened


def move_line(move: dict[str, Any]) -> str:
    return (
        f"{translate_move(move.get('id') or move.get('name'))}"
        f"（属性：{label_or_unknown(move.get('type'))}，威力：{label_or_unknown(move.get('base_power'))}，"
        f"命中：{label_or_unknown(move.get('accuracy'))}，分类：{label_or_unknown(move.get('category'))}）"
    )


def replay_event_to_chinese(event: list[Any]) -> str | None:
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
    lines.append(f"- 玩家 1：{config['players'][0]}")
    lines.append(f"- 玩家 2：{config['players'][1]}")
    lines.append(f"- 队伍来源：{config['team_source']}")
    if record.get("team_preview") and (record["team_preview"].get("player_1") or record["team_preview"].get("player_2")):
        lines.append("- 队伍选出：见第 3 节")
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

    if record.get("team_preview") and (record["team_preview"].get("player_1") or record["team_preview"].get("player_2")):
        lines.append("## 3. 队伍选出记录")
        lines.append("")
        for player_key, title in [("player_1", "玩家 1"), ("player_2", "玩家 2")]:
            selection = record["team_preview"].get(player_key)
            if not selection:
                continue
            selected = ", ".join(str(slot) for slot in selection.get("selected_slots", []))
            lines.append(f"- {title}：模式 `{selection.get('mode')}`，选择编号 `{selected}`，指令 `{selection.get('command')}`")
        lines.append("")
        section_offset = 1
    else:
        section_offset = 0

    lines.append(f"## {3 + section_offset}. 玩家 1 队伍")
    lines.append("")
    for i, mon in enumerate(battle["team"], start=1):
        lines.append(f"{i}. {pokemon_line(mon)}")
    lines.append("")

    lines.append(f"## {4 + section_offset}. 玩家 2 队伍")
    lines.append("")
    for i, mon in enumerate(battle["opponent_team"], start=1):
        lines.append(f"{i}. {pokemon_line(mon)}")
    lines.append("")

    lines.append(f"## {5 + section_offset}. 决策点记录摘要")
    lines.append("")
    lines.append(f"- 玩家 1 决策快照数：{len(record['player_1_observations'])}")
    lines.append(f"- 玩家 2 决策快照数：{len(record['player_2_observations'])}")
    lines.append("")
    lines.append("下面展示玩家 1 视角前 10 个决策点，完整数据见 `record.json`。")
    lines.append("")
    for obs in record["player_1_observations"][:10]:
        active = first_pokemon_record(obs.get("active_pokemon"))
        opp = first_pokemon_record(obs.get("opponent_active_pokemon"))
        moves = flatten_move_records(obs.get("available_moves"))
        move_text = "；".join(move_line(m) for m in moves) or "无可用招式"
        lines.append(f"### 决策点：第 {obs.get('turn')} 回合")
        lines.append(f"- 我方在场：{translate_pokemon(active.get('species'))}（HP {percent(active.get('hp_fraction'))}）")
        lines.append(f"- 对方在场：{translate_pokemon(opp.get('species'))}（HP {percent(opp.get('hp_fraction'))}）")
        lines.append(f"- 可用招式：{move_text}")
        lines.append("")

    lines.append(f"## {6 + section_offset}. 中文对战事件记录")
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

    lines.append(f"## {7 + section_offset}. 导出文件")
    lines.append("")
    lines.append(f"- 可视化 replay：`{record['files']['replay_html']}`")
    lines.append(f"- 完整 JSON 记录：`{record['files']['record_json']}`")
    lines.append(f"- 中文 Markdown 报告：`{record['files']['report_md']}`")
    lines.append("")
    return "\n".join(lines)
