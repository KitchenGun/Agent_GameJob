@echo off
chcp 65001 > nul

set "PROJECT_DIR=%~dp0"
set "TASK_NAME=GameJobAgent"
set "BATCH_CMD=%PROJECT_DIR%run_scheduled.bat"

echo.
echo ========================================
echo  GameJobAgent - Task Scheduler Setup
echo ========================================
echo.
echo   Project path : %PROJECT_DIR%
echo   Batch file   : run_scheduled.bat
echo   Schedule     : Every 6 hours (starting 09:00)
echo.

REM 기존 작업 제거 (존재하면)
echo [INFO] Removing existing task (if any)...
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

REM 새 작업 등록
echo [INFO] Registering new scheduled task...
schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%BATCH_CMD%\"" ^
  /sc HOURLY ^
  /mo 6 ^
  /st 09:00 ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo  [OK] Task registered successfully!
    echo ========================================
    echo.
    echo   - Task name : %TASK_NAME%
    echo   - Execute   : run_scheduled.bat (venv + full pipeline)
    echo   - Interval  : every 6 hours
    echo   - Schedule  : 09:00, 15:00, 21:00, 03:00
    echo   - Logging   : logs\scheduled_*.log
    echo.
    echo To verify : schtasks /query /tn "%TASK_NAME%"
    echo To run now: schtasks /run /tn "%TASK_NAME%"
    echo To delete : schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo.
    echo [ERROR] Registration failed. Try running as Administrator.
)

pause
