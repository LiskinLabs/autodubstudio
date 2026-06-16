@echo off
echo ====================================================
echo [AutoDubStudio] Downloading Gemma4 AI Model
echo ====================================================

:: Ensure Ollama saves to the project folder
set OLLAMA_MODELS=%~dp0models\ollama

if not exist "%OLLAMA_MODELS%" (
    mkdir "%OLLAMA_MODELS%"
)

echo.
echo ====================================================
echo Downloading Gemma 4 E4B (Google, 9B, best quality)
echo ====================================================
ollama pull gemma4:e4b

echo.
echo Done! Gemma4 is ready for translation.
pause
