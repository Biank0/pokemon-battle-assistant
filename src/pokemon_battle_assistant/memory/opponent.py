"""Opponent modeling: behavior prediction from short-term memory."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..perception.observation import BattleObservation
    from .short_term import ShortTermMemory


class OpponentModel:
    """基于本局已揭示信息的对手行为预测与威胁评估。

    刻意保持启发式、可解释：概率 = 频率 + 少量场景修正。
    """

    def __init__(self, short_term: ShortTermMemory) -> None:
        self.memory = short_term

    # ---- 行为预测 ----
    def predict_next_move(self, observation: BattleObservation) -> dict[str, Any] | None:
        """预测对手当前在场宝可梦下一步最可能使用的招式。"""
        opp = observation.opponent_active
        if opp is None:
            return None
        record = self.memory.revealed_pokemon.get(opp.species)
        if record is None or not record.moves:
            return None
        move_counts = self._move_usage_counts(opp.species)
        if move_counts:
            best, count = max(move_counts.items(), key=lambda kv: kv[1])
            confidence = min(0.9, 0.3 + 0.15 * count)
        else:
            # 没有使用历史：假设对手倾向第一揭示招式
            best, count = record.moves[0], 0
            confidence = 0.3
        return {
            "species": opp.species,
            "predicted_move": best,
            "confidence": confidence,
            "known_moves": list(record.moves),
        }

    def _move_usage_counts(self, species: str) -> dict[str, int]:
        """从行动历史中统计该宝可梦的招式使用频率（忽略空格/大小写）。"""
        record = self.memory.revealed_pokemon.get(species)
        if record is None:
            return {}
        counts: dict[str, int] = {}
        for action in self.memory.action_history:
            order = (action.opponent_order or "").lower().replace(" ", "")
            if not order:
                continue
            for move in record.moves:
                if move.lower().replace(" ", "") in order:
                    counts[move] = counts.get(move, 0) + 1
                    break
        return counts

    def switch_tendency(self, observation: BattleObservation) -> str:
        """估计对手换人倾向：low / medium / high。"""
        opp = observation.opponent_active
        if opp is None:
            return "low"
        if opp.hp_percent is not None and opp.hp_percent <= 30:
            return "high"
        if opp.status and opp.hp_percent is not None and opp.hp_percent <= 60:
            return "medium"
        return "low"

    # ---- 威胁评估 ----
    def assess_threats(self, observation: BattleObservation) -> list[str]:
        """列出对手在场宝可梦对我方在场的威胁点（中文描述）。"""
        threats: list[str] = []
        opp = observation.opponent_active
        mine = observation.my_active
        if opp is None or mine is None:
            return threats

        record = self.memory.revealed_pokemon.get(opp.species)
        known_moves = record.moves if record else []
        if known_moves:
            threats.append(f"{opp.species} 已揭示招式：{'、'.join(known_moves)}")

        if opp.terastallized and opp.tera_type:
            threats.append(f"{opp.species} 已太晶化（{opp.tera_type}），属性克制关系已改变")

        revealed_item = opp.item or (record.item if record else None)
        if revealed_item:
            threats.append(f"{opp.species} 已揭示道具：{revealed_item}")

        if mine.hp_percent is not None and mine.hp_percent <= 35:
            threats.append("我方在场血量危险，注意保护或换人")

        return threats

    def summary(self, observation: BattleObservation) -> dict[str, Any]:
        prediction = self.predict_next_move(observation)
        return {
            "predicted_move": prediction["predicted_move"] if prediction else None,
            "switch_tendency": self.switch_tendency(observation),
            "threats": self.assess_threats(observation),
            "revealed_count": len(self.memory.revealed_pokemon),
        }
