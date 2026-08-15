"""逐回合决策评估：LLM 评审 + 规则兜底，输出 好/一般/失误 评级。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...agent.agent import parse_json_payload
from .replayer import species_of

VALID_RATINGS = ("good", "average", "mistake")
RATING_ZH = {"good": "好", "average": "一般", "mistake": "失误"}

REVIEW_SYSTEM_PROMPT = "你是宝可梦对战教练，负责评估 AI 选手每回合的决策质量。只输出 JSON，不要输出其他内容。"


@dataclass
class TurnReview:
    """单个回合决策的评估结果。"""

    turn: int
    order_message: str
    rating: str  # good / average / mistake
    comment: str
    alternative: str = ""
    source: str = "rule"  # rule | llm

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn": self.turn,
            "order_message": self.order_message,
            "rating": self.rating,
            "rating_zh": RATING_ZH.get(self.rating, self.rating),
            "comment": self.comment,
            "alternative": self.alternative,
            "source": self.source,
        }


def first_active(slot: Any) -> dict[str, Any] | None:
    """从 active_pokemon 槽位取第一只在场宝可梦（单打/双打通用）。"""
    if isinstance(slot, list):
        first = slot[0] if slot else None
    else:
        first = slot
    return first if isinstance(first, dict) else None


def hp_fraction(mon: dict[str, Any] | None) -> float | None:
    if not mon:
        return None
    value = mon.get("hp_fraction")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def count_switches(observation: dict[str, Any]) -> int:
    switches = observation.get("available_switches")
    if not isinstance(switches, list):
        return 0
    if switches and isinstance(switches[0], list):
        return len(switches[0])
    return len(switches)


class DecisionReviewer:
    """逐回合决策评估器：优先 LLM，失败或无 LLM 时回退规则。"""

    def __init__(self, llm: Any | None = None, llm_turn_limit: int = 8) -> None:
        self.llm = llm
        self.llm_turn_limit = max(0, llm_turn_limit)

    def review(self, record: dict[str, Any]) -> list[TurnReview]:
        observations: dict[int, dict[str, Any]] = {}
        for obs in record.get("player_1_observations") or []:
            observations[int(obs.get("turn") or 0)] = obs

        reviews: list[TurnReview] = []
        budget = self.llm_turn_limit
        for decision in record.get("agent_decisions") or []:
            if decision.get("decision_type") != "turn":
                continue
            observation = observations.get(int(decision.get("turn") or 0), {})
            review: TurnReview | None = None
            if self.llm is not None and budget > 0:
                budget -= 1
                review = self._review_with_llm(observation, decision)
            if review is None:
                review = self._review_with_rules(observation, decision)
            reviews.append(review)
        return reviews

    # -- LLM 评审 -------------------------------------------------------
    def _review_with_llm(
        self, observation: dict[str, Any], decision: dict[str, Any]
    ) -> TurnReview | None:
        llm = self.llm
        if llm is None:
            return None
        try:
            response = llm.chat(
                [
                    {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                    {"role": "user", "content": self._build_prompt(observation, decision)},
                ]
            )
        except Exception:
            return None
        payload = parse_json_payload(getattr(response, "content", "") or "")
        if not payload:
            return None
        rating = str(payload.get("rating") or "").strip().lower()
        if rating not in VALID_RATINGS:
            return None
        return TurnReview(
            turn=int(decision.get("turn") or 0),
            order_message=str(decision.get("order_message") or ""),
            rating=rating,
            comment=str(payload.get("comment") or ""),
            alternative=str(payload.get("alternative") or ""),
            source="llm",
        )

    def _build_prompt(self, observation: dict[str, Any], decision: dict[str, Any]) -> str:
        active = first_active(observation.get("active_pokemon"))
        opponent = first_active(observation.get("opponent_active_pokemon"))
        hp = hp_fraction(active)
        hp_text = "未知" if hp is None else f"{hp:.0%}"
        lines = [
            f"回合：{decision.get('turn')}",
            f"己方在场：{species_of(active)}（HP {hp_text}）",
            f"对手在场：{species_of(opponent)}",
            f"可选动作：{', '.join((observation.get('legal_order_messages') or [])[:12])}",
            f"实际选择：{decision.get('order_message')}",
            f"AI 推理：{str(decision.get('reasoning') or '')[:400]}",
            "",
            "请评估该决策并只输出 JSON：",
            '{"rating": "good|average|mistake", "comment": "一句话点评", "alternative": "更优选择，没有则留空"}',
        ]
        return "\n".join(lines)

    # -- 规则兜底 -------------------------------------------------------
    def _review_with_rules(
        self, observation: dict[str, Any], decision: dict[str, Any]
    ) -> TurnReview:
        turn = int(decision.get("turn") or 0)
        message = str(decision.get("order_message") or "").strip()
        lowered = message.lower()
        if decision.get("fallback"):
            return TurnReview(
                turn,
                message,
                "average",
                "回退决策：LLM 输出未能解析，执行了保底策略。",
                "优化 prompt 或输出格式约束，减少回退。",
            )
        active = first_active(observation.get("active_pokemon"))
        hp = hp_fraction(active)
        if lowered.startswith("switch"):
            if hp is not None and hp > 0.6:
                return TurnReview(
                    turn,
                    message,
                    "average",
                    "主力血量健康时换人，可能让出进攻节奏。",
                    "确认对位劣势再换，否则继续压制。",
                )
            return TurnReview(turn, message, "good", "及时换人规避劣势对位或保存残血主力。")
        if "terastallize" in lowered:
            return TurnReview(turn, message, "good", "关键回合主动太晶化，争取属性优势。")
        if hp is not None and hp <= 0.2 and count_switches(observation) > 0:
            return TurnReview(
                turn,
                message,
                "mistake",
                f"当前主力仅剩 {hp:.0%} 血仍选择行动，容易被先手击倒。",
                "换上后备保持人数优势。",
            )
        return TurnReview(turn, message, "good", "按当前局面执行行动，节奏正常。")
