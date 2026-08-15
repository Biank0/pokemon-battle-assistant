"""Offline Showdown data lookup for trainer template creation.

Supports both English and Chinese name search via the local translation table.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "showdown_db.json"
ZH_PATH = Path(__file__).resolve().parents[2] / "data" / "translations" / "zh_cn_names.json"


@lru_cache(maxsize=1)
def load_db() -> dict:
    with open(DB_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_zh_reverse() -> dict[str, dict[str, str]]:
    """Build reverse lookup: category -> {chinese_name -> english_id}."""
    if not ZH_PATH.exists():
        return {}
    with open(ZH_PATH, encoding="utf-8") as f:
        data = json.load(f)
    reverse: dict[str, dict[str, str]] = {}
    for category in ("pokemon", "moves", "items", "abilities"):
        mapping = data.get(category, {})
        rev: dict[str, str] = {}
        for eng_id, zh_name in mapping.items():
            rev[zh_name] = eng_id
        reverse[category] = rev
    return reverse


@lru_cache(maxsize=1)
def _load_zh_forward() -> dict[str, dict[str, str]]:
    """Forward lookup: category -> {english_id -> chinese_name}."""
    if not ZH_PATH.exists():
        return {}
    with open(ZH_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {cat: data.get(cat, {}) for cat in ("pokemon", "moves", "items", "abilities")}


def _normalize(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())


def _is_cjk(text: str) -> bool:
    return any("一" <= c <= "鿿" for c in text)


def _zh_name(category: str, eng_id: str) -> str:
    """Get the Chinese name for an English ID, or empty string."""
    fwd = _load_zh_forward()
    return fwd.get(category, {}).get(eng_id, "")


def _zh_match(category: str, query: str, eng_id: str) -> bool:
    """Check if the Chinese name for eng_id contains the query."""
    zh = _zh_name(category, eng_id)
    return bool(zh and query in zh)


def _resolve_zh_query(category: str, query: str) -> str | None:
    """If query is Chinese, try to resolve it to an English ID."""
    reverse = _load_zh_reverse()
    cat_rev = reverse.get(category, {})
    if query in cat_rev:
        return cat_rev[query]
    for zh_name, eng_id in cat_rev.items():
        if query in zh_name:
            return eng_id
    return None


def _match_rank(query_id: str, entry_id: str, entry_name: str) -> int | None:
    """Rank an English match: 0=exact, 1=prefix, 2=substring, None=no match."""
    name_id = _normalize(entry_name)
    if entry_id == query_id or name_id == query_id:
        return 0
    if entry_id.startswith(query_id) or name_id.startswith(query_id):
        return 1
    if query_id in entry_id or query_id in name_id:
        return 2
    return None


def _ranked_search(category: str, query: str, limit: int, *, skip: Callable[[dict], bool] | None = None) -> list[dict]:
    """Generic search: collect all matches, rank by quality, then truncate.

    Ranking beats the previous early-break behavior, which could discard a better
    match (e.g. an exact name) that happened to be iterated after `limit` weaker
    substring hits.
    """
    q = _normalize(query)
    is_zh = _is_cjk(query)
    table = load_db()[category if category != "pokemon" else "pokedex"]
    scored: list[tuple[int, int, dict]] = []
    for order, (eid, entry) in enumerate(table.items()):
        if skip and skip(entry):
            continue
        rank = _match_rank(q, eid, entry["name"]) if q else None
        if rank is None and is_zh and _zh_match(category, query, eid):
            rank = 3
        if rank is None:
            continue
        scored.append((rank, order, {"id": eid, **entry}))
    scored.sort(key=lambda item: (item[0], item[1]))
    return [result for _, _, result in scored[:limit]]


def get_pokemon(species_id: str) -> dict | None:
    return load_db()["pokedex"].get(_normalize(species_id))


def search_pokemon(query: str, limit: int = 10) -> list[dict]:
    return _ranked_search("pokemon", query, limit, skip=lambda entry: entry.get("num", 0) <= 0)


def get_pokemon_abilities(species_id: str) -> list[str]:
    mon = get_pokemon(species_id)
    if not mon:
        return []
    abilities = mon.get("abilities", {})
    return list(dict.fromkeys(abilities.values()))


def get_learnable_moves(species_id: str) -> list[str]:
    sid = _normalize(species_id)
    learnsets = load_db()["learnsets"]
    entry = learnsets.get(sid, {})
    learnset = entry.get("learnset", {})
    moves_db = load_db()["moves"]
    result = []
    for move_id in sorted(learnset.keys()):
        move = moves_db.get(move_id)
        if move:
            result.append(move["name"])
    return result


def get_move(move_id: str) -> dict | None:
    return load_db()["moves"].get(_normalize(move_id))


def search_moves(query: str, limit: int = 10) -> list[dict]:
    return _ranked_search("moves", query, limit)


def get_item(item_id: str) -> dict | None:
    return load_db()["items"].get(_normalize(item_id))


def search_items(query: str, limit: int = 10) -> list[dict]:
    return _ranked_search("items", query, limit)


def get_natures() -> dict:
    return load_db()["natures"]


def get_nature(nature_id: str) -> dict | None:
    return load_db()["natures"].get(_normalize(nature_id))
