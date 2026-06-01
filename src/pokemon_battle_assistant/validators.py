"""Team validators for user-facing commands.

The local validator catches common template mistakes and formats them in a way
that is easier to understand than raw Showdown errors. Full format legality is
still delegated to Pokemon Showdown by :mod:`showdown_validator`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pokemon_battle_assistant.showdown_db import (
    get_item,
    get_move,
    get_nature,
    get_pokemon,
    get_pokemon_abilities,
    load_db,
)

STAT_ORDER = ["hp", "atk", "def", "spa", "spd", "spe"]
REQUIRED_MON_FIELDS = ["species", "moves"]
VALID_TYPES = {
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison",
    "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
}


@dataclass
class ValidationIssue:
    severity: str
    message: str
    source: str = "local"
    code: str = ""
    pokemon_index: int | None = None
    field: str | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "source": self.source,
            "code": self.code,
            "message": self.message,
            "pokemon_index": self.pokemon_index,
            "field": self.field,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)

    def add_error(
        self,
        message: str,
        *,
        code: str = "",
        pokemon_index: int | None = None,
        field: str | None = None,
        suggestion: str | None = None,
        source: str = "local",
    ) -> None:
        self.ok = False
        self.errors.append(message)
        self.issues.append(
            ValidationIssue(
                severity="error",
                source=source,
                code=code,
                message=message,
                pokemon_index=pokemon_index,
                field=field,
                suggestion=suggestion,
            )
        )

    def add_warning(
        self,
        message: str,
        *,
        code: str = "",
        pokemon_index: int | None = None,
        field: str | None = None,
        suggestion: str | None = None,
        source: str = "local",
    ) -> None:
        self.warnings.append(message)
        self.issues.append(
            ValidationIssue(
                severity="warning",
                source=source,
                code=code,
                message=message,
                pokemon_index=pokemon_index,
                field=field,
                suggestion=suggestion,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def normalize_id(text: str) -> str:
    return "".join(char for char in text.lower() if char.isalnum())


def load_trainer_template(path: str | Path) -> tuple[dict[str, Any] | None, ValidationResult]:
    result = ValidationResult()
    json_path = Path(path)
    if not json_path.exists():
        result.add_error(f"文件不存在：{json_path}", code="file_not_found")
        return None, result
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        result.add_error(f"JSON 解析失败：第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}", code="json_decode_error")
        return None, result
    if not isinstance(data, dict):
        result.add_error("训练家模版根节点必须是 JSON object。", code="invalid_root")
        return None, result
    return data, result


def validate_trainer_template(path: str | Path) -> ValidationResult:
    data, result = load_trainer_template(path)
    if data is None:
        return result
    validate_trainer_data(data, result=result)
    return result


def validate_trainer_data(data: dict[str, Any], *, result: ValidationResult | None = None) -> ValidationResult:
    result = result or ValidationResult()

    if not data.get("name"):
        result.add_warning("缺少 name 字段。", code="missing_name")
    if not data.get("format"):
        result.add_warning("缺少 format 字段，将由 battle 命令默认使用 gen9ou。", code="missing_format")

    team = data.get("team")
    if not isinstance(team, list):
        result.add_error("team 字段必须是数组。", code="invalid_team")
        return result
    if not 1 <= len(team) <= 6:
        result.add_error(f"team 必须包含 1-6 只宝可梦，当前为 {len(team)}。", code="team_size")

    for index, mon in enumerate(team, start=1):
        validate_one_pokemon(result, mon, index)

    return result


def validate_one_pokemon(result: ValidationResult, mon: Any, index: int) -> None:
    prefix = f"第 {index} 只宝可梦"
    if not isinstance(mon, dict):
        result.add_error(f"{prefix} 必须是 object。", code="invalid_pokemon", pokemon_index=index)
        return

    for field_name in REQUIRED_MON_FIELDS:
        if field_name not in mon:
            result.add_error(f"{prefix} 缺少字段：{field_name}。", code="missing_field", pokemon_index=index, field=field_name)

    species = mon.get("species")
    species_id = ""
    if not isinstance(species, str) or not species.strip():
        result.add_error(f"{prefix} species 不能为空。", code="empty_species", pokemon_index=index, field="species")
    elif contains_cjk(species):
        result.add_error(
            f"{prefix} species 应使用 Showdown 英文名，当前包含中文：{species}。",
            code="cjk_species",
            pokemon_index=index,
            field="species",
            suggestion="请在 pba team create 中用中文搜索，然后选择结果；保存的模版会自动写入英文名。",
        )
    else:
        species_id = normalize_id(species)
        if get_pokemon(species_id) is None:
            result.add_error(f"{prefix} species 无法识别：{species}。", code="unknown_species", pokemon_index=index, field="species")

    validate_optional_name(result, mon, index, "item", "道具", get_item, allow_empty=True)
    validate_optional_name(result, mon, index, "nature", "性格", get_nature, allow_empty=True)
    validate_ability(result, mon, index, species_id)
    validate_tera_type(result, mon, index)
    validate_moves(result, mon, index, species_id)

    validate_stat_block(result, mon.get("evs", {}), f"{prefix} EV", min_value=0, max_value=252, total_max=510, pokemon_index=index, field="evs")
    validate_stat_block(result, mon.get("ivs", {}), f"{prefix} IV", min_value=0, max_value=31, total_max=None, pokemon_index=index, field="ivs")

    level = mon.get("level", 100)
    if not isinstance(level, int) or not 1 <= level <= 100:
        result.add_error(f"{prefix} level 必须是 1-100 的整数，当前为 {level!r}。", code="invalid_level", pokemon_index=index, field="level")


def validate_optional_name(result: ValidationResult, mon: dict[str, Any], index: int, field: str, label: str, lookup_fn, *, allow_empty: bool) -> None:
    value = mon.get(field, "")
    if allow_empty and value in (None, ""):
        return
    if not isinstance(value, str) or not value.strip():
        result.add_error(f"第 {index} 只宝可梦 {label} 不能为空。", code=f"empty_{field}", pokemon_index=index, field=field)
        return
    if contains_cjk(value):
        result.add_error(f"第 {index} 只宝可梦 {label} 应使用 Showdown 英文名，当前包含中文：{value}。", code=f"cjk_{field}", pokemon_index=index, field=field)
        return
    if lookup_fn(value) is None:
        result.add_error(f"第 {index} 只宝可梦 {label} 无法识别：{value}。", code=f"unknown_{field}", pokemon_index=index, field=field)


def validate_ability(result: ValidationResult, mon: dict[str, Any], index: int, species_id: str) -> None:
    ability = mon.get("ability", "")
    if ability in (None, ""):
        return
    if not isinstance(ability, str) or not ability.strip():
        result.add_error(f"第 {index} 只宝可梦特性不能为空。", code="empty_ability", pokemon_index=index, field="ability")
        return
    if contains_cjk(ability):
        result.add_error(f"第 {index} 只宝可梦特性应使用 Showdown 英文名，当前包含中文：{ability}。", code="cjk_ability", pokemon_index=index, field="ability")
        return
    abilities_db = load_db().get("abilities", {})
    if normalize_id(ability) not in abilities_db:
        result.add_error(f"第 {index} 只宝可梦特性无法识别：{ability}。", code="unknown_ability", pokemon_index=index, field="ability")
        return
    if species_id and get_pokemon(species_id) is not None:
        legal_abilities = get_pokemon_abilities(species_id)
        legal_ability_ids = {normalize_id(legal_ability) for legal_ability in legal_abilities}
        if normalize_id(ability) not in legal_ability_ids:
            result.add_error(
                f"第 {index} 只宝可梦不能使用特性 {ability}；可用特性：{', '.join(legal_abilities)}。",
                code="illegal_ability_for_species",
                pokemon_index=index,
                field="ability",
            )


def validate_tera_type(result: ValidationResult, mon: dict[str, Any], index: int) -> None:
    tera_type = mon.get("tera_type", "")
    if tera_type in (None, ""):
        return
    if not isinstance(tera_type, str) or tera_type not in VALID_TYPES:
        result.add_error(
            f"第 {index} 只宝可梦太晶属性必须是合法英文属性，当前为：{tera_type!r}。",
            code="invalid_tera_type",
            pokemon_index=index,
            field="tera_type",
            suggestion="可用属性包括：" + ", ".join(sorted(VALID_TYPES)),
        )


def validate_moves(result: ValidationResult, mon: dict[str, Any], index: int, species_id: str) -> None:
    prefix = f"第 {index} 只宝可梦"
    moves = mon.get("moves", [])
    if not isinstance(moves, list):
        result.add_error(f"{prefix} moves 必须是数组。", code="invalid_moves", pokemon_index=index, field="moves")
        return
    if not 1 <= len(moves) <= 4:
        result.add_error(f"{prefix} moves 必须包含 1-4 个招式，当前为 {len(moves)}。", code="move_count", pokemon_index=index, field="moves")

    seen: set[str] = set()
    for move_index, move in enumerate(moves, start=1):
        field = f"moves[{move_index - 1}]"
        if not isinstance(move, str) or not move.strip():
            result.add_error(f"{prefix} 第 {move_index} 个招式不能为空。", code="empty_move", pokemon_index=index, field=field)
            continue
        if contains_cjk(move):
            result.add_error(
                f"{prefix} 第 {move_index} 个招式应使用 Showdown 英文名，当前包含中文：{move}。",
                code="cjk_move",
                pokemon_index=index,
                field=field,
                suggestion="请在 pba team create 中用中文搜索招式并选择结果。",
            )
            continue
        move_id = normalize_id(move)
        if move_id in seen:
            result.add_error(f"{prefix} 招式重复：{move}。", code="duplicate_move", pokemon_index=index, field=field)
        seen.add(move_id)
        if get_move(move_id) is None:
            result.add_error(f"{prefix} 第 {move_index} 个招式无法识别：{move}。", code="unknown_move", pokemon_index=index, field=field)
            continue


def validate_stat_block(
    result: ValidationResult,
    block: Any,
    label: str,
    *,
    min_value: int,
    max_value: int,
    total_max: int | None,
    pokemon_index: int | None = None,
    field: str | None = None,
) -> None:
    if block in ({}, None):
        return
    if not isinstance(block, dict):
        result.add_error(f"{label} 必须是 object。", code="invalid_stat_block", pokemon_index=pokemon_index, field=field)
        return
    total = 0
    for stat, value in block.items():
        stat_field = f"{field}.{stat}" if field else stat
        if stat not in STAT_ORDER:
            result.add_warning(f"{label} 包含未知能力项：{stat}。", code="unknown_stat", pokemon_index=pokemon_index, field=stat_field)
            continue
        if not isinstance(value, int):
            result.add_error(f"{label}.{stat} 必须是整数，当前为 {value!r}。", code="invalid_stat_value", pokemon_index=pokemon_index, field=stat_field)
            continue
        if not min_value <= value <= max_value:
            result.add_error(f"{label}.{stat} 必须在 {min_value}-{max_value}，当前为 {value}。", code="stat_value_range", pokemon_index=pokemon_index, field=stat_field)
        total += value
    if total_max is not None and total > total_max:
        result.add_error(f"{label} 总和不能超过 {total_max}，当前为 {total}。", code="stat_total_range", pokemon_index=pokemon_index, field=field)
