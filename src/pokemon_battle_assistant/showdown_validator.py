"""Bridge to Pokemon Showdown's authoritative TeamValidator.

This module intentionally does not reimplement tier rules. It converts a PBA
trainer template to Showdown text elsewhere, then calls the local Pokemon
Showdown command-line validator. The Showdown server does not need to be
running for this check.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SHOWDOWN_PATH = PROJECT_ROOT.parent / "pokemon-showdown"


@dataclass
class ShowdownValidationResult:
    ok: bool
    format: str
    checked: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    showdown_path: str | None = None
    command: list[str] = field(default_factory=list)
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "format": self.format,
            "checked": self.checked,
            "errors": self.errors,
            "warnings": self.warnings,
            "showdown_path": self.showdown_path,
            "command": self.command,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


def find_showdown_path(explicit_path: str | Path | None = None) -> Path | None:
    """Find a local Pokemon Showdown checkout."""
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())
    if os.environ.get("PBA_SHOWDOWN_PATH"):
        candidates.append(Path(os.environ["PBA_SHOWDOWN_PATH"]).expanduser())
    candidates.append(DEFAULT_SHOWDOWN_PATH.expanduser())

    for path in candidates:
        if (path / "pokemon-showdown").exists() and (path / "dist" / "sim" / "team-validator.js").exists():
            return path
    return None


def validate_showdown_team(
    team_text: str,
    battle_format: str,
    *,
    showdown_path: str | Path | None = None,
    timeout: float = 20.0,
) -> ShowdownValidationResult:
    """Validate Showdown team text against a format.

    Returns checked=False when the local Showdown checkout is unavailable. A
    non-zero Showdown exit code with stderr is treated as team illegality; a
    missing executable / timeout is reported as a skipped authority check with a
    warning so the caller can still show local validation results.
    """
    root = find_showdown_path(showdown_path)
    if root is None:
        return ShowdownValidationResult(
            ok=True,
            checked=False,
            format=battle_format,
            warnings=[
                "未找到本地 Pokémon Showdown，已跳过权威规则校验。请设置 PBA_SHOWDOWN_PATH 或放在 ~/Bian-workspace/pokemon-showdown。"
            ],
        )

    command = ["node", "pokemon-showdown", "validate-team", battle_format, "--skip-build"]
    try:
        proc = subprocess.run(
            command,
            input=team_text,
            text=True,
            capture_output=True,
            cwd=root,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return ShowdownValidationResult(
            ok=True,
            checked=False,
            format=battle_format,
            showdown_path=str(root),
            command=command,
            warnings=["未找到 node 命令，已跳过 Pokémon Showdown 权威规则校验。"],
        )
    except subprocess.TimeoutExpired:
        return ShowdownValidationResult(
            ok=True,
            checked=False,
            format=battle_format,
            showdown_path=str(root),
            command=command,
            warnings=["Pokémon Showdown 校验超时，已跳过权威规则校验。"],
        )

    errors = [line.strip() for line in proc.stderr.splitlines() if line.strip()]
    return ShowdownValidationResult(
        ok=proc.returncode == 0,
        checked=True,
        format=battle_format,
        errors=errors if proc.returncode != 0 else [],
        showdown_path=str(root),
        command=command,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
