"""LLM harness —— 最薄的模型调用封装。

设计约束（见 docs/module1_team_builder.md 第三节）：
- 不 import 项目内任何模块（保证模块三分析 bot 可原样复用）
- 配置全部来自 .env：OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL
- OpenAI 兼容 /chat/completions 端点（DeepSeek 等）
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field


@dataclass
class UsageStats:
    """累计用量统计（pipeline 结束时打印成本）"""
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    retries: int = 0
    elapsed_s: float = 0.0
    _t0s: list = field(default_factory=list, repr=False)

    def begin(self) -> None:
        self._t0s.append(time.perf_counter())

    def end(self) -> None:
        if self._t0s:
            self.elapsed_s += time.perf_counter() - self._t0s.pop()

    def summary(self) -> str:
        return (f"调用 {self.calls} 次（重试 {self.retries}）｜"
                f"tokens {self.prompt_tokens}+{self.completion_tokens}"
                f"={self.prompt_tokens + self.completion_tokens}｜耗时 {self.elapsed_s:.1f}s")


class LLMError(Exception):
    """重试耗尽后的最终失败"""


class LLMHarness:
    """同步 chat 封装：重试 / 超时 / json_mode / 用量统计。

    用法::

        h = LLMHarness.from_env()
        text = h.chat([{"role": "user", "content": "..."}], json_mode=True)
    """

    def __init__(self, api_key: str, base_url: str, model: str,
                 timeout_s: float = 60.0, max_retries: int = 3):
        if not api_key:
            raise LLMError("缺少 API key（.env 的 OPENAI_API_KEY）")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.stats = UsageStats()

    @classmethod
    def from_env(cls, env_path: str | os.PathLike | None = None) -> "LLMHarness":
        """从环境变量构造；可传入 .env 路径自动加载（找不到键则报错）"""
        if env_path is not None and os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        os.environ.setdefault(k.strip(), v.strip())
        return cls(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
            model=os.environ.get("OPENAI_MODEL", "deepseek-chat"),
        )

    # ------------------------------------------------------------------
    def chat(self, messages: list[dict], *, json_mode: bool = False,
             temperature: float = 0.7) -> str:
        """一次对话调用。json_mode=True 时服务端约束输出为 JSON。"""
        import httpx  # 延迟导入：离线测试不需要网络栈

        payload: dict = {"model": self.model, "messages": messages,
                         "temperature": temperature}
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            self.stats.begin()
            try:
                resp = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload, timeout=self.timeout_s,
                )
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise LLMError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                if resp.status_code != 200:
                    raise LLMError(f"HTTP {resp.status_code}（不重试）: {resp.text[:200]}")
                data = resp.json()
                self.stats.calls += 1
                u = data.get("usage") or {}
                self.stats.prompt_tokens += u.get("prompt_tokens", 0)
                self.stats.completion_tokens += u.get("completion_tokens", 0)
                return data["choices"][0]["message"]["content"]
            except (LLMError, httpx.HTTPError, json.JSONDecodeError) as e:
                last_err = e
                non_retryable = isinstance(e, LLMError) and "（不重试）" in str(e)
                if non_retryable or attempt == self.max_retries:
                    break
                self.stats.retries += 1
                time.sleep(2 ** attempt)  # 2s / 4s / 8s 指数退避
            finally:
                self.stats.end()
        raise LLMError(f"调用失败（{self.max_retries} 次尝试）: {last_err}")
