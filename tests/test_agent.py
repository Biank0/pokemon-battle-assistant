"""BattleAgent（Phase 3.2）单元测试：mock LLM 验证工具调用、JSON 解析、合法动作提取、选出决策。"""

from __future__ import annotations

import unittest
from typing import Any

from pokemon_battle_assistant.agent.agent import (
    BattleAgent,
    extract_legal_order,
    parse_json_payload,
)
from pokemon_battle_assistant.agent.decision_logger import DecisionLogger
from pokemon_battle_assistant.agent.llm_client import LLMResponse, ToolCall
from pokemon_battle_assistant.perception.observation import (
    BattleObservation,
    LegalOrder,
    MoveInfo,
    PokemonSnapshot,
)


class FakeLLM:
    """按脚本回放响应的假 LLM 客户端。"""

    backend = "openai"
    model = "fake-model"

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def chat(self, messages: list[dict], *, temperature: float | None = None) -> LLMResponse:
        return self.chat_with_tools(messages, tools=None, temperature=temperature)

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        *,
        temperature: float | None = None,
    ) -> LLMResponse:
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools})
        item = self.responses.pop(0)
        if isinstance(item, LLMResponse):
            return item
        return LLMResponse(content=str(item))


def make_observation(
    *,
    legal_orders: list[str] | None = None,
    available_moves: list[MoveInfo] | None = None,
) -> BattleObservation:
    mine = PokemonSnapshot(
        species="Garchomp",
        zh_name="烈咬陆鲨",
        level=50,
        hp_percent=70.0,
        status=None,
        types=("Dragon", "Ground"),
        tera_type=None,
        terastallized=False,
        item=None,
        ability=None,
        moves=("earthquake",),
        fainted=False,
    )
    opp = PokemonSnapshot(
        species="Tyranitar",
        zh_name="班基拉斯",
        level=50,
        hp_percent=55.0,
        status=None,
        types=("Rock", "Dark"),
        tera_type=None,
        terastallized=False,
        item=None,
        ability=None,
        moves=("crunch",),
        fainted=False,
    )
    return BattleObservation(
        battle_tag="battle-gen9bssregi-1",
        turn=4,
        format="gen9bssregi",
        game_type="singles",
        my_active=mine,
        opponent_active=opp,
        available_moves=available_moves or [],
        legal_orders=[LegalOrder(message=m) for m in (legal_orders or [])],
    )


class TestParseJsonPayload(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_json_payload('{"action": "move earthquake"}')["action"], "move earthquake")

    def test_fenced(self):
        text = '说明如下\n```json\n{"slots": [1, 2, 4], "reasoning": "对位好"}\n```'
        payload = parse_json_payload(text)
        self.assertEqual(payload["slots"], [1, 2, 4])

    def test_noise(self):
        text = '我认为应该 {"action": "switch garchomp", "reasoning": "保命"} 就这样'
        payload = parse_json_payload(text)
        self.assertEqual(payload["action"], "switch garchomp")

    def test_invalid(self):
        self.assertIsNone(parse_json_payload("没有 JSON"))
        self.assertIsNone(parse_json_payload(""))


class TestExtractLegalOrder(unittest.TestCase):
    LEGAL = ["/choose move earthquake", "/choose move fireblast", "/choose switch garchomp"]

    def test_exact_with_prefix(self):
        self.assertEqual(extract_legal_order("/choose move earthquake", self.LEGAL), self.LEGAL[0])

    def test_without_prefix(self):
        self.assertEqual(extract_legal_order("move earthquake", self.LEGAL), self.LEGAL[0])

    def test_case_insensitive(self):
        self.assertEqual(extract_legal_order("Move EarthQuake", self.LEGAL), self.LEGAL[0])

    def test_switch(self):
        self.assertEqual(extract_legal_order("switch Garchomp", self.LEGAL), self.LEGAL[2])

    def test_no_match(self):
        self.assertIsNone(extract_legal_order("move surf", self.LEGAL))
        self.assertIsNone(extract_legal_order("", self.LEGAL))


class TestDecideTurn(unittest.TestCase):
    def test_direct_json(self):
        obs = make_observation(legal_orders=["/choose move earthquake", "/choose switch garchomp"])
        llm = FakeLLM(['{"action": "move earthquake", "reasoning": "地面克制"}'])
        agent = BattleAgent(llm=llm)  # type: ignore[arg-type]
        decision = agent.decide_turn(obs)
        self.assertEqual(decision.order_message, "/choose move earthquake")
        self.assertEqual(decision.reasoning, "地面克制")
        self.assertFalse(decision.fallback)
        self.assertEqual(len(agent.logger), 1)

    def test_tool_round_then_json(self):
        obs = make_observation(legal_orders=["/choose move earthquake"])
        tool_response = LLMResponse(
            content="",
            tool_calls=[
                ToolCall(id="c1", name="type_analyzer", arguments='{"move_type": "Ground", "defender_types": ["Rock", "Dark"]}')
            ],
        )
        final = LLMResponse(content='{"action": "move earthquake", "reasoning": "2倍克制"}')
        llm = FakeLLM([tool_response, final])
        agent = BattleAgent(llm=llm)  # type: ignore[arg-type]
        decision = agent.decide_turn(obs)
        self.assertEqual(decision.order_message, "/choose move earthquake")
        self.assertEqual(len(decision.tool_calls_log), 1)
        self.assertEqual(decision.tool_calls_log[0]["name"], "type_analyzer")
        # 第二轮 messages 应包含工具结果
        self.assertEqual(len(llm.calls), 2)

    def test_fallback_on_unparseable(self):
        obs = make_observation(legal_orders=["/choose move earthquake", "/choose switch garchomp"])
        llm = FakeLLM(["抱歉我不知道怎么输出"])
        agent = BattleAgent(llm=llm)  # type: ignore[arg-type]
        decision = agent.decide_turn(obs)
        self.assertTrue(decision.fallback)
        self.assertEqual(decision.order_message, "/choose move earthquake")

    def test_fallback_on_illegal_action(self):
        obs = make_observation(legal_orders=["/choose move earthquake"])
        llm = FakeLLM(['{"action": "move surf", "reasoning": "水招式"}'])
        agent = BattleAgent(llm=llm)  # type: ignore[arg-type]
        decision = agent.decide_turn(obs)
        self.assertTrue(decision.fallback)
        self.assertEqual(decision.order_message, "/choose move earthquake")


