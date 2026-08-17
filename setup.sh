#!/usr/bin/env bash
# 宝可梦对战助手 - 一键安装（macOS / Linux）
set -e
cd "$(dirname "$0")"

echo "============================================"
echo "   宝可梦对战助手 - 一键安装"
echo "============================================"

echo "[1/5] 检查 Python ..."
command -v python3 >/dev/null || { echo "[错误] 未检测到 python3，请先安装 Python 3.10+"; exit 1; }
python3 --version

echo "[2/5] 检查 Node.js ..."
command -v node >/dev/null || { echo "[错误] 未检测到 node，请先安装 Node 18+（https://nodejs.org）"; exit 1; }
node --version

echo "[3/5] 创建虚拟环境并安装依赖 ..."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/python -m pip install -e . -q

echo "[4/5] 初始化对战引擎 Pokemon Showdown ..."
if [ -f pokemon-showdown/pokemon-showdown ]; then
    echo "对战引擎已存在，跳过。"
else
    git submodule update --init --recursive --depth 1 >/dev/null 2>&1 || \
    git -c url."https://gh-proxy.com/https://github.com/".insteadOf."https://github.com/" \
        submodule update --init --recursive --depth 1
fi

echo "[5/5] 生成配置文件 .env ..."
[ -f .env ] || { cp .env.example .env; echo "已生成 .env：默认 mock 模式无需 Key；启用真实 AI 请填入 DeepSeek 密钥（见 README）。"; }

echo "============================================"
echo "   安装完成！运行 ./start.sh 启动助手"
echo "============================================"
