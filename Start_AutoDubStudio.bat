@echo off
chcp 65001 >nul
color 0B
echo ===================================================
echo     AutoDubStudio - Portable Edition
echo ===================================================
echo.
echo Запуск сервера (Backend) и интерфейса (Frontend)...
echo.

cd /d "%~dp0"

:: Kill any existing stray processes just in case
taskkill /F /IM "llama-server.exe" 2>nul

:: Start backend in the background
echo Запуск Backend-сервера...
cd backend
start /B "" "..\.venv\Scripts\python.exe" "main.py"
cd ..

:: Give the server a few seconds to boot up
timeout /t 3 >nul

:: Start frontend
cd gui
echo Открытие браузера...
start "" "http://localhost:5173"
echo Запуск Frontend...
call npm run dev
