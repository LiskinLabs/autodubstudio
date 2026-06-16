@echo off
echo ====================================================
echo [AutoDubStudio] Downloading the best Local AI Models
echo ====================================================

:: Ensure Ollama saves to the project folder
set OLLAMA_MODELS=%~dp0models\ollama

if not exist "%OLLAMA_MODELS%" (
    mkdir "%OLLAMA_MODELS%"
)

echo.
echo ====================================================
echo 1/2 Downloading Qwen 2.5 14B (Best for translation, ~9GB RAM)
echo ====================================================
ollama pull qwen2.5:14b

echo.
echo ====================================================
echo 2/3 Downloading Llama 3.1 8B (Fastest & highly capable, ~4.7GB RAM)
echo ====================================================
ollama pull llama3.1:8b

echo.
echo ====================================================
echo 3/3 Downloading Gemma 4 E4B (Latest Google release!)
echo ====================================================
ollama pull gemma4:e4b

echo.
echo All models downloaded successfully into your project folder!
pause
