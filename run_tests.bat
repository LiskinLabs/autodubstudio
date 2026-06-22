@echo off
echo AutoDub Studio - Engine Test Suite
echo Running 26 configs... this will take ~30-60 min
echo Report will be at: downloads\test_reports\test_report_*.json
echo.
cd /d C:\Users\silvestr.liskin\Desktop\AutoDubStudio
.venv\Scripts\python.exe -u test_all_engines.py
echo.
echo ============================================
echo Tests complete! Check test_output.log
echo ============================================
