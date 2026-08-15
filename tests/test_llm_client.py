"""Tests for the unified LLM client (mocked HTTP via httpx.MockTransport)."""

from __future__ import annotations

import json
import unittest

import httpx

from pokemon_battle_assistant.agent import LLMClient, LLMResponse, ToolCall

OPENAI_CHAT_RESPONSE = {
    "model": "gpt-4o-mini",
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": "建议换上耿鼠。",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "choose_order",
                            "arguments": json.dumps({"index": 3}, ensure_ascii=False),
                        },
                    }
                ],
            }
        }
    ],
    "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
}

OLLAMA_CHAT_RESPONSE = {
    "model": "qwen2.5:7b",
    "message": {
        "role": "assistant",
        "content": "建议使用大声咆哮。",
        "tool_calls": [
            {
                "function": {
                    "name": "choose_order",
                    "arguments": {"index": 1},  # Ollama 原生返回 dict
                }
            }
        ],
    },
    "prompt_eval_count": 80,
    "eval_count": 15,
}


def mock_client(handler) -> LLMClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return LLMClient(backend="openai", api_key="test-key", http_client=http)


class TestOpenAIBackend(unittest.TestCase):
    def test_chat_success(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/chat/completions")
            assert request.headers["Authorization"] == "Bearer test-key"
            body = json.loads(request.content)
            assert body["model"] == "gpt-4o-mini"
            assert len(body["messages"]) == 1
            return httpx.Response(200, json=OPENAI_CHAT_RESPONSE)

        client = mock_client(handler)
        response = client.chat([{"role": "user", "content": "该做什么？"}])
        self.assertEqual(response.content, "建议换上耿鼠。")
        self.assertEqual(response.backend, "openai")
        self.assertEqual(response.usage.total_tokens, 120)
        self.assertEqual(len(response.tool_calls), 1)
        self.assertEqual(response.tool_calls[0].name, "choose_order")
        self.assertEqual(response.tool_calls[0].parsed_arguments(), {"index": 3})

    def test_tools_are_sent(self):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert "tools" in body and body["tools"][0]["function"]["name"] == "choose_order"
            return httpx.Response(200, json=OPENAI_CHAT_RESPONSE)

        client = mock_client(handler)
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "choose_order",
                    "description": "选择一个合法动作",
                    "parameters": {"type": "object", "properties": {"index": {"type": "integer"}}},
                },
            }
        ]
        response = client.chat_with_tools([{"role": "user", "content": "go"}], tools=tools)
        self.assertEqual(response.model, "gpt-4o-mini")

    def test_missing_api_key_raises(self):
        client = LLMClient(backend="openai", api_key=None)
        original = client.__dict__.get("api_key", "")
        client.api_key = ""  # type: ignore[misc]
        try:
            with self.assertRaises(RuntimeError):
                client.chat([{"role": "user", "content": "hi"}])
        finally:
            client.api_key = original or ""  # type: ignore[misc]

    def test_http_error_raises_with_detail(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, text='{"error": "bad key"}')

        client = mock_client(handler)
        with self.assertRaises(RuntimeError) as ctx:
            client.chat([{"role": "user", "content": "hi"}])
        self.assertIn("401", str(ctx.exception))


class TestOllamaBackend(unittest.TestCase):
    def test_chat_normalizes_tool_call_arguments(self):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/api/chat")
            body = json.loads(request.content)
            assert body["stream"] is False
            assert body["model"] == "qwen2.5:7b"
            return httpx.Response(200, json=OLLAMA_CHAT_RESPONSE)

        http = httpx.Client(transport=httpx.MockTransport(handler))
        client = LLMClient(backend="ollama", http_client=http)
        response = client.chat([{"role": "user", "content": "该做什么？"}])
        self.assertEqual(response.backend, "ollama")
        self.assertEqual(response.content, "建议使用大声咆哮。")
        self.assertEqual(response.usage.total_tokens, 95)
        # dict 形式的 arguments 被规范化为 JSON 字符串
        self.assertEqual(response.tool_calls[0].arguments, '{"index": 1}')
        self.assertEqual(response.tool_calls[0].parsed_arguments(), {"index": 1})


class TestConfig(unittest.TestCase):
    def test_invalid_backend_rejected(self):
        with self.assertRaises(ValueError):
            LLMClient(backend="azure")

    def test_env_backend_switch(self):
        import os

        old = os.environ.get("LLM_BACKEND")
        os.environ["LLM_BACKEND"] = "ollama"
        try:
            client = LLMClient()
            self.assertEqual(client.backend, "ollama")
            self.assertEqual(client.base_url, "http://localhost:11434")
        finally:
            if old is None:
                os.environ.pop("LLM_BACKEND", None)
            else:
                os.environ["LLM_BACKEND"] = old

    def test_default_openai_config(self):
        client = LLMClient(api_key="k")
        self.assertEqual(client.backend, "openai")
        self.assertEqual(client.base_url, "https://api.openai.com/v1")
        self.assertEqual(client.model, "gpt-4o-mini")


class TestDataclasses(unittest.TestCase):
    def test_tool_call_bad_arguments(self):
        call = ToolCall(id="1", name="f", arguments="not-json")
        self.assertEqual(call.parsed_arguments(), {})

    def test_response_to_dict(self):
        response = LLMResponse(content="ok", model="m", backend="ollama")
        d = response.to_dict()
        self.assertEqual(d["content"], "ok")
        self.assertEqual(d["backend"], "ollama")


if __name__ == "__main__":
    unittest.main()
