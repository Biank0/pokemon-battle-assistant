"""Read local Pokemon Showdown format metadata useful for PBA."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .showdown_validator import find_showdown_path


def is_doubles_format(format_id: str | None) -> bool:
    """Whether a format id denotes a doubles/VGC game type."""
    text = (format_id or "").lower()
    return "double" in text or "vgc" in text


@dataclass(frozen=True)
class FormatInfo:
    id: str
    exists: bool
    name: str
    game_type: str
    picked_team_size: int | None = None
    min_team_size: int | None = None
    max_team_size: int | None = None
    error: str | None = None

    @property
    def needs_team_selection(self) -> bool:
        return bool(self.picked_team_size and self.max_team_size and self.picked_team_size < self.max_team_size)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "exists": self.exists,
            "name": self.name,
            "game_type": self.game_type,
            "picked_team_size": self.picked_team_size,
            "min_team_size": self.min_team_size,
            "max_team_size": self.max_team_size,
            "needs_team_selection": self.needs_team_selection,
            "error": self.error,
        }


def _load_fallback_formats() -> dict[str, dict[str, Any]]:
    """从 data/rules/formats.json 读取结构化规则，作为本地 Showdown 不可用时的兜底。"""
    from .data_paths import FORMATS_JSON_PATH

    if not FORMATS_JSON_PATH.is_file():
        return {}
    try:
        with open(FORMATS_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        str(fmt["id"]).lower(): fmt
        for fmt in data.get("formats", [])
        if isinstance(fmt, dict) and fmt.get("id")
    }


_FALLBACK_FORMATS = _load_fallback_formats()


def get_format_info(format_id: str, *, showdown_path: str | Path | None = None, timeout: float = 10.0) -> FormatInfo:
    """Return Showdown format metadata.

    The authoritative source is local Pokemon Showdown's Dex rule table. If the
    checkout is unavailable or Node fails, return a conservative fallback for the
    known formats PBA documents.
    """
    root = find_showdown_path(showdown_path)
    fmt_entry = _FALLBACK_FORMATS.get(format_id.lower(), {})
    fallback_size = fmt_entry.get("picked_team_size")
    fallback = FormatInfo(
        id=format_id,
        exists=bool(fallback_size),
        name=format_id,
        game_type="doubles" if is_doubles_format(format_id) else "singles",
        picked_team_size=fallback_size,
        min_team_size=fallback_size,
        max_team_size=6 if fallback_size else None,
        error="未能读取本地 Pokemon Showdown format 元数据，使用 PBA 内置兜底。" if fallback_size else None,
    )
    if root is None:
        return fallback

    script = r"""
const {Dex} = require('./dist/sim/dex');
const id = process.argv[1];
try {
  const format = Dex.formats.get(id);
  const ruleTable = Dex.formats.getRuleTable(format);
  console.log(JSON.stringify({
    id,
    exists: !!format.exists,
    name: format.name || id,
    game_type: format.gameType || 'singles',
    picked_team_size: ruleTable.pickedTeamSize || null,
    min_team_size: ruleTable.minTeamSize || null,
    max_team_size: ruleTable.maxTeamSize || null
  }));
} catch (err) {
  console.log(JSON.stringify({id, exists: false, name: id, game_type: 'singles', error: String(err)}));
}
"""
    try:
        proc = subprocess.run(
            ["node", "-e", script, format_id],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode != 0:
            return replace(fallback, error=proc.stderr.strip() or fallback.error)
        data = json.loads(proc.stdout)
        return FormatInfo(
            id=data.get("id", format_id),
            exists=bool(data.get("exists")),
            name=data.get("name") or format_id,
            game_type=data.get("game_type") or "singles",
            picked_team_size=data.get("picked_team_size"),
            min_team_size=data.get("min_team_size"),
            max_team_size=data.get("max_team_size"),
            error=data.get("error"),
        )
    except Exception as exc:
        return replace(fallback, error=str(exc) or fallback.error)
