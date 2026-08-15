"""策略优化建议：LLM 生成 + 规则兜底，产出可回传 Team Builder 的反馈。"""

from __future__ import annotations

from typing import Any

from ...agent.agent import parse_json_payload
from .replayer import species_of
from .reviewer import TurnReview, first_active

ADVICE_KEYS = (
    "team_selection_assessment",
    "lead_analysis",
    "key_turn_alternatives",
    "opponent_adjustments",
    "team_builder_feedback",
    "summary",
)

ADVICE_SYSTEM_PROMPT = "你是宝可梦战术分析师，基于对局复盘给出策略优化建议。只输出 JSON，不要输出其他内容。"

ADVICE_JSON_TEMPLATE = (
    "{\n"
    '  "team_selection_assessment": "对选出与阵容的评价",\n'
    '  "lead_analysis": "首发对位分析",\n'
    '  "key_turn_alternatives": ["回合 N：替代方案"],\n'
    '  "opponent_adjustments": ["针对该对手的调整"],\n'
    '  "team_builder_feedback": ["给建队模块的优化建议"],\n'
    '  "summary": "一句话总结"\n'
    "}"
)


class StrategyAdvisor:
    """策略优化建议生成器：LLM 缺失/失败时回退规则建议。"""

    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm

    def advise(
        self,
        record: dict[str, Any],
        reviews: list[TurnReview] | None = None,
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        reviews = reviews or []
        profile = profile or {}
        fallback = self._advise_with_rules(record, reviews, profile)
        if self.llm is None:
            return fallback
        payload = self._advise_with_llm(record, reviews, profile)
        if payload is None:
            return fallback
        merged = dict(fallback)
        for key in ADVICE_KEYS:
            value = payload.get(key)
            if value:
                merged[key] = value
        return merged

    # -- LLM 建议 -------------------------------------------------------
    def _advise_with_llm(
        self,
        record: dict[str, Any],
        reviews: list[TurnReview],
        profile: dict[str, Any],
    ) -> dict[str, Any] | None:
        llm = self.llm
        if llm is None:
            return None
        try:
            response = llm.chat(
                [
                    {"role": "system", "content": ADVICE_SYSTEM_PROMPT},
                    {"role": "user", "content": self._build_prompt(record, reviews, profile)},
                ]
            )
        except Exception:
            return None
        return parse_json_payload(getattr(response, "content", "") or "")

    def _build_prompt(
        self,
        record: dict[str, Any],
        reviews: list[TurnReview],
        profile: dict[str, Any],
    ) -> str:
        battle = record.get("battle") or {}
        mistakes = [review for review in reviews if review.rating == "mistake"]
        lines = [
            f"对战格式：{battle.get('format')}",
            f"回合数：{battle.get('turns')}  结果：{'胜' if battle.get('won') else '负'}",
            f"失误回合数：{len(mistakes)}",
            *[f"- 回合 {r.turn}：{r.comment}（建议：{r.alternative}）" for r in mistakes[:6]],
            f"对手画像：风格 {profile.get('style')}、换人率 {profile.get('switch_rate')}、"
            f"太晶 {'已用' if profile.get('tera_used') else '未用'}",
            "",
            "请输出 JSON（全部字段必填，中文）：",
            ADVICE_JSON_TEMPLATE,
        ]
        return "\n".join(lines)

    # -- 规则兜底 -------------------------------------------------------
    def _advise_with_rules(
        self,
        record: dict[str, Any],
        reviews: list[TurnReview],
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        battle = record.get("battle") or {}
        won = bool(battle.get("won"))
        result = "获胜" if won else "落败"
        mistakes = [review for review in reviews if review.rating == "mistake"]
        preview = record.get("team_preview") or {}
        own_preview = preview.get("player_1") if isinstance(preview, dict) else {}
        slots = (own_preview or {}).get("selected_slots") or []
        selection_text = f"槽位 {slots}" if slots else "未记录"
        style = str(profile.get("style") or "未知")

        feedback: list[str] = []
        if not won:
            feedback.append("补充能应对对手核心输出的防守型成员（考虑抗性与回复手段）。")
        if mistakes:
            feedback.append("存在低血量硬拼的失误回合，考虑加入更能兜底的换人节拍成员。")
        if style == "激进":
            feedback.append("对手偏进攻，可考虑耐久向配置或先制招式反制。")
        if not feedback:
            feedback.append("整体发挥稳定，可保持当前阵容并微调配招覆盖面。")

        return {
            "team_selection_assessment": f"本场选出：{selection_text}，最终{result}。共有 {len(mistakes)} 个失误回合。",
            "lead_analysis": f"首发：{self._lead_species(record)}。结合对手画像（{style}），优先争取对位主动权。",
            "key_turn_alternatives": [
                f"回合 {review.turn}：{review.alternative}" for review in mistakes if review.alternative
            ]
            or ["没有明显需要修正的关键回合。"],
            "opponent_adjustments": list(profile.get("next_battle_tips") or ["保持常规准备即可。"]),
            "team_builder_feedback": feedback,
            "summary": f"对局{result}；对手风格偏{style}，共 {len(mistakes)} 处失误。",
        }

    def _lead_species(self, record: dict[str, Any]) -> str:
        for obs in record.get("player_1_observations") or []:
            mon = first_active(obs.get("active_pokemon"))
            if mon:
                return species_of(mon)
        return "未记录"
