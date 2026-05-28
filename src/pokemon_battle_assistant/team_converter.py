"""Convert trainer template JSON to Showdown team text format."""

from __future__ import annotations

STAT_LABELS = {
    "hp": "HP",
    "atk": "Atk",
    "def": "Def",
    "spa": "SpA",
    "spd": "SpD",
    "spe": "Spe",
}

STAT_ORDER = ["hp", "atk", "def", "spa", "spd", "spe"]


def pokemon_to_showdown_text(mon: dict) -> str:
    lines: list[str] = []

    species = mon["species"]
    nickname = mon.get("nickname", "")
    item = mon.get("item", "")

    header = nickname if nickname else species
    if nickname and nickname != species:
        header = f"{nickname} ({species})"
    if item:
        header += f" @ {item}"
    lines.append(header)

    if mon.get("ability"):
        lines.append(f"Ability: {mon['ability']}")

    if mon.get("tera_type"):
        lines.append(f"Tera Type: {mon['tera_type']}")

    level = mon.get("level", 100)
    if level != 100:
        lines.append(f"Level: {level}")

    evs = mon.get("evs", {})
    ev_parts = [f"{v} {STAT_LABELS[k]}" for k in STAT_ORDER if (v := evs.get(k, 0)) != 0]
    if ev_parts:
        lines.append(f"EVs: {' / '.join(ev_parts)}")

    nature = mon.get("nature", "")
    if nature:
        lines.append(f"{nature} Nature")

    ivs = mon.get("ivs", {})
    iv_parts = [f"{v} {STAT_LABELS[k]}" for k in STAT_ORDER if (v := ivs.get(k, 31)) != 31]
    if iv_parts:
        lines.append(f"IVs: {' / '.join(iv_parts)}")

    for move in mon.get("moves", []):
        lines.append(f"- {move}")

    return "\n".join(lines)


def template_to_showdown_text(template: dict) -> str:
    team = template.get("team", [])
    blocks = [pokemon_to_showdown_text(mon) for mon in team]
    return "\n\n".join(blocks)
