"""Command-line entry point for the Pokemon Battle Assistant MVP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evaluator import evaluate_battle
from .explanation import format_analysis
from .models import BattleState


def load_battle_state(path: str | Path) -> BattleState:
    """Load a BattleState from a JSON file."""

    json_path = Path(path)
    with json_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return BattleState.from_dict(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a simplified Pokemon battle state.")
    parser.add_argument("input", help="Path to a battle-state JSON file.")
    parser.add_argument("--top", type=int, default=3, help="Number of candidate actions to print.")
    args = parser.parse_args()

    state = load_battle_state(args.input)
    evaluations = evaluate_battle(state)
    print(format_analysis(state, evaluations, top_n=args.top))


if __name__ == "__main__":
    main()
