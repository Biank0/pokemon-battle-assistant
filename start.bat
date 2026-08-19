@echo off
chcp 65001 >nul
title Pokemon Battle Assistant - Backend
cd /d "%~dp0"

echo [1/3] Cleaning up old services on port 8300 ...
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 8300 -State Listen -ErrorAction SilentlyContinue; if ($c) { $c | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }; Write-Output 'killed stale process' } else { Write-Output 'none' }"
timeout /t 2 /nobreak >nul

echo [2/3] Starting backend (API + frontend) ...
start "PBA Backend" cmd /k ".venv\Scripts\python.exe -m uvicorn pokemon_battle_assistant.api.app:app --app-dir src --host 127.0.0.1 --port 8300"

echo [3/3] Waiting for service ...
timeout /t 5 /nobreak >nul
start http://127.0.0.1:8300

echo.
echo Done. Browser should open at http://127.0.0.1:8300
echo Keep the "PBA Backend" window open while using the app.
pause
