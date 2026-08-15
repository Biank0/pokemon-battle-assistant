"""meta_analyzer 工具：查询当前环境热门宝可梦和常见配置。

离线实现：基于本地 showdown_db 的种族值统计给出环境参考，并列出
data/trainers 下的示例队伍核心。接入真实使用率数据后可替换数据源。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pokemon_battle_assistant.showdown_db import load_db

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TRAINERS_DIR = PROJECT_ROOT / "data" / "trainers"
STAT_KEYS = ("hp", "atk", "def", "spa", "spd", "spe")


def _top_pokemon(limit: int = 20) -> list[dict[str, Any]]:
    pokedex = load_db().get("pokedex", {})
    scored: list[dict[str, Any]] = []
    for pid, entry in pokedex.items():
        if not isinstance(entry, dict):
            continue
        num = entry.get("num")
        if not isinstance(num, int) or num <= 0:
            continue
        base = entry.get("baseStats") or {}
        stats = {key: int(base.get(key, 0)) for key in STAT_KEYS}
        abilities = [a for a in (entry.get("abilities") or {}).values() if isinstance(a, str)]
        scored.append(
            {
                "species": entry.get("name", pid),
                "types": [str(t) for t in entry.get("types", [])],
                "base_stats": stats,
                "bst": sum(stats.values()),
                "abilities": abilities,
            }
        )
    scored.sort(key=lambda item: (-item["bst"], str(item["species"])))
    return scored[:limit]


def _sample_teams() -> list[dict[str, Any]]:
    if not TRAINERS_DIR.exists():
        return []
    samples: list[dict[str, Any]] = []
    for path in sorted(TRAINERS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        team = data.get("team")
        if not isinstance(team, list) or not team:
            continue
        samples.append(
            {
                "name": data.get("name", path.stem),
                "format": data.get("format", ""),
                "species": [str(m.get("species", "")) for m in team if isinstance(m, dict)],
            }
        )
    return samples


def analyze_meta(format: str) -> dict[str, Any]:
    """返回当前环境参考信息（热门宝可梦 + 示例队伍）。"""
    return {
        "ok": True,
        "format": format,
        "note": "离线统计：基于本地 Showdown 数据库种族值排序，非真实使用率。",
        "top_pokemon": _top_pokemon(),
        "sample_teams": _sample_teams(),
    }
