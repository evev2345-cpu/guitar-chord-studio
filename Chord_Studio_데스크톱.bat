@echo off
chcp 65001 > nul
title Chord Studio Pro - 데스크톱 프로그램
cd /d "E:\GUITAR"

echo.
echo =======================================================================
echo          🎸 Chord Studio Pro - 초고속 네이티브 데스크톱 프로그램 실행
echo =======================================================================
echo.
echo  * 웹 브라우저/터널 없이 내 컴퓨터 GPU 및 하드웨어 가속으로 즉시 실행됩니다.
echo  * 대용량 영상 업로드 렉 0초, 초고속 실시간 운지 및 지판 추적을 지원합니다.
echo.

start "" ".venv-audio-model\Scripts\pythonw.exe" desktop_app/main.py

exit
