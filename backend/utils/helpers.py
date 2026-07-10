import os
import re
import subprocess
import sys
import psutil
import requests
from urllib.parse import urlparse

try:
    import langdetect as _langdetect
    from langdetect import DetectorFactory
    DetectorFactory.seed = 0
    _HAS_LANGDETECT = True
except ImportError:
    _HAS_LANGDETECT = False

_SCRIPT_CHARS = {
    "es": set("ñ"),
    "ru": set("абвгдеёжзийклмнопрстуфхцчшщъыьэюя"),
    "tr": set("ğüşöçIİ"),
    "ar": set("ابتثجحخدذرزسشصضطظعغفقكلمنهوي"),
    "zh": set("的一是不了在人有我他这个们中来上大为和国地到以说时起作里"),
    "ja": set("あいうえおかきくけこさしすせそ"),
    "ko": set("가나다라마바사아자차카타파하"),
    "hi": set("अआइईउऊऋएऐओऔकखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह"),
    "th": set("กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ"),
}

_SUBPROCESS_SAFE_VARS = {
    "PATH", "SystemRoot", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE",
    "HOME", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "ProgramData",
    "PYTHONPATH", "PYTHONIOENCODING", "PYTHONUNBUFFERED", "CUDA_PATH",
    "CUDA_VISIBLE_DEVICES", "HF_HOME", "TORCH_HOME", "OLLAMA_HOST",
}


def detect_language(text: str) -> str:
    """Detect language of a short text segment.
    Uses langdetect (55 languages) when available, falls back to character heuristics.
    Returns ISO 639-1 language code or 'unknown'."""
    if not text or not text.strip():
        return "unknown"

    text_clean = text.strip()

    # Try langdetect first (most accurate)
    if _HAS_LANGDETECT:
        try:
            # langdetect needs at least a few characters to be reliable
            if len(text_clean) > 5:
                result = _langdetect.detect(text_clean)[:2].lower()
                # langdetect can misidentify short phrases as rare languages.
                # Verify with common English words; fall back to "unknown" otherwise
                # (the engine will use Whisper's base language for unknown segments).
                _RARE_CONFUSIONS = {"af", "fy", "cy", "sw", "fr", "ga", "gd", "la", "so"}
                if result in _RARE_CONFUSIONS:
                    _COMMON_EN = {"the", "is", "are", "was", "this", "that", "with",
                                  "what", "when", "who", "how", "you", "your", "for",
                                  "and", "but", "not", "have", "has", "good", "work",
                                  "job", "time", "years", "interview", "company",
                                  "team", "thank", "welcome", "please", "morning",
                                  "practice", "questions", "experience", "engineer",
                                  "salary", "video", "subscribe", "channel", "like"}
                    text_words = set(re.findall(r"\w+", text_clean.lower()))
                    if text_words & _COMMON_EN:
                        return "en"
                    return "unknown"  # Don't trust rare language codes
                return result
        except Exception:
            pass  # Fall through to heuristics

    # Fallback: character-based detection
    for lang, chars in _SCRIPT_CHARS.items():
        if any(c in text_clean for c in chars):
            return lang

    return "unknown"


def split_bilingual_text(text: str) -> list[tuple[str, str]]:
    """Split mixed-language text into (text, language) chunks.
    E.g. 'Hola, ¿cómo estás? Good morning, welcome.' →
    [('Hola, ¿cómo estás?', 'es'), ('Good morning, welcome.', 'en')]
    """
    if not text or not text.strip():
        return [(text, "unknown")]

    # Split into sentences
    sentences = re.split(r"(?<=[.!?¡¿])\s+", text.strip())
    if len(sentences) <= 1:
        lang = detect_language(text)
        return [(text, lang)]

    # Detect language per sentence, then group consecutive same-language sentences
    chunks = []
    current_chunk = []
    current_lang = None

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        lang = detect_language(sent)

        if lang == current_lang or current_lang is None:
            current_chunk.append(sent)
            current_lang = lang
        else:
            if current_chunk:
                chunks.append((" ".join(current_chunk), current_lang or "unknown"))
            current_chunk = [sent]
            current_lang = lang

    if current_chunk:
        chunks.append((" ".join(current_chunk), current_lang or "unknown"))

    return chunks if chunks else [(text, "unknown")]


_ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PARENT_DIR = os.path.dirname(_ENGINE_DIR)
_POSSIBLE_ROOTS = [
    _ENGINE_DIR,
    _PARENT_DIR,
    os.path.join(_ENGINE_DIR, "_up_"),
    os.path.join(_PARENT_DIR, "_up_"),
]
_dev_root = os.environ.get("AUTODUB_DEV_ROOT", "")
if _dev_root:
    _POSSIBLE_ROOTS.insert(0, _dev_root)


