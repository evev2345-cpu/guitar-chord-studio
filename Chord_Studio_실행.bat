@echo off
title Guitar Chord Studio
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_local_studio.ps1"
pause
