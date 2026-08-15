"""对手画像：纯规则统计对手行为模式与已揭示信息。"""

from __future__ import annotations

from typing import Any

from .replayer import count_fainted, species_of


class OpponentProfiler:
    """从对战记录统计对手行为模式（换人率/风格/太晶/已揭示信息）。"""

    def profile(self, record: dict[str, Any]) -> dict[str, Any]:
        battle = record.get("battle") or {}
        our_obs = record.get("player_1_observations") or []
        opp_obs = record.get("player_2_observations") or []

        actions = [
            str(obs.get("chosen_order_message") or "").strip().lower()
            for obs in opp_obs
            if obs.get("chosen_order_message")
        ]
        total = len(actions)
        switch_count = sum(1 for action in actions if action.startswith("switch"))
        tera_used = any("terastallize" in action for action in actions)
        switch_rate = round(switch_count / total, 3) if total else 0.0

        revealed: list[str] = []
        items: list[str] = []
        abilities: list[str] = []
        for obs in our_obs:
            for mon in obs.get("opponent_team") or []:
                if not isinstance(mon, dict):
                    continue
                name = species_of(mon)
                if name not in revealed:
                    revealed.append(name)
                item = str(mon.get("item") or "")
                if item and item not in ("None", "") and item not in items:
                    items.append(item)
                ability = str(mon.get("ability") or "")
                if ability and ability not in ("None", "") and ability not in abilities:
                    abilities.append(ability)

        our_kos = max((count_fainted(obs.get("team")) for obs in our_obs), default=0)
        opponent_kos = max((count_fainted(obs.get("opponent_team")) for obs in our_obs), default=0)
        style = "激进" if switch_rate < 0.15 else ("均衡" if switch_rate < 0.35 else "保守")

        return {
            "schema_version": "opponent-profile.v1",
            "battle_tag": str(battle.get("battle_tag") or ""),
            "opponent_source": str(record.get("opponent_source") or battle.get("opponent_username") or ""),
            "actions_total": total,
            "switch_count": switch_count,
            "switch_rate": switch_rate,
            "style": style,
            "tera_used": tera_used,
            "revealed_pokemon": revealed,
            "revealed_items": items,
            "revealed_abilities": abilities,
            "our_kos": our_kos,
            "opponent_kos": opponent_kos,
            "next_battle_tips": self._tips(style, tera_used, our_kos, opponent_kos),
        }

    def _tips(self, style: str, tera_used: bool, our_kos: int, opponent_kos: int) -> list[str]:
        tips: list[str] = []
        if style == "激进":
            tips.append("对手偏好正面硬拼，准备先制招式或耐久型受位来消耗其节奏。")
        elif style == "保守":
            tips.append("对手换人频繁，善用伏击/强化机会，避免被其拉扯血线。")
        else:
            tips.append("对手攻守均衡，优先按对位优势规划每回合行动。")
        if tera_used:
            tips.append("对手已展示太晶化倾向，关键回合务必预留太晶反制意识。")
        if opponent_kos == 0:
            tips.append("本场未能击倒对手任何宝可梦，需要补足输出力度或克制面。")
        elif our_kos >= opponent_kos:
            tips.append("人数交换上我方吃亏，注意保存关键成员的血量。")
        return tips
