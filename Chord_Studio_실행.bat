@echo off
title Guitar Chord Studio
chcp 65001 >nul
cd /d "e:\GUITAR"
powershell -NoProfile -ExecutionPolicy Bypass -File "e:\GUITAR\run_local_studio.ps1"
pause
