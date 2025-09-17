@echo off
REM Device Management System - One-Click Startup Script (Windows)
REM Author: CodeBuddy Code
REM Description: Starts both backend and frontend services

setlocal enabledelayedexpansion

REM Get project root directory
set "PROJECT_ROOT=%~dp0"
set "BACKEND_DIR=%PROJECT_ROOT%backend"
set "FRONTEND_DIR=%PROJECT_ROOT%frontend"

REM PID files for process management
set "BACKEND_PID_FILE=%PROJECT_ROOT%.backend.pid"
set "FRONTEND_PID_FILE=%PROJECT_ROOT%.frontend.pid"

REM Colors (limited in Windows CMD)
set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

REM Parse command line arguments
set "COMMAND=%1"
if "%COMMAND%"=="" set "COMMAND=start"

goto :%COMMAND% 2>nul || goto :usage

:start
echo %BLUE%[%date% %time%]%NC% 🚀 Starting Device Management System...
echo ==================================================

call :check_dependencies
if errorlevel 1 exit /b 1

call :stop_services

REM Install dependencies if needed
if not exist "%BACKEND_DIR%\.deps_installed" (
    call :install_backend_deps
    echo. > "%BACKEND_DIR%\.deps_installed"
)

if not exist "%FRONTEND_DIR%\node_modules" (
    call :install_frontend_deps
)

REM Start services
call :start_backend
if errorlevel 1 (
    call :stop_services
    exit /b 1
)

call :start_frontend
if errorlevel 1 (
    call :stop_services
    exit /b 1
)

call :show_status
echo %GREEN%[%date% %time%] ✓%NC% 🎉 Device Management System started successfully!
echo %BLUE%[%date% %time%]%NC% Press Ctrl+C to stop all services

REM Keep script running
:monitor_loop
timeout /t 10 /nobreak >nul
REM Check if processes are still running (simplified for Windows)
goto :monitor_loop

:stop
call :stop_services
goto :eof

:restart
call :stop_services
timeout /t 2 /nobreak >nul
call :start
goto :eof

:status
call :show_status
goto :eof

:logs
if "%2"=="backend" (
    if exist "%PROJECT_ROOT%backend.log" (
        type "%PROJECT_ROOT%backend.log"
    ) else (
        echo %RED%Backend log file not found%NC%
    )
) else if "%2"=="frontend" (
    if exist "%PROJECT_ROOT%frontend.log" (
        type "%PROJECT_ROOT%frontend.log"
    ) else (
        echo %RED%Frontend log file not found%NC%
    )
) else (
    echo %RED%Invalid service. Use 'backend' or 'frontend'%NC%
)
goto :eof

:install
call :check_dependencies
call :install_backend_deps
call :install_frontend_deps
echo %GREEN%All dependencies installed%NC%
goto :eof

:usage
echo Usage: %0 {start^|stop^|restart^|status^|logs^|install}
echo.
echo Commands:
echo   start    - Start both backend and frontend services
echo   stop     - Stop all services
echo   restart  - Restart all services
echo   status   - Show service status
echo   logs     - Show logs (backend^|frontend)
echo   install  - Install all dependencies
echo.
echo Examples:
echo   %0 start
echo   %0 logs backend
echo   %0 logs frontend
exit /b 1

REM Functions

:check_dependencies
echo %BLUE%[%date% %time%]%NC% Checking dependencies...

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo %RED%Python is not installed%NC%
    exit /b 1
)

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo %RED%Node.js is not installed%NC%
    exit /b 1
)

REM Check npm
npm --version >nul 2>&1
if errorlevel 1 (
    echo %RED%npm is not installed%NC%
    exit /b 1
)

REM Check ADB (optional)
adb version >nul 2>&1
if errorlevel 1 (
    echo %YELLOW%ADB is not installed - device detection may not work%NC%
) else (
    echo %GREEN%ADB is available%NC%
)

