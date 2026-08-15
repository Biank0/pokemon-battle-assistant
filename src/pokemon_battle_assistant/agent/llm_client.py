"""Unified LLM client: OpenAI-compatible cloud API + local Ollama.

两种 backend：
- ``openai``：任何 OpenAI 兼容的 chat/completions 接口（api.openai.com 或自建网关）
- ``ollama``：本地 Ollama /api/chat 接口（无需 API key）

配置读取顺序：构造参数 > 环境变量 > 默认值。

环境变量：
- ``LLM_BACKEND``：``openai`` / ``ollama``（默认 ``openai``）
- ``OPENAI_API_KEY``：OpenAI backend 密钥
- ``OPENAI_BASE_URL``：默认 ``https://api.openai.com/v1``
- ``OPENAI_MODEL``：默认 ``gpt-4o-mini``
- ``OLLAMA_BASE_URL``：默认 ``http://localhost:11434``
- ``OLLAMA_MODEL``：默认 ``qwen2.5:7b``

实现说明：两个 backend 均通过 ``httpx`` 直连 REST（OpenAI 兼容协议本身即 REST），
不引入额外 SDK 依赖，方便统一 mock 测试。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

LLMBackend = Literal["openai", "ollama"]

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"

Message = dict[str, Any]
ToolSpec = dict[str, Any]


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class ToolCall:
    """一次工具调用请求（arguments 恒为 JSON 字符串）。"""

    id: str
    name: str
    arguments: str

    def parsed_arguments(self) -> dict[str, Any]:
        try:
            value = json.loads(self.arguments)
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}


@dataclass(frozen=True)
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: LLMUsage = field(default_factory=LLMUsage)
    model: str = ""
    backend: LLMBackend = "openai"

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "tool_calls": [c.to_dict() for c in self.tool_calls],
            "usage": self.usage.to_dict(),
            "model": self.model,
            "backend": self.backend,
        }


def _clean_base_url(url: str) -> str:
    return url.rstrip("/")


class LLMClient:
    """统一 LLM 接口：``chat()`` 与 ``chat_with_tools()``。"""

    def __init__(
        self,
        *,
        backend: LLMBackend | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.backend: LLMBackend = backend or os.environ.get("LLM_BACKEND", "openai").strip().lower()  # type: ignore[assignment]
        if self.backend not in ("openai", "ollama"):
            raise ValueError(f"未知 LLM backend：{self.backend}（支持 openai / ollama）")

        if self.backend == "openai":
            self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
            env_base = os.environ.get("OPENAI_BASE_URL") or DEFAULT_OPENAI_BASE_URL
            self.base_url = _clean_base_url(base_url if base_url else env_base)
            self.model = model or os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        else:
            self.api_key = ""
            ollama_base = os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL
            self.base_url = _clean_base_url(base_url if base_url else ollama_base)
            self.model = model or os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)

        self.timeout = timeout
        self._http = http_client

    # ------------------------------------------------------------------
    def chat(self, messages: list[Message], *, temperature: float | None = None) -> LLMResponse:
        """普通对话，返回文本内容。"""
        return self.chat_with_tools(messages, tools=None, temperature=temperature)

    def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        temperature: float | None = None,
    ) -> LLMResponse:
        """对话 + 可选工具定义，返回内容与工具调用请求。"""
        if self.backend == "openai":
            return self._chat_openai(messages, tools, temperature)
        return self._chat_ollama(messages, tools, temperature)

    # ------------------------------------------------------------------
    def _request(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.backend == "openai":
            if not self.api_key:
                raise RuntimeError("OpenAI backend 缺少 API key：请设置 OPENAI_API_KEY 或传入 api_key。")
            headers["Authorization"] = f"Bearer {self.api_key}"
        client = self._http or httpx.Client(timeout=self.timeout)
        try:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise RuntimeError(f"LLM 请求失败（HTTP {exc.response.status_code}）：{detail}") from exc
        finally:
            if self._http is None:
                client.close()

    def _chat_openai(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None,
        temperature: float | None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            payload["tools"] = tools
        if temperature is not None:
            payload["temperature"] = temperature
        data = self._request(f"{self.base_url}/chat/completions", payload)

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        tool_calls = [
            ToolCall(
                id=call.get("id", f"call_{i}"),
                name=(call.get("function") or {}).get("name", ""),
                arguments=(call.get("function") or {}).get("arguments", "{}"),
            )
            for i, call in enumerate(message.get("tool_calls") or [])
        ]
        usage_raw = data.get("usage") or {}
        usage = LLMUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens", 0)),
            completion_tokens=int(usage_raw.get("completion_tokens", 0)),
            total_tokens=int(usage_raw.get("total_tokens", 0)),
        )
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            model=data.get("model", self.model),
            backend="openai",
        )

    def _chat_ollama(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None,
        temperature: float | None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        data = self._request(f"{self.base_url}/api/chat", payload)

        message = data.get("message") or {}
        content = message.get("content") or ""
        tool_calls: list[ToolCall] = []
        for i, call in enumerate(message.get("tool_calls") or []):
            function = call.get("function") or {}
            arguments = function.get("arguments", {})
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments, ensure_ascii=False)
            tool_calls.append(
                ToolCall(
                    id=call.get("id", f"call_{i}"),
                    name=function.get("name", ""),
                    arguments=arguments or "{}",
                )
            )
        usage_raw = data.get("prompt_eval_count"), data.get("eval_count")
        usage = LLMUsage(
            prompt_tokens=int(usage_raw[0] or 0),
            completion_tokens=int(usage_raw[1] or 0),
            total_tokens=int(usage_raw[0] or 0) + int(usage_raw[1] or 0),
        )
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            model=data.get("model", self.model),
            backend="ollama",
        )
