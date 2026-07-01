@echo off
chcp 65001 >nul
color 0B
echo ===================================================
echo     AutoDubStudio - Portable Edition
echo ===================================================
echo.
echo Starting backend + frontend...
echo.

cd /d "%~dp0"

:: Kill any existing stray processes
taskkill /F /IM "llama-server.exe" 2>nul

:: Auto-detect GitHub token for error reporting
for /f "tokens=*" %%i in ('gh auth token 2^>nul') do set GITHUB_TOKEN=%%i
if defined GITHUB_TOKEN (
    echo [OK] GitHub token detected — error reporting enabled
) else (
    echo [WARN] No GitHub token found — error reporting disabled
)

:: Check if .venv is valid
".venv\Scripts\python.exe" --version >nul 2>&1
if %errorlevel% equ 0 (
    echo Starting Backend server from .venv...
    cd backend
    start /B "" "..\.venv\Scripts\python.exe" "main.py"
    cd ..
) else (
    echo [WARN] .venv is broken or missing. Falling back to uv run...
    start /B "" uv run python backend\main.py
)

:: Wait for server
timeout /t 3 >nul

:: Start frontend
cd gui
echo Opening browser...
start "" "http://localhost:1435"
echo Starting Frontend...
call npm run dev
