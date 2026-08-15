"""共享的属性名常量与中英映射（建队工具用）。"""

from __future__ import annotations

ALL_TYPES: list[str] = [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
]

TYPE_ZH: dict[str, str] = {
    "Normal": "一般", "Fire": "火", "Water": "水", "Electric": "电",
    "Grass": "草", "Ice": "冰", "Fighting": "格斗", "Poison": "毒",
    "Ground": "地面", "Flying": "飞行", "Psychic": "超能力", "Bug": "虫",
    "Rock": "岩石", "Ghost": "幽灵", "Dragon": "龙", "Dark": "恶",
    "Steel": "钢", "Fairy": "妖精",
}

TYPE_ZH_TO_EN: dict[str, str] = {zh: en for en, zh in TYPE_ZH.items()}


def type_zh(type_name: str) -> str:
    return TYPE_ZH.get(type_name, type_name)
