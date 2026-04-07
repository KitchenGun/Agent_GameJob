@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo.
echo ========================================
echo  GameJobAgent - Full Pipeline
echo ========================================
echo.
echo [Running] Full pipeline (crawl + match + notify)...
echo.
call venv\Scripts\activate
python main.py

echo.
echo ========================================
echo  Done.
echo ========================================
pause
