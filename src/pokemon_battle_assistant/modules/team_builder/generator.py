"""TeamGenerator：LLM 调用与队伍 JSON 解析。"""

from __future__ import annotations

import json
import re

from pokemon_battle_assistant.agent.llm_client import LLMClient, LLMResponse

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def parse_team_json(content: str) -> tuple[dict | None, str]:
    """从 LLM 回复提取 (队伍模板 dict, 理由文本)；失败返回 (None, content)。"""
    if not content:
        return None, ""
    match = _JSON_BLOCK_RE.search(content)
    raw = match.group(1) if match else None
    if raw is None:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end > start:
            raw = content[start : end + 1]
    if raw is None:
        return None, content
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, content
    if not isinstance(data, dict) or not isinstance(data.get("team"), list):
        return None, content
    reasoning = re.sub(r"```(?:json)?", "", content.replace(raw, "")).strip()
    return data, reasoning


class TeamGenerator:
    """封装一次 LLM 生成调用与解析。"""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def generate(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        return self.llm.chat_with_tools(messages, tools=tools)

    def parse(self, response: LLMResponse) -> tuple[dict | None, str]:
        return parse_team_json(response.content)
