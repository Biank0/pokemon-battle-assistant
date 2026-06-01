"""Reusable battle environment / runner layer.

First-stage scope: provide a stable runner around complete poke-env battles
for CLI users, batch runs, logging, and future RL integration. This module does
not implement an assistant, bot policy, RL algorithm, or interactive
reset()/step() environment yet.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from .action_space import chosen_action_from_message, legal_actions_from_snapshot
from .team_selection import TeamSelectionConfig

OUTPUT_ROOT = Path("battle_outputs")
ControlMode = Literal["random", "manual"]


@dataclass(frozen=True)
class BattleRunConfig:
    """Configuration for one local battle run."""

    battle_format: str
    player_1_team: str | None = None
    player_2_team: str | None = None
    player_1_source: str = "Showdown random battle generator"
    player_2_source: str = "Showdown random battle generator"
    player_1_label: str = "player_1"
    player_2_label: str = "player_2"
    player_1_control: ControlMode = "random"
    player_2_control: ControlMode = "random"
    player_1_selection: TeamSelectionConfig = field(default_factory=TeamSelectionConfig)
    player_2_selection: TeamSelectionConfig = field(default_factory=TeamSelectionConfig)
    expected_selection_size: int | None = None
    player_1_kind: str | None = None
    player_2_kind: str | None = None
    server: str = "local Pokémon Showdown / localhost:8000"
    output_root: Path = OUTPUT_ROOT
    n_battles: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["output_root"] = str(self.output_root)
        return data


@dataclass(frozen=True)
class BattleRunResult:
    """Paths and structured data produced by one battle run."""

    battle_tag: str
    output_dir: Path
    replay_path: Path
    record_path: Path
    report_path: Path
    steps_path: Path
    record: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "battle_tag": self.battle_tag,
            "output_dir": str(self.output_dir),
            "replay_path": str(self.replay_path),
            "record_path": str(self.record_path),
            "report_path": str(self.report_path),
            "steps_path": str(self.steps_path),
            "record": self.record,
        }


def build_step_records(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize player observations into future RL/user step records."""

    steps: list[dict[str, Any]] = []
    observation_keys = [
        ("player_1", "player_1_observations"),
        ("player_2", "player_2_observations"),
    ]
    for player, key in observation_keys:
        for idx, obs in enumerate(record.get(key) or []):
            chosen_message = obs.get("chosen_order_message")
            steps.append(
                {
                    "step_index": len(steps),
                    "player": player,
                    "player_local_index": idx,
                    "turn": obs.get("turn"),
                    "observation": obs,
                    "legal_actions": legal_actions_from_snapshot(obs),
                    "chosen_action": chosen_action_from_message(chosen_message),
                    # Conservative first-stage semantics: BattleRunner builds
                    # records after a full battle has finished, but it is not yet
                    # an interactive reset()/step() RL environment. Avoid marking
                    # every exported decision point as an RL terminal step.
                    "reward": None,
                    "done": None,
                    "info": {
                        "battle_tag": obs.get("battle_tag"),
                        "format": obs.get("format"),
                        "chosen_order_message": chosen_message,
                        "episode_finished": bool(record.get("battle", {}).get("finished", False)),
                    },
                }
            )
    ordered = sorted(steps, key=lambda item: (item.get("turn") or 0, item["player"], item["player_local_index"]))
    for step_index, step in enumerate(ordered):
        step["step_index"] = step_index
    return ordered


def control_kind(control: ControlMode) -> str:
    if control == "manual":
        return "RecordingManualPlayer（用户手动选择合法动作）"
    return "RecordingRandomPlayer（环境基线：随机行动）"


def infer_battle_kind(battle_format: str) -> str:
    text = battle_format.lower()
    return "doubles" if "double" in text or "vgc" in text else "singles"


