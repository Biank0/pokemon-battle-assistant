"""Lightweight local validators for user-facing commands."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STAT_ORDER = ["hp", "atk", "def", "spa", "spd", "spe"]
REQUIRED_MON_FIELDS = ["species", "moves"]


@dataclass
class ValidationResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.ok = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}


def contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def load_trainer_template(path: str | Path) -> tuple[dict[str, Any] | None, ValidationResult]:
    result = ValidationResult()
    json_path = Path(path)
    if not json_path.exists():
        result.add_error(f"文件不存在：{json_path}")
        return None, result
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        result.add_error(f"JSON 解析失败：第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}")
        return None, result
    if not isinstance(data, dict):
        result.add_error("训练家模版根节点必须是 JSON object。")
        return None, result
    return data, result


def validate_trainer_template(path: str | Path) -> ValidationResult:
    data, result = load_trainer_template(path)
    if data is None:
        return result

    if not data.get("name"):
        result.add_warning("缺少 name 字段。")
    if not data.get("format"):
        result.add_warning("缺少 format 字段，将由 battle 命令默认使用 gen9ou。")

    team = data.get("team")
    if not isinstance(team, list):
        result.add_error("team 字段必须是数组。")
        return result
    if not 1 <= len(team) <= 6:
        result.add_error(f"team 必须包含 1-6 只宝可梦，当前为 {len(team)}。")

    for index, mon in enumerate(team, start=1):
        prefix = f"第 {index} 只宝可梦"
        if not isinstance(mon, dict):
            result.add_error(f"{prefix} 必须是 object。")
            continue
        for field_name in REQUIRED_MON_FIELDS:
            if field_name not in mon:
                result.add_error(f"{prefix} 缺少字段：{field_name}。")

        species = mon.get("species")
        if not isinstance(species, str) or not species.strip():
            result.add_error(f"{prefix} species 不能为空。")
        elif contains_cjk(species):
            result.add_error(f"{prefix} species 应使用 Showdown 英文名，当前包含中文：{species}。")

        moves = mon.get("moves", [])
        if not isinstance(moves, list):
            result.add_error(f"{prefix} moves 必须是数组。")
        else:
            if not 1 <= len(moves) <= 4:
                result.add_error(f"{prefix} moves 必须包含 1-4 个招式，当前为 {len(moves)}。")
            for move_index, move in enumerate(moves, start=1):
                if not isinstance(move, str) or not move.strip():
                    result.add_error(f"{prefix} 第 {move_index} 个招式不能为空。")
                elif contains_cjk(move):
                    result.add_error(f"{prefix} 第 {move_index} 个招式应使用 Showdown 英文名，当前包含中文：{move}。")

        validate_stat_block(result, mon.get("evs", {}), f"{prefix} EV", min_value=0, max_value=252, total_max=510)
        validate_stat_block(result, mon.get("ivs", {}), f"{prefix} IV", min_value=0, max_value=31, total_max=None)

        level = mon.get("level", 100)
        if not isinstance(level, int) or not 1 <= level <= 100:
            result.add_error(f"{prefix} level 必须是 1-100 的整数，当前为 {level!r}。")

    return result


def validate_stat_block(
    result: ValidationResult,
    block: Any,
    label: str,
    *,
    min_value: int,
    max_value: int,
    total_max: int | None,
) -> None:
    if block in ({}, None):
        return
    if not isinstance(block, dict):
        result.add_error(f"{label} 必须是 object。")
        return
    total = 0
    for stat, value in block.items():
        if stat not in STAT_ORDER:
            result.add_warning(f"{label} 包含未知能力项：{stat}。")
            continue
        if not isinstance(value, int):
            result.add_error(f"{label}.{stat} 必须是整数，当前为 {value!r}。")
            continue
        if not min_value <= value <= max_value:
            result.add_error(f"{label}.{stat} 必须在 {min_value}-{max_value}，当前为 {value}。")
        total += value
    if total_max is not None and total > total_max:
        result.add_error(f"{label} 总和不能超过 {total_max}，当前为 {total}。")
