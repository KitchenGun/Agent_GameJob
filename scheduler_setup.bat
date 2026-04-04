@echo off
chcp 65001 > nul

echo [GameJobAgent] Registering Windows Task Scheduler...
echo Project path: %~dp0

set "PROJECT_DIR=%~dp0"
set "PS_TEMP=%PROJECT_DIR%_sched_temp.ps1"
set "BAT_FILE=%PROJECT_DIR%run_agent.bat"

(
  echo $action  = New-ScheduledTaskAction -Execute '"%BAT_FILE%"' -WorkingDirectory '"%PROJECT_DIR%"'
  echo $trigger = New-ScheduledTaskTrigger -Once -At "09:00" -RepetitionInterval ^(New-TimeSpan -Hours 6^) -RepetitionDuration ^(New-TimeSpan -Days 3650^)
  echo $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ^(New-TimeSpan -Hours 2^) -RestartCount 3 -RestartInterval ^(New-TimeSpan -Minutes 10^) -WakeToRun:$true -DisallowStartIfOnBatteries:$false -StopIfGoingOnBatteries:$false
  echo Register-ScheduledTask -TaskName "GameJobAgent" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force
) > "%PS_TEMP%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_TEMP%"

if %errorlevel% equ 0 (
    echo.
    echo [OK] Task registered successfully!
    echo   - Task name : GameJobAgent
    echo   - Interval  : every 6 hours ^(starting 09:00^)
    echo   - Script    : %BAT_FILE%
) else (
    echo.
    echo [ERROR] Registration failed. Please run as Administrator.
)

del "%PS_TEMP%" > nul 2>&1
pause
