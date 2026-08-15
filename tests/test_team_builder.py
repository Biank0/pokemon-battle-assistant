"""TeamBuilderAgent 单元测试（mock LLM）。"""

import json
import tempfile
import unittest
from pathlib import Path

from pokemon_battle_assistant.agent.llm_client import LLMResponse, ToolCall
from pokemon_battle_assistant.modules.team_builder.agent import TeamBuilderAgent
from pokemon_battle_assistant.modules.team_builder.generator import parse_team_json
from pokemon_battle_assistant.modules.team_builder.parser import RequirementParser

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BSS_BALANCE = PROJECT_ROOT / "data" / "trainers" / "bss_balance.json"


def load_balance() -> dict:
    return json.loads(BSS_BALANCE.read_text(encoding="utf-8"))


def _valid_team_content(reasoning: str = "这是一支平衡队伍。") -> str:
    return reasoning + "\n```json\n" + json.dumps(load_balance(), ensure_ascii=False) + "\n```"


def _broken_team_content() -> str:
    template = load_balance()
    template["team"][0]["moves"] = ["Make It Rain", "TotallyNotAMove"]
    return "先来一版\n```json\n" + json.dumps(template, ensure_ascii=False) + "\n```"


class FakeLLM:
    def __init__(self, responses: list) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def chat_with_tools(self, messages, tools=None, temperature=None):
        self.calls.append({"messages": len(messages), "tools": tools})
        if not self.responses:
            raise AssertionError("FakeLLM 响应队列已耗尽")
        return self.responses.pop(0)


class TestParseTeamJson(unittest.TestCase):
    def test_fenced_json_extracted(self):
        team, reasoning = parse_team_json(_valid_team_content("思路说明"))
        self.assertIsNotNone(team)
        self.assertEqual(len(team["team"]), 6)
        self.assertIn("思路说明", reasoning)
        self.assertNotIn("```", reasoning)

    def test_plain_json_fallback(self):
        content = '说明 {"name": "x", "team": [{"species": "Garchomp"}]}'
        team, _ = parse_team_json(content)
        self.assertIsNotNone(team)

    def test_no_json(self):
        team, reasoning = parse_team_json("完全没有 JSON")
        self.assertIsNone(team)
        self.assertEqual(reasoning, "完全没有 JSON")


class TestRequirementParser(unittest.TestCase):
    def test_chinese_requirement(self):
        intent = RequirementParser().parse("我想围绕烈咬陆鲨建一支偏进攻的队伍，需要克制妖精系")
        self.assertEqual(intent.core, "garchomp")
        self.assertEqual(intent.style, "offensive")
        self.assertIn("Fairy", intent.counters)
        self.assertTrue(intent.to_prompt_text())

    def test_english_requirement(self):
        intent = RequirementParser().parse("Build a balance team around Dragonite")
        self.assertEqual(intent.core, "dragonite")
        self.assertEqual(intent.style, "balanced")

    def test_no_intent_fields(self):
        intent = RequirementParser().parse("随便来一支队伍")
        self.assertIsNone(intent.core)
        self.assertIsNone(intent.style)


class TestTeamBuilderAgent(unittest.TestCase):
    def _agent(self, responses) -> tuple[TeamBuilderAgent, FakeLLM]:
        fake = FakeLLM(responses)
        agent = TeamBuilderAgent(llm=fake, run_showdown=False)  # type: ignore[arg-type]
        return agent, fake

    def test_generate_team_happy_path(self):
        meta_call = LLMResponse(
            content="",
            tool_calls=[
                ToolCall(id="c1", name="meta_analyzer", arguments='{"format": "gen9bssregi"}')
            ],
        )
        final = LLMResponse(content=_valid_team_content())
        agent, fake = self._agent([meta_call, final])
        result = agent.generate_team("围绕 Garchomp 的进攻队")
        self.assertTrue(result.valid, result.validation_errors)
        self.assertEqual(len(result.team["team"]), 6)
        self.assertEqual(result.tool_calls_log[0]["tool"], "meta_analyzer")
        self.assertEqual(len(fake.calls), 2)
        self.assertGreaterEqual(fake.calls[1]["messages"], 4)

    def test_generate_team_fix_loop(self):
        agent, fake = self._agent(
            [
                LLMResponse(content=_broken_team_content()),
                LLMResponse(content=_valid_team_content()),
            ]
        )
        result = agent.generate_team("平衡队")
        self.assertTrue(result.valid, result.validation_errors)
        self.assertGreaterEqual(len(fake.calls), 2)
        self.assertEqual(fake.calls[1]["messages"], fake.calls[0]["messages"] + 2)

    def test_generate_team_gives_up_after_max_fixes(self):
        agent, _ = self._agent(
            [LLMResponse(content=_broken_team_content()) for _ in range(4)]
        )
        result = agent.generate_team("平衡队")
        self.assertFalse(result.valid)
        self.assertTrue(result.validation_errors)

    def test_generate_team_no_json(self):
        agent, _ = self._agent([LLMResponse(content="我拒绝输出 JSON")])
        result = agent.generate_team("平衡队")
        self.assertFalse(result.valid)
        self.assertIn("JSON", "".join(result.validation_errors))

    def test_iterate_team_sets_parent(self):
        agent, _ = self._agent([LLMResponse(content=_valid_team_content("迭代版本"))])
        result = agent.iterate_team(
            load_balance(), {"win_rate": 0.4, "suggestions": ["换一只钢系"]}
        )
        self.assertTrue(result.valid, result.validation_errors)
        self.assertEqual(result.iteration, 1)
        self.assertIsNotNone(result.parent_team_hash)

    def test_save_team_writes_file(self):
        agent, _ = self._agent([LLMResponse(content=_valid_team_content())])
        result = agent.generate_team("平衡队")
        with tempfile.TemporaryDirectory() as tmp:
            path = agent.save_team(result, name="unit test team", root=Path(tmp))
            self.assertTrue(path.exists())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["team"]), 6)
            self.assertEqual(data["meta"]["generated_by"], "team_builder_agent")


if __name__ == "__main__":
    unittest.main()