echo %GREEN%Dependencies check completed%NC%
exit /b 0

:install_backend_deps
echo %BLUE%[%date% %time%]%NC% Installing backend dependencies...
cd /d "%BACKEND_DIR%"

if not exist "requirements.txt" (
    echo %RED%requirements.txt not found in backend directory%NC%
    exit /b 1
)

pip install -r requirements.txt
echo %GREEN%Backend dependencies installed%NC%
exit /b 0

:install_frontend_deps
echo %BLUE%[%date% %time%]%NC% Installing frontend dependencies...
cd /d "%FRONTEND_DIR%"

if not exist "package.json" (
    echo %RED%package.json not found in frontend directory%NC%
    exit /b 1
)

npm install
echo %GREEN%Frontend dependencies installed%NC%
exit /b 0

:start_backend
echo %BLUE%[%date% %time%]%NC% Starting backend service...
cd /d "%BACKEND_DIR%"

REM Check if port is in use (simplified check)
netstat -an | find "8001" | find "LISTENING" >nul
if not errorlevel 1 (
    echo %RED%Port 8001 is already in use%NC%
    exit /b 1
)

REM Start backend
start /b python start.py > "%PROJECT_ROOT%backend.log" 2>&1

REM Wait for backend to start (simplified)
timeout /t 10 /nobreak >nul

REM Simple check if backend is responding
curl -s http://localhost:8001/docs >nul 2>&1
if errorlevel 1 (
    echo %RED%Backend failed to start%NC%
    exit /b 1
)

echo %GREEN%Backend started successfully%NC%
exit /b 0

:start_frontend
echo %BLUE%[%date% %time%]%NC% Starting frontend service...
cd /d "%FRONTEND_DIR%"

REM Check if port is in use
netstat -an | find "5173" | find "LISTENING" >nul
if not errorlevel 1 (
    echo %RED%Port 5173 is already in use%NC%
    exit /b 1
)

REM Start frontend
start /b npm run dev > "%PROJECT_ROOT%frontend.log" 2>&1

REM Wait for frontend to start
timeout /t 15 /nobreak >nul

REM Simple check if frontend is responding
curl -s -I http://localhost:5173 >nul 2>&1
if errorlevel 1 (
    echo %RED%Frontend failed to start%NC%
    exit /b 1
)

echo %GREEN%Frontend started successfully%NC%
exit /b 0

:stop_services
echo %BLUE%[%date% %time%]%NC% Stopping Device Management System services...

REM Kill processes on ports (Windows method)
for /f "tokens=5" %%a in ('netstat -aon ^| find "8001" ^| find "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -aon ^| find "5173" ^| find "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

REM Clean up PID files
if exist "%BACKEND_PID_FILE%" del "%BACKEND_PID_FILE%"
if exist "%FRONTEND_PID_FILE%" del "%FRONTEND_PID_FILE%"

echo %GREEN%All services stopped%NC%
exit /b 0

:show_status
echo.
echo %BLUE%=== Device Management System Status ===%NC%

REM Check backend
netstat -an | find "8001" | find "LISTENING" >nul
if not errorlevel 1 (
    echo %GREEN%Backend: Running on http://localhost:8001%NC%
    echo %BLUE%  - API Documentation: http://localhost:8001/docs%NC%
    echo %BLUE%  - API Base URL: http://localhost:8001/api%NC%
) else (
    echo %RED%Backend: Not running%NC%
)

REM Check frontend
netstat -an | find "5173" | find "LISTENING" >nul
if not errorlevel 1 (
    echo %GREEN%Frontend: Running on http://localhost:5173%NC%
    echo %BLUE%  - Web Interface: http://localhost:5173%NC%
) else (
    echo %RED%Frontend: Not running%NC%
)

echo.
echo %BLUE%Default Admin Credentials:%NC%
echo %BLUE%  Username: admin%NC%
echo %BLUE%  Password: admin123%NC%
echo.
exit /b 0