"""采集型对战 bot —— 继承 poke-env 自带启发式基线，加逐回合数据采集。

决策：SimpleHeuristicsPlayer（库自带分层启发式：估算伤害选最优招式、
估算对手威胁决定换人）。不重写决策逻辑，只在外面包一层记录器——
决策质量有库保证，采集零侵入。

采集：每次 choose_move 记录一条动作（回合/在场双方/招式或换人），
battle 结束后由 runner 合并双方记录写 battles.db。
"""
from __future__ import annotations

from poke_env.player.baselines import SimpleHeuristicsPlayer


class CollectorBot(SimpleHeuristicsPlayer):
    """带数据采集的启发式 bot。"""

    def __init__(self, username: str, team_text: str, battle_format: str, **kwargs):
        from poke_env.ps_client import AccountConfiguration
        from poke_env.ps_client.server_configuration import (
            LocalhostServerConfiguration,
        )
        from poke_env.teambuilder import ConstantTeambuilder

        super().__init__(
            account_configuration=AccountConfiguration(username, "pba-pass"),
            battle_format=battle_format,
            team=ConstantTeambuilder(team_text),
            server_configuration=LocalhostServerConfiguration,
            max_concurrent_battles=1,
            **kwargs,
        )
        self.records: list[dict] = []  # 本 bot 视角的逐动作记录

    def choose_move(self, battle):
        order = super().choose_move(battle)  # 启发式决策（不改动）
        try:
            self._record(battle, order)
        except Exception:
            pass  # 采集失败绝不影响对战
        return order

    def _record(self, battle, order) -> None:
        from poke_env.battle.move import Move
        from poke_env.battle.pokemon import Pokemon

        active = battle.active_pokemon
        opponent = battle.opponent_active_pokemon
        rec = {
            "turn": battle.turn,
            "actor_species": active.species if active else None,
            "opponent_species": opponent.species if opponent else None,
            "action": None,       # move slug 或 switch species 或 default
            "action_type": None,  # move / switch / team_order / default
        }
        # poke-env 0.15：SingleBattleOrder.order 是 Move | Pokemon | str（str=选队）
        inner = getattr(order, "order", order)
        if isinstance(inner, Move):
            rec["action_type"] = "move"
            rec["action"] = inner.id
        elif isinstance(inner, Pokemon):
            rec["action_type"] = "switch"
            rec["action"] = inner.species
        else:
            rec["action_type"] = "team_order"
            rec["action"] = str(inner)
        self.records.append(rec)
