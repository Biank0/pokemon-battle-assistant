"""对战 Agent 的 system prompt 与消息模板。"""

from __future__ import annotations

import json
from typing import Any

BATTLE_SYSTEM_PROMPT = """你是一个宝可梦 BSS Regulation I 单打对战专家（6选3、50级、允许太晶）。
你的任务：根据当前局面选择最优行动。

决策原则：
1. 优先用属性克制且能造成可观伤害的招式压制对方
2. 我方在场宝可梦可能被击倒或被严重压制时，考虑换人保留资源
3. 关注速度线：先手方可以安全收割残血，后手方要防被先手击倒
4. 对方已揭示的招式和换人习惯是重要信息（见对手模型）
5. 只能从「合法动作列表」中选择，绝不输出列表外的动作

你可以调用工具查询：属性克制（type_analyzer / weakness_profile）、伤害估算（damage_calculator）、
速度比较（speed_comparator）、威胁评估（threat_assessment，无需参数）、特性道具（ability_lookup）。

最终必须输出 JSON（不要输出其它文字）：
{"action": "<合法动作，如 move earthquake / switch pikachu>", "reasoning": "<一句话中文理由>"}"""

TEAM_PREVIEW_SYSTEM_PROMPT = """你是一个宝可梦 BSS Regulation I 单打选出专家（6选3、50级）。
你需要在 team preview 阶段从 6 只中选出 3 只参战（顺序有意义：第 1 只首发）。

选出原则：
1. 优先选出能克制对方核心的宝可梦
2. 覆盖对方主要威胁属性，避免选出被对方集体克制的一组
3. 首发选择对位好、不易被一击倒的宝可梦
4. 可以调用工具查询属性克制（type_analyzer / weakness_profile）和特性（ability_lookup）

最终必须输出 JSON（不要输出其它文字）：
{"slots": [1, 3, 5], "reasoning": "<一句话中文选出思路>"}
slots 是 3 个 1-6 的编号（不重复），第 1 个是首发。"""


def render_turn_user_message(
    observation: Any,
    plan: str,
    opponent_summary: dict[str, Any] | None = None,
) -> str:
    obs = observation.to_dict() if hasattr(observation, "to_dict") else dict(observation or {})
    legal_orders = [str(o) for o in obs.get("legal_orders") or []]
    lines = [
        f"=== 第 {obs.get('turn')} 回合 | {obs.get('phase')} ===",
        f"局面摘要：{obs.get('summary') or '（无）'}",
        "",
        "我方在场：{_fmt_mon(obs.get('my_active'))}",
        "对方在场：{_fmt_mon(obs.get('opponent_active'))}",
    ]
    if obs.get("weather") or obs.get("fields"):
        lines.append(f"天气/场地：{', '.join([*(obs.get('weather') or []), *(obs.get('fields') or [])])}")
    moves = obs.get("available_moves") or []
    if moves:
        move_descs = [
            f"{m.get('zh_name') or m.get('name')}({m.get('type')}, 威力{m.get('base_power')}, {m.get('category')})"
            for m in moves
        ]
        lines.append(f"我方可用招式：{'；'.join(move_descs)}")
    switches = obs.get("available_switches") or []
    if switches:
        switch_descs = [
            f"{s.get('zh_name') or s.get('species')}(HP {s.get('hp_percent')}%)" for s in switches
        ]
        lines.append(f"可换入：{'；'.join(switch_descs)}")
    if opponent_summary:
        lines.append(f"对手模型：{json.dumps(opponent_summary, ensure_ascii=False)}")
    lines.append(f"回合策略：{plan}")
    lines.append(f"合法动作列表：{json.dumps(legal_orders, ensure_ascii=False)}")
    lines.append("请从合法动作列表中选择最优动作，输出 JSON。")
    return "\n".join(lines)


def render_team_preview_message(
    observation: Any,
    plan: str,
    team_size: int,
) -> str:
    obs = observation.to_dict() if hasattr(observation, "to_dict") else dict(observation or {})
    my_team = obs.get("my_team") or []
    opp_team = obs.get("opponent_team") or []
    lines = [
        f"=== Team Preview（选出 {team_size} 只，第 1 只首发）===",
        f"选出策略参考：{plan}",
        "",
        "我方队伍：",
    ]
    for idx, mon in enumerate(my_team, 1):
        lines.append(f"  {idx}. {_fmt_mon(mon)}")
    lines.append("对方队伍：")
    for idx, mon in enumerate(opp_team, 1):
        lines.append(f"  {idx}. {_fmt_mon(mon)}")
    lines.append(f"请选出 {team_size} 只，输出 JSON。")
    return "\n".join(lines)


def _fmt_mon(mon: Any) -> str:
    if not mon:
        return "（无）"
    if hasattr(mon, "to_dict"):
        mon = mon.to_dict()
    name = mon.get("zh_name") or mon.get("species") or "?"
    types = "/".join(str(t) for t in (mon.get("types") or []))
    hp = mon.get("hp_percent")
    status = mon.get("status")
    text = f"{name}[{types}]"
    if hp is not None:
        text += f" HP{hp}%"
    if status:
        text += f" 状态:{status}"
    if mon.get("terastallized"):
        text += " (已太晶)"
    moves = mon.get("moves") or []
    if moves:
        text += f" 已揭示招式:{','.join(str(m) for m in moves[:4])}"
    return text
