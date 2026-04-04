@echo off
chcp 65001 > nul
cd /d "%~dp0"
if not exist logs mkdir logs
py -3 main.py >> logs\agent_%date:~0,4%%date:~5,2%%date:~8,2%.log 2>&1
