"""Showdown 服务器生命周期管理（用户零手工安装/启动）。

策略：探活 8000 端口 → 已在跑直接复用；没跑则自动 spawn
`node pokemon-showdown start --no-security`（子进程，日志重定向到
data/lab/showdown.log），等 websocket 就绪。会话结束不杀（下次复用）。
"""
from __future__ import annotations

import json
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SHOWDOWN_DIR = ROOT / "pokemon-showdown"
LOG_PATH = ROOT / "data" / "lab" / "showdown.log"

PORT = 8000
START_TIMEOUT_S = 30.0

_proc: subprocess.Popen | None = None  # 本进程拉起的实例（防 GC）


def is_alive(port: int = PORT) -> bool:
    """端口探活（showdown 起来后 8000 必然监听）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _spawn(port: int) -> subprocess.Popen:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_f = open(LOG_PATH, "ab")
    # Windows: node.exe；start 参数与 poke-env 官方文档一致（--no-security 免登录）
    return subprocess.Popen(
        ["node", "pokemon-showdown", "start", "--no-security"],
        cwd=str(SHOWDOWN_DIR), stdout=log_f, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )


def ensure_server(port: int = PORT, log=print) -> None:
    """确保 showdown 在跑（幂等：已在跑直接返回）。失败抛 RuntimeError。"""
    global _proc
    if is_alive(port):
        log("[lab] Showdown 服务器已在运行，复用")
        return
    if not (SHOWDOWN_DIR / "pokemon-showdown").exists():
        raise RuntimeError(f"Showdown 引擎不存在: {SHOWDOWN_DIR}（请先运行 setup）")
    log(f"[lab] 启动 Showdown 服务器（端口 {port}）...")
    _proc = _spawn(port)
    t0 = time.time()
    while time.time() - t0 < START_TIMEOUT_S:
        if _proc.poll() is not None:
            raise RuntimeError(
                f"Showdown 进程启动即退出（code={_proc.returncode}），日志: {LOG_PATH}")
        if is_alive(port):
            log(f"[lab] Showdown 就绪（{time.time() - t0:.1f}s）")
            return
        time.sleep(0.5)
    raise RuntimeError(f"Showdown {START_TIMEOUT_S}s 内未就绪，日志: {LOG_PATH}")


def server_info() -> dict:
    """服务器状态（给 API/前端用）。"""
    return {"port": PORT, "alive": is_alive(), "log_path": str(LOG_PATH)}
