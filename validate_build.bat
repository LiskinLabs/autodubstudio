@echo off
echo [1] Проверка синтаксиса и импортов...
uv run ruff check .
if %errorlevel% neq 0 exit /b %errorlevel%

echo [2] Тестовый запуск пайплайна...
uv run python test_pipeline.py
if %errorlevel% neq 0 exit /b %errorlevel%
