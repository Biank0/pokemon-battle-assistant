"""BattleAgent：对战 Agent 主类，协调 LLM + Tools + Memory。

流程（每回合）：
1. Planner 生成回合策略文本
2. LLM + battle tools 推理（可多轮工具调用）
3. Judge 从 LLM 输出提取合法动作（匹配 observation.legal_orders）
4. 匹配失败时回退到第一个合法招式动作，并标记 fallback
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from ..perception.observation import BattleObservation
from ..tools.battle_registry import ToolContext, battle_tool_specs, run_battle_tool
from .decision_logger import DecisionLogger
from .llm_client import LLMClient
from .planner import plan_team_preview, plan_turn
from .prompts import (
    BATTLE_SYSTEM_PROMPT,
    TEAM_PREVIEW_SYSTEM_PROMPT,
    render_team_preview_message,
    render_turn_user_message,
)


@dataclass(frozen=True)
class TeamPreviewDecision:
    slots: list[int]
    order_message: str
    reasoning: str
    tool_calls_log: list[dict[str, Any]] = field(default_factory=list)
    fallback: bool = False


@dataclass(frozen=True)
class TurnDecision:
    order_message: str
    reasoning: str
    tool_calls_log: list[dict[str, Any]] = field(default_factory=list)
    fallback: bool = False


def parse_json_payload(text: str) -> dict[str, Any] | None:
    """从 LLM 输出中提取 JSON 对象（容忍 ```json 围栏与前后噪声）。"""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def _normalize_order_text(text: str) -> str:
    value = text.strip().lower()
    if value.startswith("/choose "):
        value = value[len("/choose ") :]
    elif value.startswith("choose "):
        value = value[len("choose ") :]
    return value.strip()


def extract_legal_order(action_text: str, legal_orders: list[str]) -> str | None:
    """Judge：把 LLM 输出的 action 匹配到合法 order（大小写/前缀容忍）。"""
    if not action_text or not legal_orders:
        return None
    normalized = _normalize_order_text(action_text)
    table: dict[str, str] = {}
    for order in legal_orders:
        table[_normalize_order_text(order)] = order
        table[_normalize_order_text(order).replace(" ", "")] = order
    if normalized in table:
        return table[normalized]
    if normalized.replace(" ", "") in table:
        return table[normalized.replace(" ", "")]

    # 子串匹配：action 的核心 token（move xxx / switch yyy）出现在某个合法 order 中
    match = re.match(r"(move|switch)\s+(\S+)", normalized)
    if match:
        token = f"{match.group(1)} {match.group(2)}"
        for key, order in table.items():
            if token in key and len(token) >= len("move x"):
                return order
    # 太晶化等附加修饰：去掉后缀再匹配
    stripped = re.sub(r"\s+(terastallize|dynamax|mega|zmove)(\s+\d+)?$", "", normalized)
    if stripped != normalized and stripped in table:
        return table[stripped]
    return None


class BattleAgent:
    """对战决策 Agent。"""

    def __init__(
        self,
        llm: LLMClient,
        *,
        max_tool_rounds: int = 3,
        team_size: int = 3,
        logger: DecisionLogger | None = None,
    ) -> None:
        self.llm = llm
        self.max_tool_rounds = max_tool_rounds
        self.team_size = team_size
        self.logger = logger or DecisionLogger()

    # ------------------------------------------------------------------
    def decide_team_preview(
        self, observation: BattleObservation, memory: Any = None
    ) -> TeamPreviewDecision:
        started = time.time()
        plan = plan_team_preview(observation, memory, team_size=self.team_size)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": TEAM_PREVIEW_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": render_team_preview_message(observation, plan, self.team_size),
            },
        ]
        try:
            content, tool_log = self._run_llm_loop(messages, observation, memory)
        except Exception as exc:  # LLM 不可用（缺 key/网络）时降级为 fallback 决策
            content, tool_log = "", [{"error": f"LLM call failed: {exc}"}]

        slots: list[int] | None = None
        reasoning = ""
        payload = parse_json_payload(content)
        if payload:
            reasoning = str(payload.get("reasoning") or "")
            raw_slots = payload.get("slots")
            if isinstance(raw_slots, list):
                slots = self._sanitize_slots(raw_slots)
        fallback = slots is None
        if slots is None:
            slots = list(range(1, self.team_size + 1))
            reasoning = reasoning or "LLM 输出无法解析，回退为默认选出前几只。"
        order_message = "/team " + "".join(str(s) for s in slots)
        self.logger.log(
            turn=0,
            decision_type="team_preview",
            order_message=order_message,
            reasoning=reasoning,
            tool_calls=tool_log,
            fallback=fallback,
            model=str(getattr(self.llm, "model", "") or ""),
            backend=self.llm.backend,
            started_at=started,
        )
        return TeamPreviewDecision(
            slots=slots,
            order_message=order_message,
            reasoning=reasoning,
            tool_calls_log=tool_log,
            fallback=fallback,
        )

    # ------------------------------------------------------------------
    def decide_turn(self, observation: BattleObservation, memory: Any = None) -> TurnDecision:
        started = time.time()
        plan = plan_turn(observation, memory)
        opponent_summary = None
        if memory is not None:
            try:
                opponent_summary = memory.get_opponent_model(observation.battle_tag).summary(observation)
            except Exception:
                opponent_summary = None
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": BATTLE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": render_turn_user_message(observation, plan, opponent_summary),
            },
        ]
        try:
            content, tool_log = self._run_llm_loop(messages, observation, memory)
        except Exception as exc:  # LLM 不可用（缺 key/网络）时降级为 fallback 决策
            content, tool_log = "", [{"error": f"LLM call failed: {exc}"}]

        order: str | None = None
        reasoning = ""
        payload = parse_json_payload(content)
        if payload:
            action = str(payload.get("action") or "")
            reasoning = str(payload.get("reasoning") or "")
            order = extract_legal_order(action, [o.message for o in observation.legal_orders])
            if order is None and action:
                # 兜底：action 直接等于某个合法 order（已含 /choose 前缀）
                for legal in observation.legal_orders:
                    if action.strip().lower() == legal.message.strip().lower():
                        order = legal.message
                        break

        fallback = order is None
        if order is None:
            order = self._fallback_order(observation)
            reasoning = reasoning or "LLM 输出无法匹配合法动作，回退为默认招式。"
        self.logger.log(
            turn=observation.turn,
            decision_type="turn",
            order_message=order,
            reasoning=reasoning,
            tool_calls=tool_log,
            fallback=fallback,
            model=str(getattr(self.llm, "model", "") or ""),
            backend=self.llm.backend,
            started_at=started,
        )
        return TurnDecision(
            order_message=order,
            reasoning=reasoning,
            tool_calls_log=tool_log,
            fallback=fallback,
        )

    # ------------------------------------------------------------------
    def _run_llm_loop(
        self, messages: list[dict[str, Any]], observation: BattleObservation, memory: Any
    ) -> tuple[str, list[dict[str, Any]]]:
        """LLM 推理循环：支持多轮工具调用，返回最终文本与工具日志。"""
        tool_log: list[dict[str, Any]] = []
        specs = battle_tool_specs()
        context = ToolContext(observation=observation, memory=memory)
        for _ in range(self.max_tool_rounds):
            response = self.llm.chat_with_tools(messages, tools=specs)
            if not response.tool_calls:
                return response.content, tool_log
            messages.append(
                {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [c.to_dict() for c in response.tool_calls],
                }
            )
            for call in response.tool_calls:
                result = run_battle_tool(call.name, call.parsed_arguments(), context)
                tool_log.append(
                    {"name": call.name, "arguments": call.parsed_arguments(), "result": result}
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False)[:4000],
                    }
                )
        # 工具轮次用尽：再要一次无工具回答
        final = self.llm.chat(messages)
        return final.content, tool_log

    # ------------------------------------------------------------------
    def _sanitize_slots(self, raw: list[Any]) -> list[int] | None:
        slots: list[int] = []
        for value in raw:
            try:
                num = int(value)
            except (TypeError, ValueError):
                continue
            if 1 <= num <= 6 and num not in slots:
                slots.append(num)
        if len(slots) == self.team_size:
            return slots
        # 数量不足但至少有一只合法：补足剩余编号
        if slots:
            for num in range(1, 7):
                if len(slots) >= self.team_size:
                    break
                if num not in slots:
                    slots.append(num)
            return slots if len(slots) == self.team_size else None
        return None

    def _fallback_order(self, observation: BattleObservation) -> str:
        for legal in observation.legal_orders:
            if "move" in legal.message:
                return legal.message
        if observation.legal_orders:
            return observation.legal_orders[0].message
        return "/choose move 1"
