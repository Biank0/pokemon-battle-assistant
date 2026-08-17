#!/usr/bin/env bash
# 宝可梦对战助手 - 启动器（macOS / Linux）
set -e
cd "$(dirname "$0")"

[ -x .venv/bin/python ] || { echo "[错误] 还没安装，请先运行 ./setup.sh"; exit 1; }
[ -f pokemon-showdown/pokemon-showdown ] || { echo "[错误] 缺少对战引擎，请重新运行 ./setup.sh"; exit 1; }

echo "[1/3] 启动对战引擎（Showdown）..."
( cd pokemon-showdown && node pokemon-showdown start --no-security ) &
SHOWDOWN_PID=$!

echo "      等待引擎就绪..."
.venv/bin/python scripts/wait_port.py 8000 180 || { echo "[错误] 引擎启动超时"; exit 1; }

echo "[2/3] 启动助手后端（API + 网页）..."
.venv/bin/python -m pokemon_battle_assistant serve --port 8300 &
API_PID=$!
.venv/bin/python scripts/wait_port.py 8300 60 || { echo "[错误] 后端启动超时"; exit 1; }

echo "[3/3] 打开浏览器 ..."
( command -v open >/dev/null && open http://127.0.0.1:8300 ) || xdg-open http://127.0.0.1:8300 2>/dev/null || true

echo "============================================"
echo "   启动成功！手动访问：http://127.0.0.1:8300"
echo "   停止服务：Ctrl+C"
echo "============================================"
trap 'kill $SHOWDOWN_PID $API_PID 2>/dev/null' EXIT
wait
