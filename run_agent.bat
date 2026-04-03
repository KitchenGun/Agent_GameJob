@echo off
cd /d "%~dp0"
call venv\Scripts\activate
if not exist logs mkdir logs
python main.py >> logs\agent_%date:~0,4%%date:~5,2%%date:~8,2%.log 2>&1
