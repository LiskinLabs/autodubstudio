import httpx

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "gemma4:e4b"  # Fallback if specific model is not found

import asyncio


async def call_ollama(
    prompt: str, system_prompt: str = "", model: str = DEFAULT_MODEL, retries: int = 3
) -> str:
    """Helper to call Ollama asynchronously with retries"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {"model": model, "messages": messages, "stream": False}

    for attempt in range(retries):
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(OLLAMA_URL, json=payload, timeout=60.0)
                resp.raise_for_status()
                return resp.json().get("message", {}).get("content", "")
            except httpx.TimeoutException:
                print(f"[Ollama] Таймаут (попытка {attempt + 1}/{retries}).")
            except Exception as e:
                print(f"[Ollama] Ошибка: {e} (попытка {attempt + 1}/{retries}).")
        await asyncio.sleep(2)

    raise RuntimeError(f"Критический сбой Ollama после {retries} попыток.")


async def smart_cleanup_transcript(dirty_transcript: str) -> str:
    """Cleans up whisper transcript removing filler words and stuttering."""
    system = "You are an expert transcript editor. Clean the text by removing filler words (um, uh), stuttering, and fixing minor grammar. DO NOT summarize, just clean. Return ONLY the cleaned text."
    prompt = f"Clean this transcript:\n\n{dirty_transcript}"
    return await call_ollama(prompt, system)


async def smart_lipsync_translate(
    text: str, target_lang: str = "ru", original_length_chars: int = 0
) -> str:
    """Translates text while trying to match the original spoken length for lip-sync."""
    system = f"You are a professional video dubbing translator. Translate the text to {target_lang}. CRITICAL: You must try to make the translation exactly {original_length_chars} characters long so that the lip-sync timing matches the original video perfectly. Return ONLY the translation."
    prompt = f"Original text:\n{text}"
    return await call_ollama(prompt, system)


async def analyze_emotions(text: str) -> str:
    """Analyzes text to provide XTTS emotion tags."""
    system = "You are an emotion director for TTS. Read the text and output a JSON array of emotions that should be applied. Valid emotions: [Happy, Sad, Angry, Whisper, Shouting, Normal]. ONLY output the JSON array."
    prompt = f"Text:\n{text}"
    return await call_ollama(prompt, system)
