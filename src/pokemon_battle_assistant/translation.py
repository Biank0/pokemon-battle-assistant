"""Local Chinese name translation helpers.

The project keeps a local JSON name table at:
    data/dex/translations/zh_cn_names.json

Runtime code only reads the local file.  The file can be regenerated with:
    .venv/bin/python scripts/build_zh_translation_file.py
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRANSLATION_FILE = PROJECT_ROOT / "data" / "dex" / "translations" / "zh_cn_names.json"

_ID_RE = re.compile(r"[^a-z0-9]+")

# Showdown sometimes uses compact form IDs that do not directly exist in
# PokéAPI's pokemon-species table.  Keep these aliases small and explicit.
# Unknown forms still fall back to the base species through prefix matching.
POKEMON_FORM_ALIASES: dict[str, str] = {
    # Paldean Tauros
    "taurospaldeacombat": "肯泰罗（帕底亚斗战种）",
    "taurospaldeablaze": "肯泰罗（帕底亚火炽种）",
    "taurospaldeaaqua": "肯泰罗（帕底亚水澜种）",
    # Basculegion gender forms
    "basculegionm": "幽尾玄鱼（雄性）",
    "basculegionf": "幽尾玄鱼（雌性）",
    # Ogerpon masks
    "ogerponteal": "厄诡椪（碧草面具）",
    "ogerponwellspring": "厄诡椪（水井面具）",
    "ogerponhearthflame": "厄诡椪（火灶面具）",
    "ogerponcornerstone": "厄诡椪（础石面具）",
    # Maushold / Dudunsparce common forms
    "mausholdfour": "一家鼠（四只家庭）",
    "mausholdthree": "一家鼠（三只家庭）",
    "dudunsparcetwosegment": "土龙节节（二节形态）",
    "dudunsparcethreesegment": "土龙节节（三节形态）",
    # Tatsugiri forms
    "tatsugiricurly": "米立龙（弓姿势）",
    "tatsugiridroopy": "米立龙（垂姿势）",
    "tatsugiristretchy": "米立龙（平挺姿势）",
    # Regional / special forms often emitted by Showdown
    "meowsticf": "超能妙喵（雌性）",
    "meowsticm": "超能妙喵（雄性）",
    "indeedeef": "爱管侍（雌性）",
    "indeedeem": "爱管侍（雄性）",
    "mimikyubusted": "谜拟丘（现形）",
    "eiscuenoice": "冰砌鹅（解冻头）",
    "morpekohangry": "莫鲁贝可（空腹花纹）",
}


def normalize_id(value: Any) -> str:
    """Normalize Showdown/PokeAPI names into comparable IDs."""

    if value is None:
        return ""
    text = str(value).strip().lower()
    return _ID_RE.sub("", text)


@lru_cache(maxsize=1)
def load_zh_names() -> dict[str, Any]:
    """Load local Chinese name table if it exists."""

    if not DEFAULT_TRANSLATION_FILE.exists():
        return {"pokemon": {}, "moves": {}, "items": {}, "abilities": {}}
    with DEFAULT_TRANSLATION_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return {
        "pokemon": data.get("pokemon", {}),
        "moves": data.get("moves", {}),
        "items": data.get("items", {}),
        "abilities": data.get("abilities", {}),
    }


def translate_name(category: str, value: Any) -> str:
    """Translate a Showdown/PokeAPI ID-like value to Simplified Chinese.

    Falls back to the original value when no local translation is available.
    """

    if value is None or value == "" or value == "None":
        return "未知"
    raw = str(value)
    key = normalize_id(raw)
    names = load_zh_names().get(category, {})
    return str(names.get(key, raw))


def translate_pokemon(value: Any) -> str:
    """Translate Pokemon names with a few Showdown-form fallbacks.

    PokéAPI's pokemon-species data often stores the base species, while
    Showdown may emit form IDs such as ``basculegionf``.  If there is no exact
    match, we try a simple gender suffix strip and then a longest-prefix match.
    """

    if value is None or value == "" or value == "None":
        return "未知"
    raw = str(value)
    key = normalize_id(raw)
    names = load_zh_names().get("pokemon", {})
    if key in POKEMON_FORM_ALIASES:
        return POKEMON_FORM_ALIASES[key]
    if key in names:
        return str(names[key])
    if key.endswith(("f", "m")) and key[:-1] in names:
        return str(names[key[:-1]])
    prefix_matches = [candidate for candidate in names if key.startswith(candidate)]
    if prefix_matches:
        return str(names[max(prefix_matches, key=len)])
    return raw


def translate_move(value: Any) -> str:
    return translate_name("moves", value)


def translate_item(value: Any) -> str:
    return translate_name("items", value)


def translate_ability(value: Any) -> str:
    return translate_name("abilities", value)
