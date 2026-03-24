@echo off
setlocal

echo Stopping DeepAnalyze Tiramisu
echo ========================================

set BACKEND_PORT=8200
set TIRAMISU_PORT=3000

echo Releasing ports...
call :KillPort %BACKEND_PORT%
call :KillPort %TIRAMISU_PORT%

echo.
echo System stopped successfully.
echo.
echo Log files are kept in the logs\ directory.
echo To restart: run start.bat
goto :eof

:KillPort
set port=%1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":"%port% ^| findstr "LISTENING"') do (
    echo   Releasing port %port% [PID: %%a]...
    taskkill /F /PID %%a >nul 2>&1
)
goto :eof
