@echo off
chcp 65001 > nul

set "PROJECT_DIR=%~dp0"
set "BAT_FILE=%PROJECT_DIR%run_agent.bat"
set "TASK_NAME=GameJobAgent"

echo [GameJobAgent] Registering scheduled task via schtasks...
echo Project path: %PROJECT_DIR%

schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "\"%BAT_FILE%\"" ^
  /sc HOURLY ^
  /mo 6 ^
  /st 09:00 ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo [OK] Task registered successfully!
    echo   - Task name : %TASK_NAME%
    echo   - Interval  : every 6 hours ^(starting 09:00^)
    echo   - Script    : %BAT_FILE%
    echo.
    echo To verify: schtasks /query /tn "%TASK_NAME%"
    echo To delete: schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo.
    echo [ERROR] Registration failed. Try running as Administrator.
)

pause
