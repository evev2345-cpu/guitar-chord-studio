@echo off
chcp 65001 > nul
title 기타 지판 라벨러 실행기
cd /d "%~dp0"

echo ========================================================
echo   🎸 기타 지판 4-Point 라벨러를 실행합니다...
echo   잠시 후 웹 브라우저(Chrome/Edge)가 자동으로 열립니다.
echo ========================================================
echo.

python web_labeler.py

pause
