@echo off
chcp 65001 > nul
title Chord Studio Pro
cd /d "E:\GUITAR"

start "" "E:\GUITAR\.venv-audio-model\Scripts\pythonw.exe" "E:\GUITAR\desktop_app\main.py"
exit
