"""设置 API：查看/更新 LLM 连接配置（.env 的 OPENAI_* 三件套）+ 连接测试。

GET  /api/settings        当前配置（key 打码，如 sk-12****abcd）
POST /api/settings        更新：写 .env + 同步进程环境变量（新任务立即生效）
POST /api/settings/test   用当前配置发起一次最小 LLM 调用验证连通性

协议说明：项目走 OpenAI 兼容协议（POST {base_url}/chat/completions +
Bearer 鉴权），换服务商只需改 base_url/model/key 三项。
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...harness.llm import LLMError, LLMHarness

ROOT_DIR = Path(__file__).resolve().parents[4]
ENV_PATH = ROOT_DIR / ".env"

router = APIRouter()


def _mask(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:5] + "****" + key[-4:]


def _load_env_file() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    out: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


def _current() -> dict:
    env = _load_env_file()
    key = os.environ.get("OPENAI_API_KEY") or env.get("OPENAI_API_KEY", "")
    base = (os.environ.get("OPENAI_BASE_URL")
            or env.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1"))
    model = os.environ.get("OPENAI_MODEL") or env.get("OPENAI_MODEL", "deepseek-chat")
    return {"api_key_masked": _mask(key), "has_key": bool(key),
            "base_url": base, "model": model}


@router.get("/settings")
def get_settings():
    return _current()


class SettingsUpdate(BaseModel):
    api_key: str = ""    # 空 = 保持现有 key 不变
    base_url: str = ""
    model: str = ""


@router.post("/settings")
def update_settings(req: SettingsUpdate):
    updates: dict[str, str] = {}
    if req.api_key.strip():
        updates["OPENAI_API_KEY"] = req.api_key.strip()
    if req.base_url.strip():
        updates["OPENAI_BASE_URL"] = req.base_url.strip().rstrip("/")
    if req.model.strip():
        updates["OPENAI_MODEL"] = req.model.strip()
    if not updates:
        return _current()

    # 原位替换 .env 对应行（保留注释和其他键），缺则追加
    lines = (ENV_PATH.read_text(encoding="utf-8").splitlines()
             if ENV_PATH.exists() else [])
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.partition("=")[0].strip()
            if k in updates:
                out.append(f"{k}={updates[k]}")
                seen.add(k)
                continue
        out.append(line)
    out.extend(f"{k}={v}" for k, v in updates.items() if k not in seen)
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")

    # harness 用 os.environ.setdefault 加载 .env，进程内已有值不会刷新
    # → 必须同步环境变量，后续任务才能立即用新配置
    for k, v in updates.items():
        os.environ[k] = v
    return _current()


@router.post("/settings/test")
def test_connection():
    try:
        h = LLMHarness.from_env(ENV_PATH)
    except LLMError as e:
        raise HTTPException(400, f"配置异常: {e}")
    h.timeout_s = 15  # 测试连接不必等满 60s
    try:
        reply = h.chat([{"role": "user", "content": "只回复两个字：正常"}],
                       temperature=0.0)
    except LLMError as e:
        raise HTTPException(400, f"连接失败: {str(e)[:200]}")
    return {"ok": True, "model": h.model, "reply": reply.strip()[:20],
            "usage": h.stats.summary()}
