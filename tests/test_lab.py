"""模块二（对战实验室）离线单测。

不启动 Showdown、不连网——只测纯函数与真实库的只读查询；
完整链路由 tests/manual/smoke_battle.py + smoke_lab_api.py 覆盖。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokemon_battle_assistant.lab import runner, session


class _Battle:
    """poke-env AbstractBattle 的最小 stub。"""

    def __init__(self, won=False, lost=False, turn=0, battle_tag=None):
        self.won, self.lost = won, lost
        self.turn, self.battle_tag = turn, battle_tag


class _Bot:
    def __init__(self, battles):
        self.battles = battles


class WinnerTest(unittest.TestCase):
    def test_a_wins(self):
        a = _Bot({"b1": _Battle(won=True)})
        b = _Bot({"b1": _Battle(lost=True)})
        self.assertEqual(runner._winner_of(a, b), "a")

    def test_b_wins(self):
        a = _Bot({"b1": _Battle(lost=True)})
        b = _Bot({"b1": _Battle(won=True)})
        self.assertEqual(runner._winner_of(a, b), "b")

    def test_draw_when_no_flags(self):
        a = _Bot({"b1": _Battle()})
        b = _Bot({"b1": _Battle()})
        self.assertEqual(runner._winner_of(a, b), "draw")


class BattleMetaTest(unittest.TestCase):
    def test_meta(self):
        a = _Bot({"b1": _Battle(turn=7, battle_tag="battle-gen9bssregi-1")})
        b = _Bot({})
        turn, tag = runner._battle_meta(a, b)
        self.assertEqual(turn, 7)
        self.assertEqual(tag, "battle-gen9bssregi-1")

    def test_meta_empty(self):
        self.assertEqual(runner._battle_meta(_Bot({}), _Bot({})), (0, None))


class TeamLookupTest(unittest.TestCase):
    """真实 teams.db 只读查询（种子数据存在为前提）。"""

    def test_get_team_returns_export(self):
        t = session.get_team("xiaobian")
        self.assertEqual(t["name"], "xiaobian")
        self.assertEqual(t["format"], "gen9bssregi")
        self.assertIn("Ninetales", t["export_text"])  # 种子队伍含九尾

    def test_get_team_missing(self):
        with self.assertRaises(KeyError):
            session.get_team("no_such_team")


class DexMapTest(unittest.TestCase):
    def test_moves_zh(self):
        m = session._dex_maps()["moves"]
        self.assertEqual(m.get("hydrosteam"), "水蒸气")  # 冒烟实测出现过的招式
        self.assertIn("earthquake", m)


if __name__ == "__main__":
    unittest.main()
