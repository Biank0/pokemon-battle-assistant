"""TeamBuilderAgent：需求解析 → 工具检索 → 队伍生成 → 校验修正 → 保存。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pokemon_battle_assistant.agent.llm_client import LLMClient, LLMResponse
from pokemon_battle_assistant.tools import run_tool, team_builder_tool_specs
from pokemon_battle_assistant.tools.team_validator import validate_team

from .generator import TeamGenerator, parse_team_json
from .parser import RequirementParser
from .prompts import (
    FIX_TEAM_TEMPLATE,
    ITERATE_TEAM_TEMPLATE,
    TEAM_BUILDER_SYSTEM_PROMPT,
    USER_REQUIREMENT_TEMPLATE,
)
from .result import TeamBuildResult, team_hash

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TRAINERS_DIR = PROJECT_ROOT / "data" / "trainers"

_TOOL_RESULT_LIMIT = 6000


def _trim(text: str, limit: int = _TOOL_RESULT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...（结果过长，已截断 {len(text) - limit} 字符）"


class TeamBuilderAgent:
    """建队 Agent：generate_team / iterate_team / save_team。"""

    def __init__(
        self,
        llm: LLMClient | None = None,
        *,
        max_tool_rounds: int = 8,
        max_fix_attempts: int = 3,
        run_showdown: bool = True,
    ) -> None:
        self.llm = llm or LLMClient()
        self.parser = RequirementParser()
        self.generator = TeamGenerator(self.llm)
        self.max_tool_rounds = max_tool_rounds
        self.max_fix_attempts = max_fix_attempts
        self.run_showdown = run_showdown

    # ---- 对外接口 ----

    def generate_team(self, requirement: str, format: str = "gen9bssregi") -> TeamBuildResult:
        """AI 建队：需求解析 + 知识检索 + 队伍生成 + 合法性校验。"""
        intent = self.parser.parse(requirement)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": TEAM_BUILDER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_REQUIREMENT_TEMPLATE.format(
                    intent=intent.to_prompt_text(), format=format
                ),
            },
        ]
        return self._run(messages, format=format)

    def iterate_team(
        self,
        team: dict,
        analysis_report: dict,
        *,
        format: str = "gen9bssregi",
    ) -> TeamBuildResult:
        """基于分析报告迭代优化队伍。"""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": TEAM_BUILDER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": ITERATE_TEAM_TEMPLATE.format(
                    team=json.dumps(team, ensure_ascii=False, indent=2),
                    report=json.dumps(analysis_report, ensure_ascii=False, indent=2),
                ),
            },
        ]
        result = self._run(messages, format=format)
        result.iteration = 1
        result.parent_team_hash = team_hash(team)
        return result

    def save_team(
        self,
        result: TeamBuildResult,
        *,
        name: str | None = None,
        root: Path | None = None,
    ) -> Path:
        """把建队结果保存到 data/trainers/（或指定目录）。"""
        directory = root or TRAINERS_DIR
        directory.mkdir(parents=True, exist_ok=True)
        slug = _slugify(
            name or str(result.team.get("name") or "")
            or f"ai_team_{datetime.now():%Y%m%d_%H%M%S}"
        )
        path = directory / f"{slug}.json"
        payload = dict(result.team)
        payload["team"] = result.team.get("team", [])
        payload.setdefault("format", "gen9bssregi")
        payload.setdefault("name", slug)
        payload["meta"] = {
            "generated_by": "team_builder_agent",
            "valid": result.valid,
            "iteration": result.iteration,
            "reasoning": result.reasoning,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return path

    # ---- 内部流程 ----

    def _run(self, messages: list[dict[str, Any]], *, format: str) -> TeamBuildResult:
        messages = list(messages)
        tool_log: list[dict[str, Any]] = []
        specs = team_builder_tool_specs()
        team: dict | None = None
        reasoning = ""

        for _ in range(self.max_tool_rounds):
            response = self.llm.chat_with_tools(messages, tools=specs)
            if response.tool_calls:
                self._append_assistant(messages, response)
                for call in response.tool_calls:
                    self._execute_tool_call(messages, tool_log, call)
                continue
            messages.append({"role": "assistant", "content": response.content})
            team, reasoning = parse_team_json(response.content)
            break

        attempts = 0
        validation_errors: list[str] = []
        while team is not None and attempts <= self.max_fix_attempts:
            outcome = validate_team(team, format, run_showdown=self.run_showdown)
            validation_errors = list(outcome["errors"])
            if outcome["valid"]:
                return TeamBuildResult(
                    team=team,
                    valid=True,
                    validation_errors=[],
                    reasoning=reasoning,
                    tool_calls_log=tool_log,
                )
            if attempts >= self.max_fix_attempts:
                break
            attempts += 1
            messages.append(
                {
                    "role": "user",
                    "content": FIX_TEAM_TEMPLATE.format(
                        errors="\n".join(f"- {e}" for e in validation_errors)
                    ),
                }
            )
            team, reasoning = self._fix_round(messages, specs, tool_log)

        if team is None:
            return TeamBuildResult(
                team={"team": []},
                valid=False,
                validation_errors=validation_errors or ["LLM 未输出可解析的队伍 JSON"],
                reasoning=reasoning,
                tool_calls_log=tool_log,
            )
        return TeamBuildResult(
            team=team,
            valid=False,
            validation_errors=validation_errors,
            reasoning=reasoning,
            tool_calls_log=tool_log,
        )

    def _fix_round(
        self,
        messages: list[dict[str, Any]],
        specs: list[dict],
        tool_log: list[dict[str, Any]],
    ) -> tuple[dict | None, str]:
        for _ in range(self.max_tool_rounds):
            response = self.llm.chat_with_tools(messages, tools=specs)
            if response.tool_calls:
                self._append_assistant(messages, response)
                for call in response.tool_calls:
                    self._execute_tool_call(messages, tool_log, call)
                continue
            messages.append({"role": "assistant", "content": response.content})
            return parse_team_json(response.content)
        return None, ""

    def _execute_tool_call(
        self,
        messages: list[dict[str, Any]],
        tool_log: list[dict[str, Any]],
        call: Any,
    ) -> None:
        arguments = call.parsed_arguments()
        output = run_tool(call.name, arguments)
        tool_log.append(
            {
                "tool": call.name,
                "arguments": arguments,
                "ok": bool(output.get("ok", True)),
                "result": _trim(json.dumps(output, ensure_ascii=False, default=str), 2000),
            }
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": _trim(json.dumps(output, ensure_ascii=False, default=str)),
            }
        )

    @staticmethod
    def _append_assistant(messages: list[dict[str, Any]], response: LLMResponse) -> None:
        messages.append(
            {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": c.arguments},
                    }
                    for c in response.tool_calls
                ],
            }
        )


def _slugify(text: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z_\-]+", "_", text.strip()).strip("_").lower()
    return slug or f"ai_team_{datetime.now():%Y%m%d_%H%M%S}"
