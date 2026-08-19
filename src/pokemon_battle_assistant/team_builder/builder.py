"""阶段3 builder：蓝图 + 候选池 + skill → 完整队伍 JSON（LLM 第二次调用）。"""
from __future__ import annotations

from .planner import parse_llm_json


def build(harness, skill, format_id: str, blueprint: dict, pools_text: str) -> tuple[dict, str]:
    """返回 (队伍 dict, 原始输出文本——修复轮回喂用)。"""
    text = harness.chat(skill.builder_prompt(format_id, blueprint, pools_text),
                        json_mode=True, temperature=0.5)
    return parse_llm_json(text), text


def repair(harness, skill, format_id: str, blueprint: dict, pools_text: str,
           team_json_text: str, errors: list[str]) -> tuple[dict, str]:
    """带错误清单的修复轮。"""
    text = harness.chat(
        skill.repair_prompt(format_id, blueprint, pools_text, team_json_text, errors),
        json_mode=True, temperature=0.2)
    return parse_llm_json(text), text
