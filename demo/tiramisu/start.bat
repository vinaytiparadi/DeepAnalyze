@echo off
setlocal
set PYTHONIOENCODING=utf-8

echo Starting DeepAnalyze Tiramisu
echo ========================================

:: Ensure logs directory exists
if not exist logs mkdir logs

:: Define ports
set BACKEND_PORT=8200
set TIRAMISU_PORT=3000

:: Kill existing processes on ports
call :KillPort %BACKEND_PORT%
call :KillPort %TIRAMISU_PORT%

echo Cleanup completed.
echo.

:: Start backend API
echo Starting backend API...
start /B "Tiramisu Backend" cmd /c "python backend.py > logs\backend.log 2>&1"
echo Backend started in background.
echo API running on: http://localhost:%BACKEND_PORT%

:: Wait for backend to initialize
timeout /t 3 /nobreak >nul

:: Start frontend
echo.
echo Starting Tiramisu frontend...
start /B "Tiramisu Frontend" cmd /c "npm run dev -- -p %TIRAMISU_PORT% > logs\tiramisu.log 2>&1"
echo Frontend started in background.
echo Frontend running on: http://localhost:%TIRAMISU_PORT%

echo.
echo All services started successfully.
echo.
echo Service URLs:
echo   Backend API: http://localhost:%BACKEND_PORT%
echo   Frontend:    http://localhost:%TIRAMISU_PORT%
echo.
echo Log files:
echo   Backend:  logs\backend.log
echo   Frontend: logs\tiramisu.log
echo.
echo Stop services: run stop.bat
goto :eof

:KillPort
set port=%1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":"%port% ^| findstr "LISTENING"') do (
    echo Port %port% is in use by PID %%a. Killing...
    taskkill /F /PID %%a >nul 2>&1
)
goto :eof
