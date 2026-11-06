@echo off
title Guitar Chord Studio Shutdown
chcp 65001 >nul
cd /d "%~dp0"
echo [Chord Studio 서버 종료 중...]
taskkill /F /IM cloudflared.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8766') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo.
echo ======================================================
echo   Chord Studio 서버와 터널이 모두 종료되었습니다.
echo ======================================================
echo.
timeout /t 3
