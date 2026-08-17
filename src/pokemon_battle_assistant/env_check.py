"""Environment diagnostics for the PBA CLI."""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class CheckItem:
    name: str
    ok: bool
    detail: str
    hint: str | None = None


@dataclass
class EnvCheckResult:
    items: list[CheckItem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(item.ok for item in self.items)

    def add(self, name: str, ok: bool, detail: str, hint: str | None = None) -> None:
        self.items.append(CheckItem(name=name, ok=ok, detail=detail, hint=hint))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "items": [item.__dict__ for item in self.items],
        }


def port_open(host: str = "127.0.0.1", port: int = 8000, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def run_env_check() -> EnvCheckResult:
    result = EnvCheckResult()

    result.add("python", True, f"{sys.executable} ({sys.version.split()[0]})")
    local_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    result.add(
        "local .venv",
        local_python.exists(),
        str(local_python) if local_python.exists() else "未找到项目 .venv/bin/python",
        "建议运行：python3.13 -m venv .venv，然后安装依赖。" if not local_python.exists() else None,
    )

    for module_name, hint in [
        ("poke_env", ".venv/bin/python -m pip install -e ~/Bian-workspace/poke-env"),
        ("websockets", ".venv/bin/python -m pip install websockets"),
    ]:
        spec = importlib.util.find_spec(module_name)
        result.add(
            f"dependency:{module_name}",
            spec is not None,
            spec.origin if spec and spec.origin else "未安装",
            hint if spec is None else None,
        )

    showdown_ok = port_open("127.0.0.1", 8000)
    result.add(
        "showdown:localhost:8000",
        showdown_ok,
        "可连接" if showdown_ok else "不可连接",
        f"请先运行 start.bat（或手动：cd {PROJECT_ROOT / 'pokemon-showdown'} && node pokemon-showdown start --no-security）" if not showdown_ok else None,
    )

    for rel_path in [
        "data/dex/showdown_db.json",
        "data/dex/translations/zh_cn_names.json",
        "data/teams/lab",
        "data/teams/generated",
    ]:
        path = PROJECT_ROOT / rel_path
        result.add(f"data:{rel_path}", path.exists(), str(path), f"缺少必要数据：{rel_path}" if not path.exists() else None)

    return result


def format_env_check(result: EnvCheckResult, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

    lines = ["# PBA Environment Check", ""]
    for item in result.items:
        icon = "✅" if item.ok else "❌"
        lines.append(f"{icon} {item.name}: {item.detail}")
        if item.hint:
            lines.append(f"   hint: {item.hint}")
    lines.append("")
    lines.append("结果：" + ("通过" if result.ok else "存在问题，请按 hint 修复。"))
    return "\n".join(lines)