class TestDecideTeamPreview(unittest.TestCase):
    def _preview_observation(self) -> BattleObservation:
        def mon(species: str, zh: str, types: tuple[str, ...]) -> PokemonSnapshot:
            return PokemonSnapshot(
                species=species,
                zh_name=zh,
                level=50,
                hp_percent=100.0,
                status=None,
                types=types,
                tera_type=None,
                terastallized=False,
                item=None,
                ability=None,
                moves=(),
                fainted=False,
            )

        my_team = [
            mon("Garchomp", "烈咬陆鲨", ("Dragon", "Ground")),
            mon("Tyranitar", "班基拉斯", ("Rock", "Dark")),
            mon("Rotom-Wash", "洗衣机洛托姆", ("Electric", "Water")),
            mon("Dragonite", "快龙", ("Dragon", "Flying")),
            mon("Amoonguss", "败露球菇", ("Grass", "Poison")),
            mon("Chien-Pao", "古剑豹", ("Dark", "Ice")),
        ]
        opp_team = [
            mon("Gholdengo", "赛富豪", ("Steel", "Ghost")),
            mon("Dragonite", "快龙", ("Dragon", "Flying")),
            mon("Iron Hands", "铁臂膀", ("Fighting", "Electric")),
        ]
        return BattleObservation(
            battle_tag="battle-preview",
            turn=0,
            format="gen9bssregi",
            game_type="singles",
            my_active=None,
            opponent_active=None,
            my_team=my_team,
            opponent_team=opp_team,
        )

    def test_valid_slots(self):
        llm = FakeLLM(['{"slots": [2, 4, 6], "reasoning": "覆盖钢鬼"}'])
        agent = BattleAgent(llm=llm)  # type: ignore[arg-type]
        decision = agent.decide_team_preview(self._preview_observation())
        self.assertEqual(decision.slots, [2, 4, 6])
        self.assertEqual(decision.order_message, "/team 246")
        self.assertFalse(decision.fallback)

    def test_fallback_slots(self):
        llm = FakeLLM(["无法决策"])
        agent = BattleAgent(llm=llm)  # type: ignore[arg-type]
        decision = agent.decide_team_preview(self._preview_observation())
        self.assertTrue(decision.fallback)
        self.assertEqual(decision.slots, [1, 2, 3])

    def test_invalid_slots_repaired(self):
        llm = FakeLLM(['{"slots": [99, 2, "bad"], "reasoning": "测试修复"}'])
        agent = BattleAgent(llm=llm)  # type: ignore[arg-type]
        decision = agent.decide_team_preview(self._preview_observation())
        # 99 和 "bad" 被丢弃，只留 2，再补足 1、3
        self.assertEqual(decision.slots, [2, 1, 3])
        self.assertFalse(decision.fallback)


class BrokenLLM:
    """始终抛异常的假 LLM，验证无 key/网络时的降级路径。"""

    backend = "openai"
    model = "broken"

    def chat(self, messages: list[dict], *, temperature: float | None = None) -> Any:
        raise RuntimeError("no api key")

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        *,
        temperature: float | None = None,
    ) -> Any:
        raise RuntimeError("no api key")


class TestLLMUnavailableFallback(unittest.TestCase):
    def test_decide_turn_falls_back_when_llm_raises(self) -> None:
        agent = BattleAgent(BrokenLLM())  # type: ignore[arg-type]
        observation = make_observation(legal_orders=["/choose move earthquake"])
        decision = agent.decide_turn(observation)
        self.assertTrue(decision.fallback)
        self.assertEqual(decision.order_message, "/choose move earthquake")

    def test_decide_team_preview_falls_back_when_llm_raises(self) -> None:
        agent = BattleAgent(BrokenLLM())  # type: ignore[arg-type]
        observation = make_observation()
        decision = agent.decide_team_preview(observation)
        self.assertTrue(decision.fallback)
        self.assertEqual(decision.slots, [1, 2, 3])
        self.assertEqual(decision.order_message, "/team 123")


class TestDecisionLogger(unittest.TestCase):
    def test_records_export(self):
        logger = DecisionLogger()
        logger.log(turn=1, decision_type="turn", order_message="/choose move 1", reasoning="r", started_at=1.0)
        logger.log(turn=0, decision_type="team_preview", order_message="/team 123", reasoning="s")
        data = logger.to_list()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["decision_type"], "turn")
        self.assertEqual(data[1]["order_message"], "/team 123")


if __name__ == "__main__":
    unittest.main()
