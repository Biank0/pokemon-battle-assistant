@echo off
chcp 65001 >nul
title 宝可梦对战助手 - 一键安装
cd /d "%~dp0"

echo ============================================
echo    宝可梦对战助手 - 一键安装
echo ============================================
echo.

echo [1/5] 检查 Python ...
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (
    where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
    echo [错误] 未检测到 Python。请先安装 Python 3.10+：
    echo        https://www.python.org/downloads/
    echo        安装时务必勾选 "Add Python to PATH"
    goto :fail
)
%PY% --version

echo [2/5] 检查 Node.js ...
where node >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Node.js。请先安装 Node 18+：
    echo        https://nodejs.org/
    goto :fail
)
node --version

echo [3/5] 创建虚拟环境并安装依赖（首次需要几分钟）...
if not exist .venv (
    %PY% -m venv .venv
    if errorlevel 1 goto :fail
)
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" -m pip install -e . -q
if errorlevel 1 goto :fail

echo [4/5] 初始化对战引擎 Pokemon Showdown ...
if exist "pokemon-showdown\pokemon-showdown" (
    echo 对战引擎已存在，跳过。
) else (
    git submodule update --init --recursive --depth 1 >nul 2>nul
    if not exist "pokemon-showdown\pokemon-showdown" (
        echo 直连 GitHub 失败，尝试镜像加速 ...
        git -c url."https://gh-proxy.com/https://github.com/".insteadOf."https://github.com/" submodule update --init --recursive --depth 1
        if errorlevel 1 (
            echo [错误] 对战引擎下载失败，请检查网络后重新运行本脚本
            goto :fail
        )
    )
)

echo [5/5] 生成配置文件 .env ...
if not exist .env (
    copy .env.example .env >nul
    echo 已生成 .env：默认 mock 模式无需 Key 即可使用。
    echo            想启用真实 AI，请编辑 .env 填入 DeepSeek 密钥（见 README）。
) else (
    echo .env 已存在，跳过。
)

echo.
echo ============================================
echo    安装完成！双击 start.bat 启动助手
echo ============================================
pause
exit /b 0

:fail
echo.
echo [安装失败] 请把上方错误信息反馈给开发者
pause
exit /b 1
