"""对战工具注册表：Battle Module 的 LLM function-calling 接口。

与建队工具（``tools/__init__.py``）的区别：
- 对战工具依赖当前局面（``ToolContext``：observation + memory）
- ``threat_assessment`` 无需 LLM 传参，直接从 context 取 observation
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .ability_lookup import lookup_ability
from .damage_calculator import estimate_damage
from .speed_comparator import compare_speed
from .threat_assessment import assess_threat
from .type_analyzer import analyze_type, defender_weakness_profile

ToolFn = Callable[..., dict]


@dataclass
class ToolContext:
    """一次回合决策时可用的上下文。"""

    observation: Any = None  # BattleObservation | None
    memory: Any = None  # MemoryManager | None


def _type_analyze(args: dict, ctx: ToolContext) -> dict:
    move_type = args.get("move_type") or args.get("type")
    defender_types = args.get("defender_types") or args.get("types")
    if not isinstance(move_type, str):
        return {"ok": False, "error": "type_analyzer 需要 move_type 字符串参数"}
    if isinstance(defender_types, list) and defender_types:
        return analyze_type(move_type, [str(t) for t in defender_types])
    opponent = getattr(ctx.observation, "opponent_active", None)
    opp_types = getattr(opponent, "types", None) if opponent else None
    if opp_types:
        return analyze_type(move_type, [str(t) for t in opp_types])
    return {"ok": False, "error": "type_analyzer 需要 defender_types，或上下文中有对方在场宝可梦"}


def _weakness_profile(args: dict, ctx: ToolContext) -> dict:
    defender_types = args.get("defender_types") or args.get("types")
    if isinstance(defender_types, list) and defender_types:
        return defender_weakness_profile([str(t) for t in defender_types])
    opponent = getattr(ctx.observation, "opponent_active", None)
    opp_types = getattr(opponent, "types", None) if opponent else None
    if opp_types:
        return defender_weakness_profile([str(t) for t in opp_types])
    return {"ok": False, "error": "weakness_profile 需要 defender_types，或上下文中有对方在场宝可梦"}


def _damage(args: dict, ctx: ToolContext) -> dict:
    attacker = args.get("attacker")
    defender = args.get("defender")
    move = args.get("move")
    if not isinstance(move, dict):
        return {"ok": False, "error": "damage_calculator 需要 move（招式 dict）参数"}
    if not isinstance(attacker, dict):
        attacker = _active_to_dict(getattr(ctx.observation, "my_active", None))
    if not isinstance(defender, dict):
        defender = _active_to_dict(getattr(ctx.observation, "opponent_active", None))
    if attacker is None or defender is None:
        return {"ok": False, "error": "damage_calculator 需要 attacker/defender，或上下文中有双方在场宝可梦"}
    return estimate_damage(attacker, defender, move)


def _speed(args: dict, ctx: ToolContext) -> dict:
    mine = args.get("my_pokemon") or args.get("mine")
    opponent = args.get("opponent_pokemon") or args.get("opponent")
    if not isinstance(mine, dict):
        mine = _active_to_dict(getattr(ctx.observation, "my_active", None))
    if not isinstance(opponent, dict):
        opponent = _active_to_dict(getattr(ctx.observation, "opponent_active", None))
    if mine is None or opponent is None:
        return {"ok": False, "error": "speed_comparator 需要双方宝可梦信息（参数或上下文）"}
    return compare_speed(mine, opponent)


def _threat(args: dict, ctx: ToolContext) -> dict:
    observation = ctx.observation
    if observation is None:
        return {"ok": False, "error": "threat_assessment 需要当前局面上下文（observation）"}
    return assess_threat(observation)


def _ability(args: dict, ctx: ToolContext) -> dict:
    species = args.get("species")
    if not isinstance(species, str):
        return {"ok": False, "error": "ability_lookup 需要 species 字符串参数"}
    item = args.get("item")
    return lookup_ability(species, item if isinstance(item, str) else None)


def _active_to_dict(mon: Any) -> dict[str, Any] | None:
    if mon is None:
        return None
    if hasattr(mon, "to_dict"):
        return mon.to_dict()
    if isinstance(mon, dict):
        return mon
    return None


BATTLE_TOOLS: dict[str, dict[str, Any]] = {
    "type_analyzer": {
        "fn": _type_analyze,
        "description": (
            "属性克制查询：一个攻击属性对防守方属性组合的倍率。"
            "不传 defender_types 时默认查当前对方在场宝可梦。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "move_type": {"type": "string", "description": "攻击属性，如 Water / 水"},
                "defender_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "防守方属性组合；缺省用对方在场宝可梦",
                },
            },
            "required": ["move_type"],
        },
    },
    "weakness_profile": {
        "fn": _weakness_profile,
        "description": "查询防守方（默认当前对方在场宝可梦）面对全部属性的弱点/抗性/免疫表。",
        "parameters": {
            "type": "object",
            "properties": {
                "defender_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "防守方属性组合；缺省用对方在场宝可梦",
                },
            },
            "required": [],
        },
    },
    "damage_calculator": {
        "fn": _damage,
        "description": (
            "伤害估算：50级简化公式，估算一个招式对目标的伤害百分比区间和击倒概率。"
            "attacker/defender 缺省用当前双方在场宝可梦。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "move": {
                    "type": "object",
                    "description": "招式 {name/type/base_power/category}，至少给 name",
                },
                "attacker": {"type": "object", "description": "攻击方 {species,...}；缺省用我方在场"},
                "defender": {"type": "object", "description": "防守方 {species,hp_percent,...}；缺省用对方在场"},
            },
            "required": ["move"],
        },
    },
    "speed_comparator": {
        "fn": _speed,
        "description": "速度线比较：判断我方与对方在场宝可梦谁先手（含麻痹修正）。参数缺省用当前双方在场宝可梦。",
        "parameters": {
            "type": "object",
            "properties": {
                "my_pokemon": {"type": "object", "description": "我方宝可梦 {species,speed?}；缺省用我方在场"},
                "opponent_pokemon": {"type": "object", "description": "对方宝可梦 {species,speed?}；缺省用对方在场"},
            },
            "required": [],
        },
    },
    "threat_assessment": {
        "fn": _threat,
        "description": "威胁评估：评估对方在场宝可梦已揭示招式对我方的威胁等级、最危险招式、我方最佳反制。无需传参。",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "ability_lookup": {
        "fn": _ability,
        "description": "特性/道具查询：查一只宝可梦的全部可能特性（含隐藏特性）和可选道具效果说明。",
        "parameters": {
            "type": "object",
            "properties": {
                "species": {"type": "string", "description": "宝可梦名（英文或中文）"},
                "item": {"type": "string", "description": "可选：道具名，附带查询道具效果"},
            },
            "required": ["species"],
        },
    },
}


def run_battle_tool(name: str, arguments: dict | None, context: ToolContext | None = None) -> dict[str, Any]:
    """执行一个对战工具，异常时返回错误 dict 而不是抛出。"""
    spec = BATTLE_TOOLS.get(name)
    if spec is None:
        return {"ok": False, "error": f"未知工具：{name}"}
    ctx = context or ToolContext()
    try:
        return spec["fn"](dict(arguments or {}), ctx)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def battle_tool_specs() -> list[dict[str, Any]]:
    """输出 OpenAI function-calling 格式的工具描述。"""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": spec["description"],
                "parameters": spec["parameters"],
            },
        }
        for name, spec in BATTLE_TOOLS.items()
    ]
