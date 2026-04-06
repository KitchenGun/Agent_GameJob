@echo off
chcp 65001 > nul

set "PROJECT_DIR=%~dp0"
set "TASK_NAME=GameJobAgent"
set "PY_CMD=py -3 \"%PROJECT_DIR%main.py\""

echo [GameJobAgent] Registering scheduled task via schtasks...
echo Project path: %PROJECT_DIR%

schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "%PY_CMD%" ^
  /sc HOURLY ^
  /mo 6 ^
  /st 09:00 ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo [OK] Task registered successfully!
    echo   - Task name : %TASK_NAME%
    echo   - Interval  : every 6 hours ^(starting 09:00^)
    echo   - Script    : %PY_CMD%
    echo.
    echo To verify: schtasks /query /tn "%TASK_NAME%"
    echo To delete: schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo.
    echo [ERROR] Registration failed. Try running as Administrator.
)

pause
