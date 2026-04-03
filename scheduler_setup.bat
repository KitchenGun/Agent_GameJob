@echo off
:: Windows 작업 스케줄러 등록 배치 (관리자 권한으로 실행)
:: 게임 프로그래머 채용 매칭 에이전트 - 6시간마다 자동 실행

set PROJECT_DIR=%~dp0
set BAT_FILE=%PROJECT_DIR%run_agent.bat

echo [GameJobAgent] 작업 스케줄러 등록 중...
echo 프로젝트 경로: %PROJECT_DIR%

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$action = New-ScheduledTaskAction -Execute '%BAT_FILE%' -WorkingDirectory '%PROJECT_DIR%';" ^
  "$trigger = New-ScheduledTaskTrigger -Once -At '09:00' -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration (New-TimeSpan -Days 3650);" ^
  "Register-ScheduledTask -TaskName 'GameJobAgent' -Action $action -Trigger $trigger -Description '게임 프로그래머 채용 매칭 에이전트 (6시간 주기)' -Force"

if %errorlevel% equ 0 (
    echo [성공] 작업 스케줄러 등록 완료!
    echo   - 작업 이름: GameJobAgent
    echo   - 실행 주기: 6시간마다 (매일 09:00 시작)
    echo   - 실행 파일: %BAT_FILE%
) else (
    echo [오류] 등록 실패. 관리자 권한으로 다시 실행하세요.
)

pause
