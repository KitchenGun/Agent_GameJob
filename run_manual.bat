@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo.
echo ========================================
echo  GameJobAgent - Manual Run
echo ========================================
echo.
echo  1. Full pipeline (crawl + match + notify)
echo  2. Crawl only   (collect job postings)
echo  3. Match only   (match + Discord notify)
echo  4. Exit
echo.
set /p choice="Select (1-4): "

if "%choice%"=="1" goto FULL
if "%choice%"=="2" goto CRAWL
if "%choice%"=="3" goto MATCH
if "%choice%"=="4" goto END
echo Invalid selection.
goto END

:FULL
echo.
echo [Running] Full pipeline...
echo.
py -3 main.py
goto DONE

:CRAWL
echo.
echo [Running] Crawl only...
echo.
py -3 main.py --crawl-only
goto DONE

:MATCH
echo.
echo [Running] Match + Discord notify...
echo.
py -3 main.py --match-only
goto DONE

:DONE
echo.
echo ========================================
echo  Done.
echo ========================================

:END
pause
