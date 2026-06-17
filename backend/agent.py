import httpx
import json

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "gemma4:e4b" # Fallback if specific model is not found

async def call_ollama(prompt: str, system_prompt: str = "", model: str = DEFAULT_MODEL) -> str:
    """Helper to call Ollama synchronously or asynchronously"""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": False
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(OLLAMA_URL, json=payload, timeout=60.0)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content", "")
            else:
                print(f"[Ollama Error] Status {resp.status_code}: {resp.text}")
                return ""
        except Exception as e:
            print(f"[Ollama Exception] {e}")
            return ""

async def smart_cleanup_transcript(dirty_transcript: str) -> str:
    """Cleans up whisper transcript removing filler words and stuttering."""
    system = "You are an expert transcript editor. Clean the text by removing filler words (um, uh), stuttering, and fixing minor grammar. DO NOT summarize, just clean. Return ONLY the cleaned text."
    prompt = f"Clean this transcript:\n\n{dirty_transcript}"
    return await call_ollama(prompt, system)

async def smart_lipsync_translate(text: str, target_lang: str = "ru", original_length_chars: int = 0) -> str:
    """Translates text while trying to match the original spoken length for lip-sync."""
    system = f"You are a professional video dubbing translator. Translate the text to {target_lang}. CRITICAL: You must try to make the translation exactly {original_length_chars} characters long so that the lip-sync timing matches the original video perfectly. Return ONLY the translation."
    prompt = f"Original text:\n{text}"
    return await call_ollama(prompt, system)

async def analyze_emotions(text: str) -> str:
    """Analyzes text to provide XTTS emotion tags."""
    system = "You are an emotion director for TTS. Read the text and output a JSON array of emotions that should be applied. Valid emotions: [Happy, Sad, Angry, Whisper, Shouting, Normal]. ONLY output the JSON array."
    prompt = f"Text:\n{text}"
    return await call_ollama(prompt, system)
