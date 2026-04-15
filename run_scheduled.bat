@echo off
chcp 65001 > nul
cd /d "%~dp0"

REM ============================================
REM  GameJobAgent - Scheduled Auto Run
REM  (스케줄러 전용: pause 없음, 로그 파일 기록)
REM ============================================

REM 로그 디렉토리 생성
if not exist "logs" mkdir logs

REM 로그 파일명 (날짜_시간)
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set "DATESTAMP=%%a%%b%%c"
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set "TIMESTAMP=%%a%%b"
set "LOGFILE=logs\scheduled_%DATESTAMP%_%TIMESTAMP%.log"

echo [%date% %time%] ======================================== >> "%LOGFILE%"
echo [%date% %time%] GameJobAgent - Scheduled Execution Start >> "%LOGFILE%"
echo [%date% %time%] ======================================== >> "%LOGFILE%"

REM venv 활성화 후 전체 파이프라인 실행
call venv\Scripts\activate
python main.py >> "%LOGFILE%" 2>&1

if %errorlevel% equ 0 (
    echo [%date% %time%] [OK] Pipeline completed successfully >> "%LOGFILE%"
) else (
    echo [%date% %time%] [ERROR] Pipeline failed with code %errorlevel% >> "%LOGFILE%"
)

echo [%date% %time%] ======================================== >> "%LOGFILE%"
echo [%date% %time%] Execution End >> "%LOGFILE%"
echo [%date% %time%] ======================================== >> "%LOGFILE%"
