@echo off
chcp 936 >nul
title 宝可梦对战助手 - 启动器
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 还没安装。请先双击 setup.bat 完成一键安装。
    pause
    exit /b 1
)
if not exist "pokemon-showdown\pokemon-showdown" (
    echo [错误] 缺少对战引擎。请重新运行 setup.bat。
    pause
    exit /b 1
)

echo [1/4] 清理旧服务（自动结束占用 8000/8300 端口的进程）...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000,8300 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Write-Host ('      killed stale process PID=' + $_); Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
ping -n 3 127.0.0.1 >nul

echo [2/4] 启动对战引擎（Showdown，最小化窗口）...
start "Showdown 对战引擎（关闭此窗口=停止对战引擎）" /min cmd /k "cd /d "%~dp0pokemon-showdown" && node pokemon-showdown start --no-security"

echo      等待引擎就绪（最多 180 秒（首次启动需编译数据，较慢））...
".venv\Scripts\python.exe" scripts\wait_port.py 8000 180
if errorlevel 1 (
    echo [错误] 对战引擎启动超时。请展开任务栏的 Showdown 窗口查看报错。
    pause
    exit /b 1
)

echo [3/4] 启动助手后端（API + 网页，最小化窗口）...
start "PBA 后端（关闭此窗口=停止网页服务）" /min cmd /k "cd /d "%~dp0" && .venv\Scripts\python.exe -m pokemon_battle_assistant serve --port 8300"

echo      等待后端就绪（最多 180 秒（首次启动需编译数据，较慢））...
".venv\Scripts\python.exe" scripts\wait_port.py 8300 60
if errorlevel 1 (
    echo [错误] 后端启动超时。请展开任务栏的 PBA 后端窗口查看报错。
    pause
    exit /b 1
)

echo [4/4] 打开浏览器 ...
start "" http://127.0.0.1:8300

echo.
echo ============================================
echo    启动成功！
echo    浏览器没自动打开就手动访问：http://127.0.0.1:8300
echo    重复运行本脚本即可重启服务（自动清理旧进程，无需先关窗口）
echo    彻底停止：关闭任务栏里两个最小化的黑色窗口
echo ============================================
pause
exit /b 0
