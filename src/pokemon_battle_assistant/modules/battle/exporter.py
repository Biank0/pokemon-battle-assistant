"""对战结果导出：record.json（含 agent_decisions）+ report.md + steps.jsonl。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ...environment import build_step_records, infer_battle_kind

OUTPUT_ROOT = Path("battle_outputs")


@dataclass(frozen=True)
class AgentBattleResult:
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
        }


def build_agent_record(
    *,
    battle: Any,
    agent_player: Any,
    opponent_player: Any,
    battle_format: str,
    player_source: str,
    opponent_source: str,
    agent_backend: str = "",
    agent_model: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """从结束的 battle + 两个 player 组装 record dict。"""
    from ...battle_recorder import battle_summary

    battle_tag = str(battle.battle_tag)
    record: dict[str, Any] = {
        "schema_version": "agent-battle.v1",
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "battle_format": battle_format,
        "battle_kind": infer_battle_kind(battle_format),
        "player_source": player_source,
        "opponent_source": opponent_source,
        "agent": {
            "backend": agent_backend,
            "model": agent_model,
        },
        "metadata": dict(metadata or {}),
        "pre_battle_config": {
            "battle_format": battle_format,
            "server": "local Pokémon Showdown / localhost:8000",
            "battle_kind": infer_battle_kind(battle_format),
            "control_modes": {"player_1": "agent", "player_2": "opponent"},
            "players": [
                f"RecordingAgentPlayer（LLM Agent 决策），队伍来源：{player_source}",
                f"对手 player，队伍来源：{opponent_source}",
            ],
            "team_source": f"{player_source} vs {opponent_source}",
        },
        "battle": battle_summary(battle),
        "player_1_observations": agent_player.observations.get(battle_tag, []),
        "player_2_observations": opponent_player.observations.get(battle_tag, []),
        "team_preview": {
            "player_1": agent_player.team_selections.get(battle_tag),
            "player_2": opponent_player.team_selections.get(battle_tag),
        },
        "agent_decisions": agent_player.agent_decisions.get(battle_tag, []),
    }
    record["steps"] = build_step_records(record)
    return record


def export_agent_battle(
    record: dict[str, Any],
    *,
    battle: Any,
    output_root: Path = OUTPUT_ROOT,
) -> AgentBattleResult:
    """写 replay.html / record.json / report.md / steps.jsonl，返回结果。"""
    from ...battle_recorder import build_markdown_report

    battle_tag = str(record["battle"]["battle_tag"])
    output_dir = Path(output_root) / battle_tag
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        replay_path = Path(battle.save_replay(output_dir / "replay.html"))
    except Exception:
        replay_path = output_dir / "replay.html"
        replay_path.write_text("<!-- replay unavailable -->", encoding="utf-8")
    record_path = output_dir / "record.json"
    report_path = output_dir / "report.md"
    steps_path = output_dir / "steps.jsonl"

    record["files"] = {
        "replay_html": str(replay_path),
        "record_json": str(record_path),
        "report_md": str(report_path),
        "steps_jsonl": str(steps_path),
    }
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    steps_path.write_text(
        "".join(json.dumps(step, ensure_ascii=False) + "\n" for step in record["steps"]),
        encoding="utf-8",
    )
    report_path.write_text(build_markdown_report(record), encoding="utf-8")
    return AgentBattleResult(
        battle_tag=battle_tag,
        output_dir=output_dir,
        replay_path=replay_path,
        record_path=record_path,
        report_path=report_path,
        steps_path=steps_path,
        record=record,
    )