class BattleRunner:
    """Run poke-env battles and export environment-oriented records."""

    async def run(self, config: BattleRunConfig) -> BattleRunResult:
        if config.n_battles != 1:
            raise ValueError("BattleRunner currently exports one battle per run; use a loop for batch runs.")

        # Import poke-env dependent recorder lazily so environment data helpers can
        # be imported in lightweight test/documentation contexts without requiring
        # a running poke-env installation.
        from .battle_recorder import (
            RecordingManualPlayer,
            RecordingRandomPlayer,
            battle_summary,
            build_markdown_report,
        )

        player_cls = {"random": RecordingRandomPlayer, "manual": RecordingManualPlayer}

        player_1 = player_cls[config.player_1_control](
            label=config.player_1_label,
            battle_format=config.battle_format,
            max_concurrent_battles=1,
            save_replays=False,
            team=config.player_1_team,
            selection_config=config.player_1_selection,
            expected_selection_size=config.expected_selection_size,
        )
        player_2 = player_cls[config.player_2_control](
            label=config.player_2_label,
            battle_format=config.battle_format,
            max_concurrent_battles=1,
            save_replays=False,
            team=config.player_2_team,
            selection_config=config.player_2_selection,
            expected_selection_size=config.expected_selection_size,
        )

        try:
            await player_1.battle_against(player_2, n_battles=config.n_battles)

            battle_tag = next(iter(player_1.battles))
            battle = player_1.battles[battle_tag]
            output_dir = config.output_root / battle_tag
            output_dir.mkdir(parents=True, exist_ok=True)

            replay_path = Path(battle.save_replay(output_dir / "replay.html"))
            record_path = output_dir / "record.json"
            report_path = output_dir / "report.md"
            steps_path = output_dir / "steps.jsonl"

            record = {
                "schema_version": "battle-environment.v1",
                "exported_at": datetime.now().isoformat(timespec="seconds"),
                "run_config": config.to_dict(),
                "pre_battle_config": {
                    "battle_format": config.battle_format,
                    "server": config.server,
                    "battle_kind": infer_battle_kind(config.battle_format),
                    "team_source_kind": "random" if not config.player_1_team and not config.player_2_team else "template",
                    "control_modes": {
                        "player_1": config.player_1_control,
                        "player_2": config.player_2_control,
                    },
                    "selection_modes": {
                        "player_1": config.player_1_selection.to_dict(),
                        "player_2": config.player_2_selection.to_dict(),
                    },
                    "expected_selection_size": config.expected_selection_size,
                    "players": [
                        f"{config.player_1_kind or control_kind(config.player_1_control)}，队伍来源：{config.player_1_source}",
                        f"{config.player_2_kind or control_kind(config.player_2_control)}，队伍来源：{config.player_2_source}",
                    ],
                    "team_source": f"{config.player_1_source} vs {config.player_2_source}",
                },
                "battle": battle_summary(battle),
                "player_1_observations": player_1.observations.get(battle_tag, []),
                "player_2_observations": player_2.observations.get(battle_tag, []),
                "team_preview": {
                    "player_1": player_1.team_selections.get(battle_tag),
                    "player_2": player_2.team_selections.get(battle_tag),
                },
                "files": {
                    "replay_html": str(replay_path),
                    "record_json": str(record_path),
                    "report_md": str(report_path),
                    "steps_jsonl": str(steps_path),
                },
            }
            record["steps"] = build_step_records(record)

            record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            steps_path.write_text(
                "".join(json.dumps(step, ensure_ascii=False) + "\n" for step in record["steps"]),
                encoding="utf-8",
            )
            report_path.write_text(build_markdown_report(record), encoding="utf-8")

            return BattleRunResult(
                battle_tag=battle_tag,
                output_dir=output_dir,
                replay_path=replay_path,
                record_path=record_path,
                report_path=report_path,
                steps_path=steps_path,
                record=record,
            )
        finally:
            await player_1.ps_client.stop_listening()
            await player_2.ps_client.stop_listening()
