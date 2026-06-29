@echo off
echo ====================================================
echo [AutoDubStudio] Starting Local Ollama AI Server...
echo ====================================================

:: Set the models directory to be inside the project folder
set OLLAMA_MODELS=%~dp0models\ollama

if not exist "%OLLAMA_MODELS%" (
    echo Creating models directory at: %OLLAMA_MODELS%
    mkdir "%OLLAMA_MODELS%"
)

echo.
echo Models will be saved to: %OLLAMA_MODELS%
echo The server is running on http://127.0.0.1:11434
echo Keep this window open while using AutoDubStudio.
echo.

ollama serve
