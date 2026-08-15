"""对战回放解析：从 record.json 提取关键事件与时间线摘要。

纯规则实现，无 LLM 依赖：选出 / 击倒 / 换人 / 太晶化事件 + 关键回合标记。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReplayEvent:
    """时间线上的一个关键事件。"""

    turn: int
    kind: str  # team_preview / knockout / switch / tera / result
    player: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"turn": self.turn, "kind": self.kind, "player": self.player, "detail": self.detail}


@dataclass
class ReplayTimeline:
    """整局时间线。"""

    battle_tag: str
    events: list[ReplayEvent] = field(default_factory=list)
    key_turns: list[int] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "battle_tag": self.battle_tag,
            "events": [event.to_dict() for event in self.events],
            "key_turns": list(self.key_turns),
            "summary": self.summary,
        }


def species_of(mon: Any) -> str:
    if isinstance(mon, dict):
        return str(mon.get("species") or mon.get("base_species") or "未知")
    return "未知"


def count_fainted(team: Any) -> int:
    if not isinstance(team, list):
        return 0
    return sum(
        1
        for mon in team
        if isinstance(mon, dict) and (mon.get("fainted") is True or mon.get("status") == "濒死")
    )


class BattleReplayer:
    """解析对战记录，生成关键事件时间线与摘要。"""

    def replay(self, record: dict[str, Any]) -> ReplayTimeline:
        battle = record.get("battle") or {}
        battle_tag = str(battle.get("battle_tag") or record.get("battle_tag") or "")
        events: list[ReplayEvent] = []
        events.extend(self._team_preview_events(record))
        events.extend(self._knockout_events(record))
        events.extend(self._action_events(record))
        events.sort(key=lambda event: (event.turn, event.kind, event.player))
        result_event = self._result_event(record)
        if result_event is not None:
            events.append(result_event)
        key_turns = sorted({event.turn for event in events if event.kind in ("knockout", "switch", "tera")})
        timeline = ReplayTimeline(battle_tag=battle_tag, events=events, key_turns=key_turns)
        timeline.summary = self._summary(record, key_turns, events)
        return timeline

    def _team_preview_events(self, record: dict[str, Any]) -> list[ReplayEvent]:
        events: list[ReplayEvent] = []
        preview = record.get("team_preview") or {}
        if not isinstance(preview, dict):
            return events
        for player in ("player_1", "player_2"):
            entry = preview.get(player)
            if not isinstance(entry, dict):
                continue
            slots = entry.get("selected_slots") or []
            events.append(ReplayEvent(0, "team_preview", player, f"选出槽位：{slots}"))
        return events

    def _knockout_events(self, record: dict[str, Any]) -> list[ReplayEvent]:
        """击倒事件只从 player_1 视角推导，避免双方观测重复计数。"""
        events: list[ReplayEvent] = []
        own_prev = 0
        opp_prev = 0
        for obs in record.get("player_1_observations") or []:
            turn = int(obs.get("turn") or 0)
            own_now = count_fainted(obs.get("team"))
            opp_now = count_fainted(obs.get("opponent_team"))
            if own_now > own_prev:
                events.append(ReplayEvent(turn, "knockout", "player_1", f"我方倒下第 {own_now} 只宝可梦"))
            if opp_now > opp_prev:
                events.append(ReplayEvent(turn, "knockout", "player_2", f"对手倒下第 {opp_now} 只宝可梦"))
            own_prev, opp_prev = own_now, opp_now
        return events

    def _action_events(self, record: dict[str, Any]) -> list[ReplayEvent]:
        events: list[ReplayEvent] = []
        for player, key in (
            ("player_1", "player_1_observations"),
            ("player_2", "player_2_observations"),
        ):
            for obs in record.get(key) or []:
                turn = int(obs.get("turn") or 0)
                message = str(obs.get("chosen_order_message") or "").strip()
                lowered = message.lower()
                if not message:
                    continue
                if lowered.startswith("switch"):
                    events.append(ReplayEvent(turn, "switch", player, f"换人：{message}"))
                if "terastallize" in lowered:
                    events.append(ReplayEvent(turn, "tera", player, f"太晶化：{message}"))
        return events

    def _result_event(self, record: dict[str, Any]) -> ReplayEvent | None:
        battle = record.get("battle") or {}
        if battle.get("won"):
            detail = "我方获胜"
        elif battle.get("lost"):
            detail = "我方落败"
        else:
            detail = "对局未完成"
        return ReplayEvent(int(battle.get("turns") or 0), "result", "player_1", detail)

    def _summary(self, record: dict[str, Any], key_turns: list[int], events: list[ReplayEvent]) -> str:
        battle = record.get("battle") or {}
        turns = int(battle.get("turns") or 0)
        result = "获胜" if battle.get("won") else ("落败" if battle.get("lost") else "未完成")
        key_text = "、".join(str(turn) for turn in key_turns[:8]) or "无"
        return f"共 {turns} 回合，结果：我方{result}；关键回合：{key_text}；事件总数 {len(events)}。"
