"""Offline Showdown data lookup for trainer template creation."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "showdown_db.json"


@lru_cache(maxsize=1)
def load_db() -> dict:
    with open(DB_PATH, encoding="utf-8") as f:
        return json.load(f)


def _normalize(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())


def get_pokemon(species_id: str) -> dict | None:
    return load_db()["pokedex"].get(_normalize(species_id))


def search_pokemon(query: str, limit: int = 10) -> list[dict]:
    q = _normalize(query)
    pokedex = load_db()["pokedex"]
    results = []
    for pid, entry in pokedex.items():
        if entry.get("num", 0) <= 0:
            continue
        if q in pid or q in _normalize(entry["name"]):
            results.append({"id": pid, **entry})
            if len(results) >= limit:
                break
    return results


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
    q = _normalize(query)
    moves = load_db()["moves"]
    results = []
    for mid, entry in moves.items():
        if q in mid or q in _normalize(entry["name"]):
            results.append({"id": mid, **entry})
            if len(results) >= limit:
                break
    return results


def get_item(item_id: str) -> dict | None:
    return load_db()["items"].get(_normalize(item_id))


def search_items(query: str, limit: int = 10) -> list[dict]:
    q = _normalize(query)
    items = load_db()["items"]
    results = []
    for iid, entry in items.items():
        if q in iid or q in _normalize(entry["name"]):
            results.append({"id": iid, **entry})
            if len(results) >= limit:
                break
    return results


def get_natures() -> dict:
    return load_db()["natures"]


def get_nature(nature_id: str) -> dict | None:
    return load_db()["natures"].get(_normalize(nature_id))
