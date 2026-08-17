"""等待端口就绪的小工具：start 脚本用它确认服务启动完成。

用法：python wait_port.py <端口> [超时秒数]
"""

from __future__ import annotations

import socket
import sys
import time


def wait_port(port: int, timeout: int = 60) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return 0
        except OSError:
            time.sleep(1)
    return 1


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    sys.exit(wait_port(port, timeout))
