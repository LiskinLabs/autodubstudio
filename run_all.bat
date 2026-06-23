@echo off
set PYTHONIOENCODING=utf-8
echo Running video 1...
uv run python -u run_test.py
echo Running videos 2 and 3...
uv run python -u run_remaining.py
echo All done!
