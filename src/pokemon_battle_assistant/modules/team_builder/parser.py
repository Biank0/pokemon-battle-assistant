"""RequirementParser：把自然语言建队需求解析为结构化 BuildIntent。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pokemon_battle_assistant.showdown_db import load_db
from pokemon_battle_assistant.tools.zh import TYPE_ZH
from pokemon_battle_assistant.translation import load_zh_names

# 顺序即优先级：越靠前越具体
STYLE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("trick_room", ("空间", "戏法空间", "trick room")),
    ("sun", ("晴天", "太阳队", "晴队", "sun team")),
    ("rain", ("雨天", "雨队", "rain team")),
    ("sand", ("沙暴", "沙队", "sand team")),
    ("snow", ("雪天", "雪队", "snow team")),
    ("hyper_offense", ("速攻", "快攻", "hyper offense")),
    ("stall", ("受队", "消耗", "stall")),
    ("offensive", ("进攻", "攻击", "offense", "offensive")),
    ("defensive", ("防守", "防守反击", "defensive")),
    ("balanced", ("平衡", "均衡", "balance", "balanced")),
]

_ZH_TYPE_RE = re.compile(
    "(" + "|".join(sorted(TYPE_ZH.values(), key=len, reverse=True)) + ")系"
)


@dataclass
class BuildIntent:
    """结构化建队意图。"""

    requirement: str = ""
    core: str | None = None
    core_display: str | None = None
    style: str | None = None
    counters: list[str] = field(default_factory=list)
    must_include: list[str] = field(default_factory=list)

    def to_prompt_text(self) -> str:
        lines = [f"用户原始需求：{self.requirement}"]
        if self.core:
            lines.append(f"核心宝可梦：{self.core_display or self.core}")
        if self.style:
            lines.append(f"偏好风格：{self.style}")
        if self.counters:
            lines.append("需要克制的属性：" + "、".join(self.counters))
        if self.must_include:
            lines.append("需要包含的宝可梦：" + "、".join(self.must_include))
        return "\n".join(lines)


def _pokedex_entries() -> list[tuple[str, str]]:
    """返回按名字长度降序的 (id, 英文名) 列表。"""
    entries: list[tuple[str, str]] = []
    for pid, entry in load_db().get("pokedex", {}).items():
        name = entry.get("name") if isinstance(entry, dict) else None
        if name:
            entries.append((str(pid), str(name)))
    entries.sort(key=lambda item: len(item[1]), reverse=True)
    return entries


class RequirementParser:
    """规则式需求解析（可测试、离线）；LLM 拿到意图后负责发挥。"""

    def parse(self, requirement: str) -> BuildIntent:
        text = (requirement or "").strip()
        lowered = text.lower()
        found: list[tuple[str, str]] = []

        zh_table = load_zh_names().get("pokemon", {})
        zh_hits = [(pid, zh) for pid, zh in zh_table.items() if zh and zh in text]
        zh_hits.sort(key=lambda item: len(item[1]), reverse=True)
        found.extend(zh_hits)

        for pid, name in _pokedex_entries():
            if name.lower() in lowered:
                found.append((pid, name))

        seen: set[str] = set()
        ordered: list[tuple[str, str]] = []
        for pid, display in found:
            if pid not in seen:
                seen.add(pid)
                ordered.append((pid, display))

        intent = BuildIntent(requirement=text)
        if ordered:
            intent.core = ordered[0][0]
            intent.core_display = ordered[0][1]
            intent.must_include = [pid for pid, _ in ordered]

        for style, words in STYLE_KEYWORDS:
            zh_words = [w for w in words if not w.isascii()]
            en_words = [w for w in words if w.isascii()]
            if any(w in text for w in zh_words) or any(w in lowered for w in en_words):
                intent.style = style
                break

        zh_to_en = {zh: en for en, zh in TYPE_ZH.items()}
        for zh_name in _ZH_TYPE_RE.findall(text):
            en = zh_to_en.get(zh_name)
            if en and en not in intent.counters:
                intent.counters.append(en)
        for en in TYPE_ZH:
            if re.search(rf"\b{en.lower()}\b", lowered) and en not in intent.counters:
                intent.counters.append(en)
        return intent
