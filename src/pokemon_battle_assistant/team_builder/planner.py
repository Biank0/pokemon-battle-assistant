"""阶段1 planner：用户需求 → 队伍蓝图（LLM 第一次调用）。"""
from __future__ import annotations

import json
import re

TYPES_18 = {
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
}
STAT_KEYS = {"hp", "atk", "def", "spa", "spd", "spe"}


def slugify(name: str) -> str:
    """显示名 → dex 官方 slug：小写 + 去掉所有非字母数字字符。

    Blaze → blaze；Solar Power → solarpower；Heavy-Duty Boots → heavydutyboots
    """
    return re.sub(r"[^a-z0-9]", "", name.lower())


def parse_llm_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON 对象（容忍 markdown 代码块包裹/前后废话）。"""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"LLM 输出中找不到 JSON 对象: {text[:120]}...")
    return json.loads(text[start:end + 1])


def _norm_slot(slot: dict, i: int) -> dict:
    """规范化单个角色位：非法属性/键直接剔除，不报错（planner 输出宽松）。"""
    types = [t for t in (slot.get("types") or [])
             if isinstance(t, str) and t.strip().title() in TYPES_18]
    stat_min = {}
    for k, v in (slot.get("stat_min") or {}).items():
        if k in STAT_KEYS and isinstance(v, (int, float)):
            stat_min[k] = max(0, min(255, int(v)))
    focus = [k for k in (slot.get("stat_focus") or []) if k in STAT_KEYS]
    return {
        "role_zh": str(slot.get("role_zh") or f"角色位{i}"),
        "types": [t.title() for t in types],
        "abilities_preferred": [str(a).lower() for a in (slot.get("abilities_preferred") or [])],
        "stat_min": stat_min,
        "stat_focus": focus[:2],
        "notes": str(slot.get("notes") or ""),
    }


def plan(harness, skill, requirement: str, format_id: str) -> dict:
    """需求文本 → 规范化蓝图 dict。"""
    text = harness.chat(skill.blueprint_prompt(format_id, requirement),
                        json_mode=True, temperature=0.3)
    data = parse_llm_json(text)
    slots_raw = data.get("slots") or []
    if not 3 <= len(slots_raw) <= 6:
        raise ValueError(f"蓝图角色位数非法（{len(slots_raw)}，应 3~6）")
    return {
        "strategy": str(data.get("strategy") or ""),
        "slots": [_norm_slot(s, i + 1) for i, s in enumerate(slots_raw)],
    }