def get_python_exe():
    """Returns the path to the current python executable (handles virtualenvs)"""
    if "UV_PROJECT_ENVIRONMENT" in os.environ:
        cand = os.path.join(os.environ["UV_PROJECT_ENVIRONMENT"], "Scripts", "python.exe")
        if os.path.exists(cand):
            return cand
    for root in _POSSIBLE_ROOTS:
        candidate = os.path.join(root, ".venv", "Scripts", "python.exe")
        if os.path.exists(candidate):
            return candidate
    return sys.executable


def _resolve_venv_python(venv_name: str) -> str:
    for root in _POSSIBLE_ROOTS:
        candidate = os.path.join(root, venv_name, "Scripts", "python.exe")
        if os.path.exists(candidate):
            return candidate
    return get_python_exe()


def kill_process_tree(pid):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
    except psutil.NoSuchProcess:
        pass


_SUBPROCESS_BLOCK_VARS = {
    "GITHUB_TOKEN",
    "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY",
    "DEEPL_API_KEY",
    "OPENAI_API_KEY",
    "AZURE_OPENAI_KEY",
    "HUGGINGFACE_TOKEN",
    "WS_AUTH_TOKEN",
    "VERCEL_API_TOKEN",
}


def _safe_subprocess_env(**extra) -> dict:
    """Return minimal env for subprocess calls — NO API keys, NO secrets.

    Uses both whitelist (SAFE_VARS) and blacklist (BLOCK_VARS) approach:
    1. Start with whitelisted variables from os.environ
    2. Add any GPU-related vars (CUDA_, NVIDIA_, TORCH_, OLLAMA_)
    3. Explicitly REMOVE any blacklisted vars
    4. Add caller-provided extras
    """
    import os
    # Start with whitelisted safe vars
    env = {}
    for key in _SUBPROCESS_SAFE_VARS:
        val = os.environ.get(key)
        if val:
            env[key] = val
    # Add GPU-related vars
    for key, val in os.environ.items():
        if key.startswith(("CUDA_", "NVIDIA_", "TORCH_", "OLLAMA_")):
            if key not in env:
                env[key] = val
    # Explicitly remove sensitive vars (defense in depth)
    for key in _SUBPROCESS_BLOCK_VARS:
        env.pop(key, None)
    # Add caller extras
    env.update(extra)
    return env


def _pipeline_t(key: str, ui_lang: str = "ru", **kwargs) -> str:
    """Return a translated pipeline log message."""

    try:
        from engine import _PIPELINE_LOG
    except ImportError:
        import sys
        if "engine" in sys.modules:
            _PIPELINE_LOG = sys.modules["engine"]._PIPELINE_LOG
        else:
            _PIPELINE_LOG = {}
    entry = _PIPELINE_LOG.get(key, {})
    msg = entry.get(ui_lang) or entry.get("en") or key
    if kwargs:
        msg = msg.format(**kwargs)
    return msg


def _set_model_status(model: str, state: str):
    """Update global pipeline_status dict for the StatusBar."""
    try:
        from shared import pipeline_status  # noqa: PLC0415

        pipeline_status["models"][model] = state
        pipeline_status["active"] = True
    except Exception:
        pass


def _finish_pipeline_status(error: bool = False):
    """Finalize pipeline status. Reset models to idle (gray indicators).
    On error: mark the running model as 'error' (red) for diagnostics."""
    try:
        from shared import pipeline_status  # noqa: PLC0415

        pipeline_status["active"] = False
        pipeline_status["step"] = ""
        pipeline_status["step_index"] = 0
        step_order = ["demucs", "whisper", "pyannote", "translate", "tts", "mux"]
        if error:
            # Mark the currently running model as 'error' (visible red in StatusBar)
            found = False
            for m in step_order:
                if pipeline_status["models"].get(m) == "running":
                    pipeline_status["models"][m] = "error"
                    found = True
                    break
            if not found:
                for m in step_order:
                    if pipeline_status["models"].get(m) == "idle":
                        pipeline_status["models"][m] = "error"
                        break
            # Остальные модели — idle (серые)
            for m in step_order:
                if pipeline_status["models"].get(m) not in ("error",):
                    pipeline_status["models"][m] = "idle"
        else:
            # Успех/отмена — все модели idle (серые индикаторы)
            for k in pipeline_status["models"]:
                pipeline_status["models"][k] = "idle"
    except Exception:
        pass


def _set_engine_info(model: str, engine_id: str):
    """Set which engine is used for translate/TTS (for StatusBar display)."""
    try:
        from shared import pipeline_status  # noqa: PLC0415

        if model == "translate":
            pipeline_status["translate_engine"] = engine_id.lower()
        elif model == "tts":
            pipeline_status["tts_engine"] = engine_id.lower()
    except Exception:
        pass


def _set_pipeline_step(step_name: str, step_index: int):
    try:
        from shared import pipeline_status  # noqa: PLC0415

        pipeline_status["step"] = step_name
        pipeline_status["step_index"] = step_index
    except Exception:
        pass
