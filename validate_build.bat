@echo off
echo [1] Проверка синтаксиса и импортов...
uv run ruff check .
if %errorlevel% neq 0 exit /b %errorlevel%

echo Все проверки пройдены!
exit /b 0
