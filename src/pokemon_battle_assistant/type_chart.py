"""Pokemon type effectiveness helpers.

The chart uses English type names because they are concise and easy to reuse
with common Pokemon data sources.  The user-facing explanation can translate or
explain them later if needed.
"""

from __future__ import annotations

# Attacking type -> defending type -> multiplier.
# Missing entries mean neutral damage.
TYPE_CHART: dict[str, dict[str, float]] = {
    "Normal": {"Rock": 0.5, "Ghost": 0.0, "Steel": 0.5},
    "Fire": {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 2.0, "Bug": 2.0, "Rock": 0.5, "Dragon": 0.5, "Steel": 2.0},
    "Water": {"Fire": 2.0, "Water": 0.5, "Grass": 0.5, "Ground": 2.0, "Rock": 2.0, "Dragon": 0.5},
    "Electric": {"Water": 2.0, "Electric": 0.5, "Grass": 0.5, "Ground": 0.0, "Flying": 2.0, "Dragon": 0.5},
    "Grass": {"Fire": 0.5, "Water": 2.0, "Grass": 0.5, "Poison": 0.5, "Ground": 2.0, "Flying": 0.5, "Bug": 0.5, "Rock": 2.0, "Dragon": 0.5, "Steel": 0.5},
    "Ice": {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 0.5, "Ground": 2.0, "Flying": 2.0, "Dragon": 2.0, "Steel": 0.5},
    "Fighting": {"Normal": 2.0, "Ice": 2.0, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Rock": 2.0, "Ghost": 0.0, "Dark": 2.0, "Steel": 2.0, "Fairy": 0.5},
    "Poison": {"Grass": 2.0, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0.0, "Fairy": 2.0},
    "Ground": {"Fire": 2.0, "Electric": 2.0, "Grass": 0.5, "Poison": 2.0, "Flying": 0.0, "Bug": 0.5, "Rock": 2.0, "Steel": 2.0},
    "Flying": {"Electric": 0.5, "Grass": 2.0, "Fighting": 2.0, "Bug": 2.0, "Rock": 0.5, "Steel": 0.5},
    "Psychic": {"Fighting": 2.0, "Poison": 2.0, "Psychic": 0.5, "Dark": 0.0, "Steel": 0.5},
    "Bug": {"Fire": 0.5, "Grass": 2.0, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5, "Psychic": 2.0, "Ghost": 0.5, "Dark": 2.0, "Steel": 0.5, "Fairy": 0.5},
    "Rock": {"Fire": 2.0, "Ice": 2.0, "Fighting": 0.5, "Ground": 0.5, "Flying": 2.0, "Bug": 2.0, "Steel": 0.5},
    "Ghost": {"Normal": 0.0, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5},
    "Dragon": {"Dragon": 2.0, "Steel": 0.5, "Fairy": 0.0},
    "Dark": {"Fighting": 0.5, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5, "Fairy": 0.5},
    "Steel": {"Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2.0, "Rock": 2.0, "Steel": 0.5, "Fairy": 2.0},
    "Fairy": {"Fire": 0.5, "Fighting": 2.0, "Poison": 0.5, "Dragon": 2.0, "Dark": 2.0, "Steel": 0.5},
}


# 中文属性名 -> 英文属性名（LLM 常用中文调用工具）
ZH_TYPE_NAMES: dict[str, str] = {
    "一般": "Normal", "普通": "Normal",
    "火": "Fire", "水": "Water", "电": "Electric", "草": "Grass", "冰": "Ice",
    "格斗": "Fighting", "毒": "Poison", "地面": "Ground", "飞行": "Flying",
    "超能力": "Psychic", "超能": "Psychic", "虫": "Bug", "岩石": "Rock",
    "幽灵": "Ghost", "鬼": "Ghost", "龙": "Dragon", "恶": "Dark",
    "钢": "Steel", "妖精": "Fairy",
}


def normalize_type(type_name: str | None) -> str:
    """Normalize loose user input into title-cased type names.

    依次尝试：英文精确 -> 中文精确 -> 英文子串（容忍 ``Water (Pokemon Type) Object``
    这类被污染的输入）-> 中文子串（按长度降序，避免"超能力"被"超能"抢先）。
    """

    if not type_name:
        return "Unknown"
    raw = str(type_name).strip()
    titled = raw.title()
    if titled in TYPE_CHART:
        return titled
    if raw in ZH_TYPE_NAMES:
        return ZH_TYPE_NAMES[raw]
    lowered = raw.lower()
    for english in TYPE_CHART:
        if english.lower() in lowered:
            return english
    for zh in sorted(ZH_TYPE_NAMES, key=len, reverse=True):
        if zh in raw:
            return ZH_TYPE_NAMES[zh]
    return titled


def get_type_multiplier(move_type: str | None, defender_types: list[str]) -> float:
    """Return the combined type multiplier for one move against one defender."""

    attacking_type = normalize_type(move_type)
    if attacking_type == "Unknown":
        return 1.0

    multiplier = 1.0
    matchups = TYPE_CHART.get(attacking_type, {})
    for defender_type in defender_types:
        multiplier *= matchups.get(normalize_type(defender_type), 1.0)
    return multiplier


def describe_multiplier(multiplier: float) -> str:
    """Convert a numeric multiplier into a short Chinese explanation."""

    if multiplier == 0:
        return "无效"
    if multiplier >= 4:
        return "四倍克制"
    if multiplier >= 2:
        return "效果拔群"
    if multiplier == 1:
        return "正常效果"
    if multiplier <= 0.25:
        return "四倍抵抗"
    return "效果不佳"
