"""Thin wrapper kept for backwards compatibility.

The trainer template logic now lives in the package module
`pokemon_battle_assistant.trainer_cli`. This script lets the documented
`PYTHONPATH=src python scripts/trainer_cli.py ...` invocation keep working.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokemon_battle_assistant.trainer_cli import main

if __name__ == "__main__":
    main()
