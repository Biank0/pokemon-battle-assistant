"""建队工具注册表：统一的 LLM function-calling 接口。

约定：
- 每个工具函数接收 dict 参数，返回 JSON 可序列化的 dict
- ``run_tool`` 统一兜底异常，保证 LLM 循环不会因工具崩溃而中断
- ``team_builder_tool_specs`` 输出 OpenAI 兼容的工具描述
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .coverage_analyzer import analyze_coverage
from .meta_analyzer import analyze_meta
from .synergy_checker import check_synergy
from .team_validator import validate_team

ToolFn = Callable[[dict], dict]


def _meta(args: dict) -> dict:
    return analyze_meta(str(args.get("format") or "gen9bssregi"))


def _synergy(args: dict) -> dict:
    team = args.get("team")
    if not isinstance(team, list):
        return {"ok": False, "error": "synergy_checker 需要 team（宝可梦列表）参数"}
    return check_synergy(team)


def _coverage(args: dict) -> dict:
    team = args.get("team")
    if not isinstance(team, list):
        return {"ok": False, "error": "coverage_analyzer 需要 team（宝可梦列表）参数"}
    return analyze_coverage(team)


def _validate(args: dict) -> dict:
    team = args.get("team")
    if team is None:
        return {"ok": False, "error": "team_validator 需要 team 参数"}
    return validate_team(team, str(args.get("format") or "gen9bssregi"))


TEAM_BUILDER_TOOLS: dict[str, dict[str, Any]] = {
    "meta_analyzer": {
        "fn": _meta,
        "description": "查询当前对战环境的热门宝可梦（种族值统计）与本地示例队伍核心。",
        "parameters": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "description": "对战格式，默认 gen9bssregi"},
            },
            "required": [],
        },
    },
    "synergy_checker": {
        "fn": _synergy,
        "description": "检查候选队伍 6 只之间的防守属性互补性（共享弱点/集体抵抗）。",
        "parameters": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "array",
                    "description": "宝可梦列表，每项至少包含 species 字段",
                    "items": {"type": "object"},
                },
            },
            "required": ["team"],
        },
    },
    "coverage_analyzer": {
        "fn": _coverage,
        "description": "分析候选队伍全部攻击招式的打击面覆盖（克制/被抵抗属性）。",
        "parameters": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "array",
                    "description": "宝可梦列表，每项包含 species 与 moves 字段",
                    "items": {"type": "object"},
                },
            },
            "required": ["team"],
        },
    },
    "team_validator": {
        "fn": _validate,
        "description": "校验队伍是否符合 BSS 规则（本地结构校验 + Showdown 权威校验）。",
        "parameters": {
            "type": "object",
            "properties": {
                "team": {
                    "type": "object",
                    "description": "完整队伍模板 {name, format, team:[...]}，或直接传宝可梦列表",
                },
                "format": {"type": "string", "description": "对战格式，默认 gen9bssregi"},
            },
            "required": ["team"],
        },
    },
}


def run_tool(name: str, arguments: dict | None) -> dict[str, Any]:
    """执行一个建队工具，异常时返回错误 dict 而不是抛出。"""
    spec = TEAM_BUILDER_TOOLS.get(name)
    if spec is None:
        return {"ok": False, "error": f"未知工具：{name}"}
    try:
        return spec["fn"](dict(arguments or {}))
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def team_builder_tool_specs() -> list[dict[str, Any]]:
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
        for name, spec in TEAM_BUILDER_TOOLS.items()
    ]
