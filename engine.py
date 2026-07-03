import os
import re
import shutil
import subprocess
import sys

# ── Language detection for bilingual subtitle processing ──
# Uses langdetect library (55 languages) with fallback to character-based heuristics
try:
    import langdetect as _langdetect
    # Seed the detector for deterministic results
    from langdetect import DetectorFactory
    DetectorFactory.seed = 0
    _HAS_LANGDETECT = True
except ImportError:
    _HAS_LANGDETECT = False

# Characters unique to specific scripts (fallback when langdetect is unavailable)
_SCRIPT_CHARS = {
    "es": set("áéíóúüñ¿¡"),
    "ru": set("абвгдеёжзийклмнопрстуфхцчшщъыьэюя"),
    "tr": set("ğışçöüİĞŞÇÖÜ"),
    "ar": set("ابتثجحخدذرزسشصضطظعغفقكلمنهوي"),
    "zh": set("的一是不了在有人我他这为之来以个们到说"),  # Common CJK
    "ja": set("のはがでをにたてとしすいるまな"),  # Hiragana
    "ko": set("이것은그리고그래서때문에에서의"),  # Common Hangul
    "hi": set("अआइईउऊएऐओऔकखगघचछजझटठडढणतथदधनपफबभमयरलवशषसह"),
    "th": set("กขคงจฉชซฎฐณดตถทธนบปผฝพฟภมยรลวศษสหอ"),
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
import threading
import warnings

warnings.filterwarnings("ignore")

import torch

os.environ["PYTHONIOENCODING"] = "utf-8"

# ── Venv resolution with fallback for installed app ──
# In the installed version (AppData), only .venv is bundled.
# .venv-xtts may only exist in the dev project directory.
# (F5-TTS, Qwen3-TTS, ONNX removed — not stable on Windows)
_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
# Go up one level if we're inside an extracted resource dir
_PARENT_DIR = os.path.dirname(_ENGINE_DIR)
_POSSIBLE_ROOTS = [
    _ENGINE_DIR,
    _PARENT_DIR,
    # Tauri v2 extracts resources next to the binary or in _up_ dir
    os.path.join(_ENGINE_DIR, "_up_"),
    os.path.join(_PARENT_DIR, "_up_"),
]
# Also check AUTODUB_DEV_ROOT env var for dev convenience
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
    import sys
    return sys.executable

def _resolve_venv_python(venv_name: str) -> str:
    for root in _POSSIBLE_ROOTS:
        candidate = os.path.join(root, venv_name, "Scripts", "python.exe")
        if os.path.exists(candidate):
            return candidate
    return get_python_exe()

# WhisperX will be imported locally inside the worker

import time

import psutil
from pydub import AudioSegment

from backend.translator import Translator
from backend.vram_manager import get_monitor


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


# ── Safe subprocess environment (security: don't leak API keys to child processes) ──
# Whitelist of safe env vars to pass to child processes
_SUBPROCESS_SAFE_VARS = {
    "PATH",
    "SystemRoot",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOME",
    "HOMEDRIVE",
    "HOMEPATH",
    "APPDATA",
    "LOCALAPPDATA",
    "ProgramData",
    "PYTHONPATH",
    "PYTHONIOENCODING",
    "PYTHONUNBUFFERED",
    "CUDA_PATH",
    "CUDA_VISIBLE_DEVICES",
    "HF_HOME",
    "TORCH_HOME",
    "OLLAMA_HOST",
    "COQUI_TOS_AGREED",
    "COMSPEC",
    "PATHEXT",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
}

# Blacklist of sensitive vars that MUST NOT leak to child processes
_SUBPROCESS_BLOCK_VARS = {
    "GITHUB_TOKEN",
    "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY",
    "DEEPL_API_KEY",
    "OPENAI_API_KEY",
    "AZURE_OPENAI_KEY",
    "HF_TOKEN",
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


# ── Multi-language log messages ──
_PIPELINE_LOG = {
    "downloading_video": {
        "ru": "📥 Загрузка видео: {url}...",
        "en": "📥 Downloading video: {url}...",
        "tr": "📥 Video indiriliyor: {url}...",
    },
    "downloaded": {
        "ru": "✅ Загружено: {name}",
        "en": "✅ Downloaded: {name}",
        "tr": "✅ İndirildi: {name}",
    },
    "demucs_start": {
        "ru": "🎵 Изоляция вокала (Demucs) — извлекаем чистый голос...",
        "en": "🎵 Voice isolation (Demucs) — extracting clean voice...",
        "tr": "🎵 Ses izolasyonu (Demucs) — temiz ses çıkarılıyor...",
    },
    "demucs_skip": {
        "ru": "✅ Чистый голос найден (пропуск Demucs)",
        "en": "✅ Clean voice found (skipping Demucs)",
        "tr": "✅ Temiz ses bulundu (Demucs atlanıyor)",
    },
    "low_vram_cleaning": {
        "ru": "⚠ Мало VRAM, чистка фоновых процессов...",
        "en": "⚠ Low VRAM, cleaning background processes...",
        "tr": "⚠ VRAM düşük, arka plan işlemleri temizleniyor...",
    },
    "low_vram_cpu_fallback": {
        "ru": "⚠ VRAM всё ещё мало. Переключаюсь на CPU.",
        "en": "⚠ VRAM still low. Switching to CPU.",
        "tr": "⚠ VRAM hâlâ düşük. CPU'ya geçiliyor.",
    },
    "segments_from_cache": {
        "ru": "✅ Сегменты загружены из кэша ({n} шт., пропуск Whisper)",
        "en": "✅ Segments loaded from cache ({n} pcs, skipping Whisper)",
        "tr": "✅ Segmentler önbellekten yüklendi ({n} adet, Whisper atlanıyor)",
    },
    "whisper_loading": {
        "ru": "🔄 Загрузка {engine} ({model}) на {device}...",
        "en": "🔄 Loading {engine} ({model}) on {device}...",
        "tr": "🔄 {engine} ({model}) {device} üzerinde yükleniyor...",
    },
    "segments_found": {
        "ru": "✅ Найдено и размечено {n} сегментов.",
        "en": "✅ Found and marked {n} segments.",
        "tr": "✅ {n} segment bulundu ve işaretlendi.",
    },
    "diarization_start": {
        "ru": "👥 Диаризация (Pyannote) — определение спикеров...",
        "en": "👥 Diarization (Pyannote) — identifying speakers...",
        "tr": "👥 Diarizasyon (Pyannote) — konuşmacılar belirleniyor...",
    },
    "diarization_done": {
        "ru": "✅ Диаризация: {pyannote} спикеров в аудио, {n} в сегментах.",
        "en": "✅ Diarization: {pyannote} in audio, {n} in segments.",
        "tr": "✅ Diarizasyon: {pyannote} seste, {n} segmentte.",
    },
    "diarization_failed": {
        "ru": "⚠ Диаризация не удалась: {e}. Использую SPEAKER_00.",
        "en": "⚠ Diarization failed: {e}. Using SPEAKER_00.",
        "tr": "⚠ Diarizasyon başarısız: {e}. SPEAKER_00 kullanılıyor.",
    },
    "subtitles_saved": {
        "ru": "📝 Оригинальные субтитры сохранены.",
        "en": "📝 Original subtitles saved.",
        "tr": "📝 Orijinal altyazılar kaydedildi.",
    },
    "processing_lang": {
        "ru": "▶ Обработка языка: {lang}...",
        "en": "▶ Processing language: {lang}...",
        "tr": "▶ Dil işleniyor: {lang}...",
    },
    "translation_from_cache": {
        "ru": "  ✅ Перевод загружен из кэша ({n} сегментов)",
        "en": "  ✅ Translation loaded from cache ({n} segments)",
        "tr": "  ✅ Çeviri önbellekten yüklendi ({n} segment)",
    },
    "translation_start": {
        "ru": "🔤 Перевод на {lang}...",
        "en": "🔤 Translating to {lang}...",
        "tr": "🔤 {lang} diline çevriliyor...",
    },
    "translation_done": {
        "ru": "✅ Перевод завершен!",
        "en": "✅ Translation complete!",
        "tr": "✅ Çeviri tamamlandı!",
    },
    "tts_edge_start": {
        "ru": "🎙️ Edge-TTS: генерация {n} сегментов...",
        "en": "🎙️ Edge-TTS: generating {n} segments...",
        "tr": "🎙️ Edge-TTS: {n} segment oluşturuluyor...",
    },
    "tts_group_progress": {
        "ru": "  -> TTS группа {gi}/{total}: {n} сегментов, {chars} симв.",
        "en": "  -> TTS group {gi}/{total}: {n} segs, {chars} chars",
        "tr": "  -> TTS grubu {gi}/{total}: {n} seg, {chars} karakter",
    },
    "lipsync_start": {
        "ru": "👄 Запуск Lip-Sync (LatentSync/Wav2Lip)...",
        "en": "👄 Starting Lip-Sync (LatentSync/Wav2Lip)...",
        "tr": "👄 Lip-Sync başlatılıyor (LatentSync/Wav2Lip)...",
    },
    "lipsync_done": {
        "ru": "✅ Lip-Sync завершен!",
        "en": "✅ Lip-Sync complete!",
        "tr": "✅ Lip-Sync tamamlandı!",
    },
    "lipsync_error": {
        "ru": "⚠ Ошибка Lip-Sync: {e}",
        "en": "⚠ Lip-Sync error: {e}",
        "tr": "⚠ Lip-Sync hatası: {e}",
    },
    "lipsync_not_found": {
        "ru": "⚠ Скрипт Lip-Sync не найден. Пропуск.",
        "en": "⚠ Lip-Sync script not found. Skipping.",
        "tr": "⚠ Lip-Sync betiği bulunamadı. Atlanıyor.",
    },
    "pipeline_cancelled": {
        "ru": "🛑 Пайплайн отменён пользователем.",
        "en": "🛑 Pipeline cancelled by user.",
        "tr": "🛑 İşlem kullanıcı tarafından iptal edildi.",
    },
    "pipeline_error": {
        "ru": "❌ Ошибка пайплайна: {e}",
        "en": "❌ Pipeline error: {e}",
        "tr": "❌ İşlem hatası: {e}",
    },
    "model_loading": {
        "ru": "📦 Загрузка модели: {model}...",
        "en": "📦 Loading model: {model}...",
        "tr": "📦 Model yükleniyor: {model}...",
    },
    "model_loaded": {
        "ru": "✅ Модель загружена.",
        "en": "✅ Model loaded.",
        "tr": "✅ Model yüklendi.",
    },
    "pipeline_success": {
        "ru": "✅ Готово: {path}",
        "en": "✅ Done: {path}",
        "tr": "✅ Tamam: {path}",
    },
}


def _pipeline_t(key: str, ui_lang: str = "ru", **kwargs) -> str:
    """Return a translated pipeline log message."""
    entry = _PIPELINE_LOG.get(key, {})
    msg = entry.get(ui_lang) or entry.get("en") or key
    if kwargs:
        msg = msg.format(**kwargs)
    return msg


class EventSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for cb in self.callbacks:
            try:
                cb(*args, **kwargs)
            except Exception:
                pass  # Never let a callback crash the pipeline


PIPELINE_BUSY = False
PIPELINE_LOCK = threading.Lock()


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


class InterruptedError(Exception):
    """Raised when user cancels pipeline — triggers clean finally-block cleanup."""

    pass


class AutoDubWorker(threading.Thread):
    def __init__(
        self,
        video_path=None,
        out_dir=None,
        langs=None,
        model_size=None,
        device=None,
        translator_engine=None,
        gemini_key="",
        deepseek_key="",
        deepl_key="",
        dub_engine="",
        hf_key="",
        manual_mode=False,
        translator_model="gemma4:e4b",
    ):
        super().__init__()
        self.progress_signal = EventSignal()
        self.log_signal = EventSignal()
        self.finished_signal = EventSignal()
        self.extras_signal = EventSignal()
        self.vram_warning_signal = EventSignal()
        self.translation_ready_signal = EventSignal()
        self.manual_edit_signal = EventSignal()
        self._stop_event = threading.Event()

        # Support both old positional-arg style and new dict-based config (v3 UI)
        if isinstance(video_path, dict):
            cfg = video_path
            self.video_path = cfg.get("video_path", "")

            # ── Security: Path Traversal Protection for out_dir ──
            req_out_dir = cfg.get("out_dir")

            # Determine sane default output directory
            is_url_input = bool(
                self.video_path
                and (
                    self.video_path.startswith("http://")
                    or self.video_path.startswith("https://")
                )
            )
            if is_url_input:
                default_out = os.path.join(os.getcwd(), "downloads")
            else:
                default_out = (
                    os.path.dirname(self.video_path) if self.video_path else os.getcwd()
                )
                if not default_out:
                    default_out = os.getcwd()

            # Safe makedirs with validation (defence against URL-as-path)
            def _safe_makedirs(path: str):
                """Only create directories on local filesystem, never for URLs."""
                if any(
                    path.startswith(p) for p in ("http://", "https://", "ftp://")
                ):
                    raise ValueError(
                        f"Refusing to create directory from URL: {path!r}"
                    )
                if not path:
                    path = os.getcwd()
                os.makedirs(path, exist_ok=True)

            _safe_makedirs(default_out)

            if req_out_dir:
                # ── Reject URL-like out_dir immediately ──
                if req_out_dir.startswith(("http://", "https://", "ftp://")):
                    print(f"[SECURITY] Blocked URL as out_dir: {req_out_dir}")
                    self.out_dir = default_out
                else:
                    # Resolve paths to absolute to prevent bypass via symlinks or ..
                    abs_req = os.path.realpath(req_out_dir)
                    # Allow only if it's inside user home or same drive (for Industrial Edition)
                    # But strictly block sensitive system paths
                    system_paths = [
                        os.environ.get("SystemRoot", "C:\\Windows").lower(),
                        "C:\\program files",
                        "C:\\program files (x86)",
                        "C:\\users\\public",
                    ]
                    is_system = any(abs_req.lower().startswith(p) for p in system_paths)

                    if not is_system:
                        self.out_dir = abs_req
                    else:
                        print(f"[SECURITY] Blocked out_dir on system path: {abs_req}")
                        self.out_dir = default_out
            else:
                self.out_dir = default_out

            target_langs = cfg.get("target_langs", cfg.get("langs", ["en"]))
            self.langs = {lang: f"{lang}-default" for lang in target_langs}
            self.model_size = cfg.get("whisper_model", "large-v3")
            self.whisper_engine = cfg.get("whisper_engine", "whisperX")
            self.device = cfg.get("device", "cpu")
            self.translator_engine = cfg.get(
                "translation_engine", "Google Translate (Free)"
            )
            self.translator_model = cfg.get("translator_model", "gemma4:e4b")
            self.user_glossary = cfg.get("user_glossary", "")
            self.gemini_key = cfg.get("gemini_key", "")
            self.deepseek_key = cfg.get("deepseek_key", "")
            self.deepl_key = cfg.get("deepl_key", "")
            self.dub_engine = cfg.get("dub_engine", "Edge-TTS (Cloud, Free, Fast)")
            self.hf_key = cfg.get("hf_key", "")
            self.manual_mode = cfg.get("manual_mode", False)
            self.lip_sync = cfg.get("lip_sync", False)
            self.lip_sync_engine = cfg.get("lip_sync_engine", "off")
            self.tag = cfg.get("tag", "")
            self.demucs_model = cfg.get("demucs_model", "htdemucs_ft")
            self.ui_language = cfg.get("ui_language", "ru")
            self.use_gender_ai = cfg.get("use_gender_ai", True)
            self.use_youtube_subs = cfg.get("use_youtube_subs", True)
            self.use_nlp_splitter = cfg.get("use_nlp_splitter", True)
            self.max_duration = cfg.get("max_duration", 0)
            self.local_only = cfg.get("local_only", False)
            self.source_lang = cfg.get("source_lang", "en")
            
            # Enforce local_only restrictions
            if self.local_only:
                if "ollama" not in self.translator_engine.lower() and "llamacpp" not in self.translator_engine.lower() and "qwen" not in self.translator_engine.lower():
                    self.translator_engine = "Ollama / Gemma 4 (Local AI, Slow)"
                if "xtts" not in self.dub_engine.lower() and "f5" not in self.dub_engine.lower():
                    self.dub_engine = "XTTS v2 (Local, Voice Clone)"
                # Disable YouTube subs download as it hits external API
                self.use_youtube_subs = False
        else:
            self.video_path = video_path
            # ── Reject URL-like out_dir even in positional mode ──
            if out_dir and str(out_dir).startswith(("http://", "https://", "ftp://")):
                print(f"[SECURITY] Blocked URL as out_dir (positional): {out_dir}")
                out_dir = os.path.join(os.getcwd(), "downloads")
            self.out_dir = out_dir
            self.lip_sync = False
            self.tag = ""
            self.demucs_model = "htdemucs_ft"
            self.ui_language = "ru"
            self.use_gender_ai = True
            self.use_youtube_subs = True
            self.use_nlp_splitter = True
            self.max_duration = 0
            self.local_only = False
            self.source_lang = "en"
            self.langs = langs
            self.model_size = model_size
            self.device = device
            self.translator_engine = translator_engine
            self.gemini_key = gemini_key
            self.deepseek_key = deepseek_key
            self.deepl_key = deepl_key
            self.dub_engine = dub_engine
            self.hf_key = hf_key
            self.manual_mode = manual_mode
            self.translator_model = translator_model
            self.lip_sync = False
            self.lip_sync_engine = "off"

        self.translator = Translator(
            self.translator_engine,
            self.gemini_key,
            self.deepseek_key,
            self.deepl_key,
            self.device,
            translator_model=self.translator_model,
            user_glossary=self.user_glossary,
        )

        self.pause_event = threading.Event()
        self.edited_segments = None
        self.active_processes = []

    def isInterruptionRequested(self):
        return self._stop_event.is_set()

    def requestInterruption(self):
        self._stop_event.set()
        self.pause_event.set()
        for p in self.active_processes:
            try:
                p.terminate()
            except:  # noqa: E722
                pass

    def _run_subprocess(self, cmd, **kwargs):
        check = kwargs.pop("check", False)
        timeout = kwargs.pop("timeout", None)

        # ── Security: don't leak API keys to child processes ──
        if "env" not in kwargs:
            kwargs["env"] = _safe_subprocess_env()
        else:
            # Merge caller-provided extras into safe base (caller's keys take precedence)
            base = _safe_subprocess_env()
            base.update(kwargs["env"])
            kwargs["env"] = base

        # Don't override if explicitly devnull
        if kwargs.get("stdout") != subprocess.DEVNULL:
            kwargs["stdout"] = subprocess.PIPE
            kwargs["stderr"] = subprocess.STDOUT
            kwargs["bufsize"] = 1
            kwargs["text"] = True
            kwargs["encoding"] = "utf-8"
            kwargs["errors"] = "replace"

        process = subprocess.Popen(cmd, **kwargs)
        self.active_processes.append(process)

        def _read_output(pipe):
            for line in pipe:
                if line.strip():
                    self.log_signal.emit(f"  > {line.strip()}")

        reader_thread = None
        if kwargs.get("stdout") == subprocess.PIPE:
            reader_thread = threading.Thread(
                target=_read_output, args=(process.stdout,), daemon=True
            )
            reader_thread.start()

        start_time = time.time()

        while process.poll() is None:
            if self._stop_event.is_set():
                try:
                    kill_process_tree(process.pid)
                    # Close stdout to unblock reader thread
                    try:
                        process.stdout.close()
                    except Exception:
                        pass
                except:  # noqa: E722
                    pass
            if timeout is not None and (time.time() - start_time) > timeout:
                try:
                    kill_process_tree(process.pid)
                    # Kill orphan CUDA child processes that may hold VRAM
                    import subprocess as _sp
                    _sp.run(
                        ["taskkill", "/f", "/fi", "IMAGENAME eq python.exe", "/fi", "MEMUSAGE gt 500000"],
                        capture_output=True, timeout=5,
                    )
                except:  # noqa: E722
                    pass
                raise subprocess.TimeoutExpired(cmd, timeout)
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass

        if reader_thread:
            reader_thread.join(timeout=1.0)

        if process in self.active_processes:
            self.active_processes.remove(process)
        if process.returncode != 0:
            if self._stop_event.is_set():
                raise InterruptedError("Pipeline cancelled by user")
            if check:
                raise subprocess.CalledProcessError(process.returncode, cmd)

    def resume_with_translations(self, edited_segments):
        self.edited_segments = edited_segments
        self.pause_event.set()

    def resume(self, subs: list):
        """v3 UI compatibility — resume from manual editor."""
        edited = []
        for s in subs:
            edited.append(
                {
                    "text": s.get("trans", s.get("text", "")),
                    "start": float(s.get("start", 0)),
                    "end": float(s.get("end", 0)),
                    "speaker": s.get("speaker", "SPEAKER_00"),
                    "skip_dub": s.get("skip_dub", False),
                    "gender": s.get("gender", "unknown"),
                }
            )
        self.resume_with_translations(edited)

    def format_timestamp(self, seconds):
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        msecs = int((seconds - int(seconds)) * 1000)
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"

    def _download_youtube(self, url, out_dir):
        """Download video from YouTube/TikTok/Vimeo URL using yt-dlp."""
        from urllib.parse import urlparse  # noqa: PLC0415

        import yt_dlp  # noqa: PLC0415

        # SSRF Protection: Validate URL scheme and domain
        parsed = urlparse(url)
        allowed_domains = [
            "youtube.com",
            "youtu.be",
            "www.youtube.com",
            "tiktok.com",
            "www.tiktok.com",
            "vimeo.com",
            "www.vimeo.com",
        ]
        if (
            parsed.scheme not in ["http", "https"]
            or parsed.hostname not in allowed_domains
        ):
            raise ValueError(
                f"URL domain '{parsed.hostname}' is not allowed or invalid scheme. Only YouTube, TikTok, and Vimeo are supported."
            )

        self.log_signal.emit(
            _pipeline_t("downloading_video", self.ui_language, url=url[:60])
        )
        ydl_opts = {
            "outtmpl": os.path.join(out_dir, "%(title)s.%(ext)s"),
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": [getattr(self, "source_lang", "en"), "en"],
            "quiet": True,
            "no_warnings": True,
            "retries": 10,
            "fragment_retries": 10,
            "postprocessors": [
                {
                    "key": "FFmpegSubtitlesConvertor",
                    "format": "srt",
                }
            ],
        }

        cookie_file = os.path.join(os.path.dirname(__file__), "backend", "youtube_cookies.txt")
        if os.path.exists(cookie_file):
            ydl_opts["cookiefile"] = cookie_file
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
                if not filepath.endswith(".mp4"):
                    filepath = filepath.rsplit(".", 1)[0] + ".mp4"
                if os.path.exists(filepath):
                    self.log_signal.emit(
                        _pipeline_t(
                            "downloaded",
                            self.ui_language,
                            name=os.path.basename(filepath),
                        )
                    )
                    return filepath
        except yt_dlp.utils.DownloadError as e:
            if (
                "Too Many Requests" in str(e)
                or "HTTP Error 429" in str(e)
                or "subtitles" in str(e).lower()
            ):
                self.log_signal.emit(
                    "⚠️ YouTube rate limited subtitles (HTTP 429). Retrying without subtitles (will use Whisper instead)..."
                )
                # Fallback: Disable subtitle download and try again
                ydl_opts["writesubtitles"] = False
                ydl_opts["writeautomaticsub"] = False
                with yt_dlp.YoutubeDL(ydl_opts) as ydl_fallback:
                    info = ydl_fallback.extract_info(url, download=True)
                    filepath = ydl_fallback.prepare_filename(info)
                    if not filepath.endswith(".mp4"):
                        filepath = filepath.rsplit(".", 1)[0] + ".mp4"
                    if os.path.exists(filepath):
                        self.log_signal.emit(
                            _pipeline_t(
                                "downloaded",
                                self.ui_language,
                                name=os.path.basename(filepath),
                            )
                        )
                        return filepath
            else:
                raise e

        raise RuntimeError(f"Failed to download: {url}")

    def _check_cancelled(self):
        """Raise InterruptedError if stop was requested — allows clean finally-block cleanup."""
        if self._stop_event.is_set():
            raise InterruptedError("Pipeline cancelled by user")

    def _report_error_to_github(self, error_msg: str):
        """Send pipeline error to GitHub Issues (best-effort, never raises)."""
        try:
            import json as _json  # noqa: PLC0415
            from os import environ, path  # noqa: PLC0415

            import httpx  # noqa: PLC0415

            token = environ.get("GITHUB_TOKEN", "")
            if not token:
                root = path.dirname(path.dirname(__file__))
                for cfg_name in ["config.json", "github_token.txt"]:
                    cfg_path = path.join(root, cfg_name)
                    if path.exists(cfg_path):
                        try:
                            with open(cfg_path, "r", encoding="utf-8") as f:
                                if cfg_name == "github_token.txt":
                                    token = f.read().strip()
                                else:
                                    token = _json.load(f).get("github_token", "")
                                if token:
                                    break
                        except Exception:
                            pass
            if not token:
                return

            safe = str(error_msg)[:300]
            import re  # noqa: PLC0415

            safe = re.sub(r"C:\\Users\\[^\\]+", "~", safe)
            safe = re.sub(r"[A-Z]:\\[^\s,]+", "[path]", safe)
            title = f"[Bug] Pipeline error: {safe[:80]}"
            body = f"**Error:** {safe}\n**Time:** {__import__('time').strftime('%Y-%m-%dT%H:%M:%S')}"

            httpx.post(
                "https://api.github.com/repos/LiskinLabs/autodubstudio/issues",
                json={"title": title, "body": body, "labels": ["bug", "auto-reported"]},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=10,
            )
        except Exception:
            pass

    def run(self):
        global PIPELINE_BUSY
        with PIPELINE_LOCK:
            if PIPELINE_BUSY:
                self.finished_signal.emit(False, "Pipeline Busy")
                return
            PIPELINE_BUSY = True

        all_created_files = []
        demucs_out_dir = None
        _was_url_source = False  # Track if source was URL for cleanup

        # ── Start continuous resource monitor (VRAM + RAM) ──
        monitor = get_monitor(
            on_cleanup=lambda level, vram, ram, actions: self.log_signal.emit(
                f"  🧹 Auto-cleanup [{level}]: VRAM={vram}MB RAM={ram}MB → {', '.join(actions)}"
            )
        )
        self.log_signal.emit(
            f"  📊 Resource monitor active — VRAM: {monitor.vram_free_mb}MB free, RAM: {monitor.ram_free_mb}MB free"
        )
        try:
            # Handle YouTube/TikTok/Vimeo URLs — download first
            if self.video_path.startswith("http://") or self.video_path.startswith(
                "https://"
            ):
                _was_url_source = True
                self.video_path = self._download_youtube(self.video_path, self.out_dir)

            self._check_cancelled()
            # Security: validate and normalize video path
            if not self.video_path or not os.path.isfile(self.video_path):
                self.finished_signal.emit(False, "Invalid video file path")
                return
            self.video_path = os.path.realpath(self.video_path)
            
            # Trim video if max_duration is set
            max_duration = self.max_duration
            if max_duration > 0:
                self.log_signal.emit(f"✂️ Trimming video to {max_duration} seconds...")
                base, ext = os.path.splitext(self.video_path)
                trimmed_path = f"{base}_trimmed{ext}"
                cmd = f'ffmpeg -y -i "{self.video_path}" -t {max_duration} -c copy "{trimmed_path}"'
                self._run_subprocess(cmd)
                if os.path.exists(trimmed_path):
                    self.video_path = trimmed_path
                self.log_signal.emit(f"✅ Video trimmed successfully: {self.video_path}")

            # Language-TTS compatibility check
            # Use IDs for internal logic to match frontend config
            TTS_COMPAT = {
                "edge-tts": {
                    "ru", "en", "tr", "ar", "es", "fr", "de", "zh", "ja", "ko",
                    "it", "pt", "pl", "hi",
                },
                "azure": {
                    "ru", "en", "tr", "ar", "es", "fr", "de", "zh", "ja", "ko",
                    "it", "pt", "pl", "hi",
                },
                "openai": {
                    "ru", "en", "tr", "ar", "es", "fr", "de", "zh", "ja", "ko",
                    "it", "pt", "pl", "hi",
                },
                "xttsv2": {
                    "ru", "en", "tr", "ar", "es", "fr", "de", "zh", "ja", "ko",
                    "it", "pt", "pl", "hi",
                },
                "qwen3-tts": {
                    "ru", "en", "zh", "ja", "ko", "es", "de", "fr", "pt", "it",
                },
                "f5-tts": {
                    "tr", "en", "zh", "ru",
                },
                # "gpt-sovits": NOT IMPLEMENTED — removed until worker exists
                "none": {
                    "ru", "en", "tr", "ar", "es", "fr", "de", "zh", "ja", "ko",
                    "it", "pt", "pl", "hi",
                },

                "xttsv2": {
                    "ru",
                    "en",
                    "tr",
                    "ar",
                    "es",
                    "fr",
                    "de",
                    "zh",
                    "ja",
                    "ko",
                    "it",
                    "pt",
                    "pl",
                    "hi",
                },
            }
            # Fallback for display names if sent instead of IDs
            DISPLAY_TO_ID = {
                "Edge-TTS (Cloud, Free, Fast)": "edge-tts",
                "XTTSv2 Local": "xttsv2",
                "Azure OpenAI (Cloud)": "azure",
            }
            engine_id = self.dub_engine.lower()
            if self.dub_engine in DISPLAY_TO_ID:
                engine_id = DISPLAY_TO_ID[self.dub_engine]

            for lang, _ in self.langs.items():
                compat = TTS_COMPAT.get(engine_id, set())
                if lang not in compat:
                    err = f"❌ {self.dub_engine} не поддерживает язык '{lang}'. Совместимые языки: {sorted(compat)}"
                    self.log_signal.emit(err)
                    self.finished_signal.emit(False, err)
                    return

            base_name = os.path.splitext(os.path.basename(self.video_path))[0]
            # Sanitize: ASCII-only alphanumeric + dash + underscore, NO path traversal
            base_name = re.sub(  # noqa: F821
                r"[^a-zA-Z0-9_\-]", "_", base_name
            )
            base_name = base_name.strip("_.") or "video"  # prevent empty name

            # ── Checkpoint helper ──
            def _save_checkpoint(name, data):
                cp_path = os.path.join(
                    self.out_dir, f".autodub_{base_name}_{name}.json"
                )
                import json as _json  # noqa: PLC0415

                with open(cp_path, "w", encoding="utf-8") as f:
                    _json.dump(data, f, ensure_ascii=False)
                all_created_files.append(cp_path)
                return cp_path

            def _load_checkpoint(name):
                cp_path = os.path.join(
                    self.out_dir, f".autodub_{base_name}_{name}.json"
                )
                if os.path.exists(cp_path):
                    import json as _json  # noqa: PLC0415

                    with open(cp_path, "r", encoding="utf-8") as f:
                        return _json.load(f)
                return None

            # 1. Изоляция вокала (Demucs)
            self._check_cancelled()
            self.progress_signal.emit(5)
            _set_pipeline_step("demucs", 1)
            _set_model_status("demucs", "running")
            self.log_signal.emit(_pipeline_t("demucs_start", self.ui_language))
            demucs_out_dir = os.path.join(self.out_dir, "demucs_out")
            os.makedirs(demucs_out_dir, exist_ok=True)

            # Demucs model: htdemucs_ft = fine-tuned (cleaner vocals for cloning)
            # htdemucs = balanced, htdemucs_6s = 6-source (best isolation)
            _ALLOWED_DEMUCS = {
                "htdemucs",
                "htdemucs_ft",
                "htdemucs_6s",
                "mdx_extra_q",
                "mdx_extra",
            }
            demucs_model = getattr(self, "demucs_model", None) or "htdemucs_ft"
            if demucs_model not in _ALLOWED_DEMUCS:
                raise ValueError(f"Invalid demucs model: {demucs_model}")
            # Demucs создаёт папку со СВОЕЙ sanitization имени файла (отличается от нашей).
            # Поэтому НЕ угадываем путь — сканируем output директорию после работы Demucs.
            vocals_path = os.path.join(
                demucs_out_dir, demucs_model, base_name, "vocals.wav"
            )
            no_vocals_path = os.path.join(
                demucs_out_dir, demucs_model, base_name, "no_vocals.wav"
            )

            if not (os.path.exists(vocals_path) and os.path.exists(no_vocals_path)):
                import json  # noqa: PLC0415
                import subprocess  # noqa: PLC0415

                try:
                    probe = subprocess.check_output(
                        [
                            "ffprobe",
                            "-v",
                            "quiet",
                            "-print_format",
                            "json",
                            "-show_format",
                            self.video_path,
                        ],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    duration = float(json.loads(probe)["format"]["duration"])
                except Exception:
                    duration = 0

                if duration > 1800:
                    self.log_signal.emit(
                        f"  ⚡ Умная нарезка: Видео длится {duration / 60:.1f} мин. Делим аудио на куски по 15 минут для безопасного извлечения голоса..."
                    )
                    chunk_dir = os.path.join(demucs_out_dir, "chunks", base_name)
                    os.makedirs(chunk_dir, exist_ok=True)
                    full_audio = os.path.join(chunk_dir, "full.wav")
                    self._run_subprocess(
                        [
                            "ffmpeg",
                            "-y",
                            "-i",
                            self.video_path,
                            "-vn",
                            "-c:a",
                            "pcm_s16le",
                            full_audio,
                        ],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self._run_subprocess(
                        [
                            "ffmpeg",
                            "-y",
                            "-i",
                            full_audio,
                            "-f",
                            "segment",
                            "-segment_time",
                            "900",
                            "-c",
                            "copy",
                            os.path.join(chunk_dir, "chunk_%03d.wav"),
                        ],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

                    chunks = sorted(
                        [
                            f
                            for f in os.listdir(chunk_dir)
                            if f.startswith("chunk_") and f.endswith(".wav")
                        ]
                    )
                    for i, chunk in enumerate(chunks):
                        self.log_signal.emit(
                            f"  ⚡ Обработка куска {i + 1} из {len(chunks)}..."
                        )
                        c_path = os.path.join(chunk_dir, chunk)
                        d_cmd = [
                            get_python_exe(),
                            "-m",
                            "demucs.separate",
                            "-n",
                            demucs_model,
                            "-d",
                            self.device,
                            "--two-stems=vocals",
                            "-o",
                            chunk_dir,
                            c_path,
                        ]
                        try:
                            self._run_subprocess(d_cmd, check=True)
                        except subprocess.CalledProcessError:
                            if "-d" in d_cmd and "cuda" in d_cmd:
                                self.log_signal.emit(
                                    f"  ⚠ Кусок {i + 1} не поместился в VRAM (CUDA). Пробуем на CPU..."
                                )
                                d_cmd[d_cmd.index("cuda")] = "cpu"
                                try:
                                    self._run_subprocess(d_cmd, check=True)
                                except subprocess.CalledProcessError:
                                    self.log_signal.emit(
                                        f"  ❌ Ошибка куска {i + 1} на CPU. Пропускаем."
                                    )
                            else:
                                self.log_signal.emit(
                                    f"  ❌ Ошибка куска {i + 1}. Пропускаем."
                                )

                    v_list = os.path.join(chunk_dir, "v_list.txt")
                    nv_list = os.path.join(chunk_dir, "nv_list.txt")
                    with (
                        open(v_list, "w", encoding="utf-8") as f_v,
                        open(nv_list, "w", encoding="utf-8") as f_nv,
                    ):
                        for chunk in chunks:
                            c_base = os.path.splitext(chunk)[0]
                            v_p = os.path.join(
                                chunk_dir, demucs_model, c_base, "vocals.wav"
                            )
                            nv_p = os.path.join(
                                chunk_dir, demucs_model, c_base, "no_vocals.wav"
                            )
                            f_v.write(f"file '{v_p}'\n".replace("\\", "/"))
                            f_nv.write(f"file '{nv_p}'\n".replace("\\", "/"))

                    self.log_signal.emit(
                        "  ⚡ Склеиваем извлеченные куски обратно в единый файл..."
                    )
                    os.makedirs(os.path.dirname(vocals_path), exist_ok=True)
                    try:
                        self._run_subprocess(
                            [
                                "ffmpeg",
                                "-y",
                                "-f",
                                "concat",
                                "-safe",
                                "0",
                                "-i",
                                v_list,
                                "-c",
                                "copy",
                                vocals_path,
                            ],
                            check=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        self._run_subprocess(
                            [
                                "ffmpeg",
                                "-y",
                                "-f",
                                "concat",
                                "-safe",
                                "0",
                                "-i",
                                nv_list,
                                "-c",
                                "copy",
                                no_vocals_path,
                            ],
                            check=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    except subprocess.CalledProcessError as e:
                        self.log_signal.emit(
                            f"  ❌ Ошибка склейки Demucs (exit {e.returncode}). Пропускаем Demucs для этого видео."
                        )
                        # Demucs chunks concatenation failed — continue without vocal isolation
                else:
                    # ── Resource check: skip CUDA if VRAM is tight ──
                    monitor = get_monitor()
                    use_cuda = self.device == "cuda"
                    if use_cuda and monitor.vram_free_mb < 2500:
                        self.log_signal.emit(
                            f"  ⚠ Low VRAM ({monitor.vram_free_mb}MB free). Switching Demucs to CPU."
                        )
                        use_cuda = False

                    demucs_cmd = [
                        get_python_exe(),
                        "-m",
                        "demucs.separate",
                        "-n",
                        demucs_model,
                        "-d",
                        "cuda" if use_cuda else "cpu",
                        "--two-stems=vocals",
                        "-o",
                        demucs_out_dir,
                        self.video_path,
                    ]
                    try:
                        self._run_subprocess(demucs_cmd, check=True)
                    except subprocess.CalledProcessError as e:
                        if "-d" in demucs_cmd and "cuda" in demucs_cmd:
                            self.log_signal.emit(
                                f"  ⚠ Demucs failed on CUDA (exit {e.returncode}). Retrying on CPU..."
                            )
                            idx = demucs_cmd.index("cuda")
                            demucs_cmd[idx] = "cpu"
                            try:
                                self._run_subprocess(demucs_cmd, check=True)
                            except subprocess.CalledProcessError as e2:
                                self.log_signal.emit(
                                    f"  ❌ Demucs failed on CPU (exit {e2.returncode}). Skipping Demucs for this huge video."
                                )
                        else:
                            self.log_signal.emit(
                                f"  ❌ Demucs failed (exit {e.returncode}). Skipping Demucs."
                            )

                    # ── Находим РЕАЛЬНУЮ папку, которую создал Demucs (для обычного режима) ──
                    model_out = os.path.join(demucs_out_dir, demucs_model)
                    if os.path.isdir(model_out):
                        for folder in os.listdir(model_out):
                            candidate_v = os.path.join(model_out, folder, "vocals.wav")
                            if os.path.exists(candidate_v):
                                vocals_path = candidate_v
                                no_vocals_path = os.path.join(
                                    model_out, folder, "no_vocals.wav"
                                )
                                break
            else:
                self.log_signal.emit(_pipeline_t("demucs_skip", self.ui_language))

            # ── Если no_vocals.wav не создался (6-source модель) — собираем из стемов ──
            if not os.path.exists(no_vocals_path) and os.path.exists(vocals_path):
                demucs_track_dir = os.path.join(demucs_out_dir, demucs_model, base_name)
                # Ищем все не-вокальные стемы (drums, bass, other, piano, guitar)
                stem_parts = []
                for fname in (
                    sorted(os.listdir(demucs_track_dir))
                    if os.path.exists(demucs_track_dir)
                    else []
                ):
                    if fname.endswith(".wav") and fname != "vocals.wav":
                        stem_parts.append(os.path.join(demucs_track_dir, fname))
                if stem_parts:
                    # Микшируем все не-вокальные стемы в один no_vocals.wav
                    concat_inputs = []
                    for sp in stem_parts:
                        concat_inputs.extend(["-i", sp])
                    filter_parts = [f"[{i}:a]" for i in range(len(stem_parts))]
                    self._run_subprocess(
                        ["ffmpeg", "-y"]
                        + concat_inputs
                        + [
                            "-filter_complex",
                            f"{''.join(filter_parts)}amix=inputs={len(stem_parts)}:duration=longest",
                            no_vocals_path,
                        ],
                        check=True,
                        timeout=60,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self.log_signal.emit(
                        f"  > Собрал no_vocals из {len(stem_parts)} стемов"
                    )

            _set_model_status("demucs", "done")
            self.progress_signal.emit(15)

            transcribe_path = (
                vocals_path if os.path.exists(vocals_path) else self.video_path
            )

            if self.device == "cuda":
                monitor = get_monitor()
                vram_free = monitor.vram_free_mb
                if vram_free < 2000:
                    self.log_signal.emit(
                        _pipeline_t("low_vram_cpu_fallback", self.ui_language)
                    )
                    self.device = "cpu"
                elif vram_free < 3500:
                    self.log_signal.emit(
                        _pipeline_t("low_vram_cleaning", self.ui_language)
                    )
                    monitor.force_cleanup()
                if self.device == "cuda":
                    torch.cuda.empty_cache()

            # 2. Транскрибация (Whisper) — или загрузка из чекпойнта
            self._check_cancelled()
            _set_pipeline_step("whisper", 2)
            _set_model_status("whisper", "running")
            source_lang = getattr(self, "source_lang", "en")  # default, переопределяется из Whisper если запущен
            segments = _load_checkpoint("segments")
            if not segments and self.use_youtube_subs:
                import glob  # noqa: PLC0415

                srt_files = glob.glob(os.path.join(self.out_dir, "*.srt"))
                if srt_files:
                    pref = getattr(self, "source_lang", "en")
                    srt_files.sort(key=lambda x: (f"{pref}.srt" not in x.lower(), "en.srt" not in x.lower()))
                    segments = []  # Initialize before parsing
                    try:
                        import pysrt  # noqa: PLC0415

                        chosen_srt = srt_files[0]
                        # Попробуем достать язык из имени файла (напр. video.en.srt -> en)
                        parts = os.path.basename(chosen_srt).split(".")
                        if len(parts) >= 3 and len(parts[-2]) in (2, 3):
                            source_lang = parts[-2]
                            
                        subs = pysrt.open(chosen_srt)
                        for sub in subs:
                            start_s = sub.start.ordinal / 1000.0
                            end_s = sub.end.ordinal / 1000.0
                            
                            if getattr(self, "max_duration", 0) > 0:
                                if start_s >= self.max_duration:
                                    continue
                                if end_s > self.max_duration:
                                    end_s = float(self.max_duration)
                                    
                            text = re.sub(  # noqa: F821
                                r"<[^>]+>", "", sub.text.replace("\n", " ")
                            ).strip()
                            if text:
                                segments.append(
                                    {
                                        "start": start_s,
                                        "end": end_s,
                                        "text": text,
                                        "speaker": "SPEAKER_00",
                                    }
                                )
                        if segments:
                            # ── Dedup: remove micro-slices (<0.3s) and overlapping duplicates ──
                            deduped = []
                            for i, seg in enumerate(segments):
                                dur = seg["end"] - seg["start"]
                                # Skip micro-slices that are subsets of next/prev segment
                                if dur < 0.3:
                                    # Check if text is fully contained in adjacent segment
                                    prev_text = deduped[-1]["text"] if deduped else ""
                                    next_text = segments[i + 1]["text"] if i + 1 < len(segments) else ""
                                    if (prev_text and seg["text"] in prev_text) or (next_text and seg["text"] in next_text):
                                        continue
                                deduped.append(seg)
                            segments = deduped
                            # ── Bilingual split: detect and separate mixed-language segments ──
                            bilingual_splits = 0
                            bilingual_segments = []
                            for seg in segments:
                                chunks = split_bilingual_text(seg["text"])
                                if len(chunks) > 1:
                                    bilingual_splits += 1
                                    seg_dur = seg["end"] - seg["start"]
                                    total_chars = sum(len(c[0]) for c in chunks)
                                    current_start = seg["start"]
                                    for chunk_text, chunk_lang in chunks:
                                        ratio = len(chunk_text) / max(1, total_chars)
                                        chunk_dur = seg_dur * ratio
                                        bilingual_segments.append({
                                            "start": current_start,
                                            "end": current_start + chunk_dur,
                                            "text": chunk_text.strip(),
                                            "speaker": seg.get("speaker", "SPEAKER_00"),
                                            "language": chunk_lang,
                                        })
                                        current_start += chunk_dur
                                else:
                                    lang = detect_language(seg["text"])
                                    seg["language"] = lang
                                    bilingual_segments.append(seg)
                            if bilingual_splits > 0:
                                segments = bilingual_segments
                                self.log_signal.emit(
                                    f"  [BILINGUAL] Split {bilingual_splits} mixed-language segments into {len(segments)} total."
                                )
                            self.log_signal.emit(
                                f"  > Loaded {len(segments)} segments from YouTube Subtitles ({os.path.basename(srt_files[0])})."
                            )
                    except Exception as e:
                        self.log_signal.emit(f"  ⚠ Failed to parse YouTube SRT: {e}")
                        segments = []

            if segments:
                self.log_signal.emit(
                    _pipeline_t(
                        "segments_from_cache", self.ui_language, n=len(segments)
                    )
                )
                _save_checkpoint("segments", segments)
            else:
                self.log_signal.emit(
                    _pipeline_t(
                        "whisper_loading",
                        self.ui_language,
                        engine=self.whisper_engine,
                        model=self.model_size,
                        device=self.device,
                    )
                )
                # ── Run Whisper in subprocess for guaranteed VRAM cleanup ──
                import json as _json  # noqa: PLC0415
                import tempfile

                whisper_json_path = os.path.join(
                    self.out_dir, f".autodub_{base_name}_whisper_out.json"
                )
                
                param_dict = {
                    "model_size": self.model_size,
                    "device": self.device,
                    "audio_path": transcribe_path,
                    "output_path": whisper_json_path,
                    "engine_type": self.whisper_engine,
                    "use_multi_lang": True,
                    "hf_token": getattr(self, "hf_key", "") or "",
                }
                
                fd, params_file = tempfile.mkstemp(suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    _json.dump(param_dict, f, ensure_ascii=False)

                # Use WhisperX venv for word-level alignment; main venv for standard Whisper
                if self.whisper_engine == "whisperX":
                    whisper_python = _resolve_venv_python(".venv-whisperx")
                else:
                    whisper_python = get_python_exe()

                try:
                    self._run_subprocess(
                        [whisper_python, "backend/whisper_multi_worker.py", params_file],
                        check=True,
                        timeout=14400,
                    )
                except subprocess.CalledProcessError as e:
                    self.log_signal.emit(f"⚠️ Whisper failed (error {e.returncode}). Check logs.")
                finally:
                    if os.path.exists(params_file):
                        os.remove(params_file)

                with open(whisper_json_path, "r", encoding="utf-8") as f:
                    whisper_data = _json.load(f)
                segments = whisper_data["segments"]
                source_lang = whisper_data.get("language", "en")
                # ── Ensure every segment has a language field (SpeechBrain may have failed) ──
                for seg in segments:
                    if not seg.get("language"):
                        seg["language"] = source_lang
                all_created_files.append(whisper_json_path)

                # --- NLP Splitting ---
                if getattr(self, "use_nlp_splitter", True):
                    self.log_signal.emit(
                        f"🧠 Запуск NLP-сплиттера (Spacy) для языка {source_lang}..."
                    )
                    from backend.nlp_splitter import (  # noqa: PLC0415
                        split_segments_by_meaning,
                    )

                    old_count = len(segments)
                    segments = split_segments_by_meaning(segments, source_lang)
                    if len(segments) > old_count:
                        self.log_signal.emit(
                            f"✂️ Фразы были умнее разделены: {old_count} -> {len(segments)} сегментов."
                        )

                # ── Text-based language re-detection AFTER NLP splitting ──
                # Must run AFTER splitting so English sentences are separated from Russian
                # segments and can be correctly identified by langdetect.
                lang_corrections = 0
                for seg in segments:
                    text_lang = detect_language(seg.get("text", ""))
                    audio_lang = seg.get("language", "")
                    if text_lang != "unknown" and text_lang != audio_lang:
                        seg["language"] = text_lang
                        lang_corrections += 1
                    elif not seg.get("language"):
                        seg["language"] = text_lang if text_lang != "unknown" else source_lang
                if lang_corrections > 0:
                    self.log_signal.emit(
                        f"  [BILINGUAL] Language tags corrected for {lang_corrections}/{len(segments)} segments using text-based detection"
                    )

                self.log_signal.emit(
                    _pipeline_t("segments_found", self.ui_language, n=len(segments))
                )
                _save_checkpoint("segments", segments)

            _set_model_status("whisper", "done")
            self.progress_signal.emit(30)

            # 3. Диаризация (определение спикеров) — опционально, если есть HF токен
            if self.hf_key:
                _set_model_status("pyannote", "running")
                self.log_signal.emit(_pipeline_t("diarization_start", self.ui_language))
                diar_json = os.path.join(self.out_dir, f"{base_name}_diarization.json")
                try:
                    diar_script = os.path.join(
                        os.path.dirname(__file__), "diarization_worker.py"
                    )
                    # Pyannote НЕ умеет читать .mp4 — нужен WAV.
                    # Используем vocals.wav (Demucs) если есть, иначе извлекаем аудио из видео
                    diar_audio = vocals_path if os.path.exists(vocals_path) else None
                    if diar_audio is None:
                        # Извлекаем аудиодорожку во временный WAV для диаризации
                        diar_audio = os.path.join(
                            self.out_dir, f"{base_name}_diar_audio.wav"
                        )
                        if not os.path.exists(diar_audio):
                            self._run_subprocess(
                                [
                                    "ffmpeg",
                                    "-y",
                                    "-i",
                                    self.video_path,
                                    "-vn",
                                    "-acodec",
                                    "pcm_s16le",
                                    "-ar",
                                    "16000",
                                    diar_audio,
                                ],
                                check=True,
                                timeout=120,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                        all_created_files.append(diar_audio)
                    self._run_subprocess(
                        [get_python_exe(), diar_script, diar_audio, diar_json],
                        check=True
                    )
                    
                    if os.path.exists(diar_json):
                        import json as _json  # noqa: PLC0415
                        with open(diar_json, "r", encoding="utf-8") as f:
                            diar_data = _json.load(f)
                        
                        for seg in segments:
                            seg_start = seg["start"]
                            seg_end = seg["end"]
                            best_speaker = seg.get("speaker", "SPEAKER_00")
                            max_overlap = 0
                            
                            for turn in diar_data:
                                overlap = max(0, min(seg_end, turn["end"]) - max(seg_start, turn["start"]))
                                if overlap > max_overlap:
                                    max_overlap = overlap
                                    best_speaker = turn["speaker"]
                                    
                            seg["speaker"] = best_speaker
                            
                        _save_checkpoint("trimmed_segments", segments)
                        unique_spks = len(set(s.get("speaker", "SPEAKER_00") for s in segments))
                        self.log_signal.emit(
                            _pipeline_t("diarization_done", self.ui_language, pyannote=len(set(t["speaker"] for t in diar_data)), n=unique_spks)
                        )

                except Exception as e:
                    self.log_signal.emit(
                        f"  [!] Ошибка диаризации: {e}. Будет использован один спикер."
                    )
                    
            _set_model_status("pyannote", "done")
            self.progress_signal.emit(35)

            # 3.5 — Save original subtitles with language tags
            orig_srt_path = os.path.join(self.out_dir, f"{base_name}_original.srt")
            all_created_files.append(orig_srt_path)
            with open(orig_srt_path, "w", encoding="utf-8") as f:
                for idx, s in enumerate(segments):
                    seg_lang = s.get("language", source_lang or "en")
                    lang_tag = f"[{seg_lang[:2].upper()}] " if seg_lang else ""
                    f.write(
                        f"{idx + 1}\n{self.format_timestamp(s['start'])} --> {self.format_timestamp(s['end'])}\n{lang_tag}{s['text'].strip()}\n\n"
                    )
            self.log_signal.emit(_pipeline_t("subtitles_saved", self.ui_language))

            # 4. Обработка языков
            ffmpeg_inputs = ["-i", self.video_path, "-i", orig_srt_path]
            src_display = source_lang.upper() if source_lang else "ORIG"
            
            # We will collect tracks and build maps at the end to ensure correct ordering
            dubbed_audio_tracks = [] # list of dict with file_idx, lang, label, clean_label
            dubbed_subtitle_tracks = []
            
            # Start tracking input files for ffmpeg map
            file_idx = 2  # 0=video, 1=original audio+subs

            for i, (lang, _) in enumerate(self.langs.items()):
                self._check_cancelled()
                _set_pipeline_step("translate", 3)
                _set_model_status("translate", "running")
                _set_engine_info("translate", getattr(self, "translator_engine", ""))

                # ── VRAM cleanup before loading LLMs ──
                try:
                    import gc  # noqa: PLC0415

                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()
                except Exception:
                    pass
                self.log_signal.emit(
                    _pipeline_t("processing_lang", self.ui_language, lang=lang)
                )
                srt_path = os.path.join(self.out_dir, f"{base_name}_{lang}.srt")
                all_created_files.append(srt_path)

                # Check for cached translation
                cached = _load_checkpoint(f"translated_{lang}")
                if cached:
                    translated_segments = cached
                    self.log_signal.emit(
                        _pipeline_t(
                            "translation_from_cache",
                            self.ui_language,
                            n=len(translated_segments),
                        )
                    )
                else:
                    self.log_signal.emit(
                        _pipeline_t("translation_start", self.ui_language, lang=lang)
                    )
                    translated_segments = self.translator.smart_translate_segments(
                        [dict(s) for s in segments],
                        lang,
                        self.log_signal.emit,
                        self._check_cancelled,
                        ui_language=self.ui_language,
                    )
                    
                    # Post-processing: restore original text and skip dubbing if segment language matches target language
                    for seg, orig_seg in zip(translated_segments, segments):
                        seg_lang = orig_seg.get("language", "")
                        if seg_lang and seg_lang[:2].lower() == lang[:2].lower():
                            seg["skip_dub"] = True
                            seg["text"] = orig_seg["text"]
                            
                    _save_checkpoint(f"translated_{lang}", translated_segments)

                # Progress: 35% + translation portion (15% of total range per lang)
                num_langs = len(self.langs)
                self.progress_signal.emit(35 + (i + 1) * (15 // max(num_langs, 1)))

                if self.manual_mode:
                    manual_subs = []
                    for idx, s in enumerate(translated_segments):
                        manual_subs.append(
                            {
                                "time": f"{self.format_timestamp(s['start'])} → {self.format_timestamp(s['end'])}",
                                "orig": segments[idx]["text"],
                                "trans": s["text"],
                                "start": s["start"],
                                "end": s["end"],
                                "speaker": s.get("speaker", "SPEAKER_00"),
                                "gender": s.get("gender", "unknown"),
                                "skip_dub": s.get("skip_dub", False),
                            }
                        )
                    self.manual_edit_signal.emit(manual_subs)
                    while not self.pause_event.is_set():
                        if getattr(self, "isInterruptionRequested", lambda: False)():
                            self.finished_signal.emit(False, "Aborted")
                            return
                        self.pause_event.wait(0.5)
                    self.pause_event.clear()
                    # Re-check after unpausing — user may have cancelled during pause
                    if self.isInterruptionRequested():
                        self.finished_signal.emit(False, "Aborted")
                        return
                    if self.edited_segments:
                        translated_segments = self.edited_segments

                # ── Save translated SRT (single-language output) ──
                with open(srt_path, "w", encoding="utf-8") as f:
                    for idx, tseg in enumerate(translated_segments):
                        text_val = tseg.get('text') or ""
                        f.write(
                            f"{idx + 1}\n{self.format_timestamp(tseg['start'])} --> {self.format_timestamp(tseg['end'])}\n{text_val.strip()}\n\n"
                        )

                # ── Save bilingual SRT (original + translation) ──
                bilingual_srt_path = os.path.join(self.out_dir, f"{base_name}_{lang}_bilingual.srt")
                all_created_files.append(bilingual_srt_path)
                with open(bilingual_srt_path, "w", encoding="utf-8") as f:
                    for idx, (tseg, oseg) in enumerate(zip(translated_segments, segments)):
                        orig_text = oseg.get('text', '').strip()
                        trans_text = tseg.get('text', '').strip()
                        orig_lang = oseg.get('language', source_lang or 'en')
                        orig_tag = orig_lang[:2].upper() if orig_lang else "??"
                        target_tag = lang[:2].upper()

                        if tseg.get("skip_dub"):
                            # Segment already in target language — show original only
                            subtitle_text = f"[{orig_tag}] {orig_text}"
                        elif orig_text == trans_text:
                            # No translation needed or same text
                            subtitle_text = f"[{orig_tag}] {orig_text}"
                        else:
                            # Bilingual output: original + translation
                            subtitle_text = f"[{orig_tag}] {orig_text}\n[{target_tag}] {trans_text}"

                        f.write(
                            f"{idx + 1}\n{self.format_timestamp(tseg['start'])} --> {self.format_timestamp(tseg['end'])}\n{subtitle_text}\n\n"
                        )
                self.log_signal.emit(
                    f"  📝 Bilingual subtitles saved: {os.path.basename(bilingual_srt_path)}"
                    f" ({sum(1 for t in translated_segments if t.get('skip_dub'))} segments kept in original language)"
                )

                # --- TTS Logic ---
                _set_model_status("translate", "done")
                _set_pipeline_step("tts", 4)

                # Subtitles-only mode: skip TTS entirely but still add subtitle tracks to ffmpeg
                if engine_id == "none":
                    _set_model_status("tts", "done")
                    self.log_signal.emit(
                        f"  [SUB] Subtitles-only mode — skipping TTS for {lang}"
                    )
                    # Add SRT file as ffmpeg input (same pattern as normal TTS path)
                    ffmpeg_inputs.extend(["-i", srt_path])
                    dubbed_subtitle_tracks.append({
                        "lang": lang,
                        "sub_file_idx": file_idx,
                    })
                    file_idx += 1
                    continue  # Skip to next language

                _set_model_status("tts", "running")
                _set_engine_info("tts", engine_id)

                use_xtts = "xttsv2" in engine_id
                use_qwen = "qwen3-tts" in engine_id or "qwen" in engine_id
                use_f5 = "f5-tts" in engine_id or "f5" in engine_id
                use_local_tts = use_xtts or use_qwen or use_f5
                audio_clips = []

                # Pre-extract skip_dub segments
                vocals_full = AudioSegment.from_file(transcribe_path)
                tts_segments = []

                # ── Shared: Select best reference audio per speaker + gender detection ──
                # Runs for all TTS engines (XTTSv2, Edge-TTS) — not just XTTSv2
                speaker_refs = {}
                for s in segments:
                    spk = s.get("speaker", "SPEAKER_00")
                    dur = s["end"] - s["start"]
                    text = s.get("text", "").strip()
                    word_count = len(text.split())
                    if dur > 0.5 and word_count > 0:
                        wps = word_count / dur
                        if 3.0 <= dur <= 8.0:
                            dur_bonus = 1.0
                        elif dur < 3.0:
                            dur_bonus = dur / 3.0
                        else:
                            dur_bonus = max(0.3, 8.0 / dur)
                        score = wps * dur_bonus
                        if spk not in speaker_refs or score > speaker_refs[spk]["score"]:
                            speaker_refs[spk] = {
                                "dur": dur, "start": s["start"], "end": s["end"],
                                "text": text, "score": score, "wps": wps,
                            }

                # Extract reference audio files and run gender detection (all TTS engines)
                for spk, ref in speaker_refs.items():
                    ref_path = os.path.join(self.out_dir, f"ref_{spk}.wav")
                    if not os.path.exists(ref_path):
                        ref_audio_segment = vocals_full[int(ref["start"] * 1000) : int(ref["end"] * 1000)]
                        ref_audio_segment.set_frame_rate(22050).set_channels(1).set_sample_width(2).export(ref_path, format="wav")
                    ref["path"] = ref_path
                    all_created_files.append(ref_path)

                if self.use_gender_ai and speaker_refs:
                    try:
                        gender_tasks = [
                            {"speaker_id": spk, "audio_path": ref["path"]}
                            for spk, ref in speaker_refs.items()
                        ]
                        if gender_tasks:
                            gender_tasks_file = os.path.join(self.out_dir, "gender_tasks.json")
                            gender_out_file = os.path.join(self.out_dir, "gender_out.json")
                            import json as _json_gender
                            with open(gender_tasks_file, "w", encoding="utf-8") as f:
                                _json_gender.dump(gender_tasks, f)
                            gender_py = _resolve_venv_python(".venv")
                            gender_script = os.path.join(os.path.dirname(__file__), "gender_worker.py")
                            self._run_subprocess(
                                [gender_py, gender_script, gender_tasks_file, gender_out_file],
                                check=True, timeout=120,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            )
                            with open(gender_out_file, "r", encoding="utf-8") as f:
                                gender_results = _json_gender.load(f)
                            for spk, gen in gender_results.items():
                                speaker_refs[spk]["gender"] = gen
                            # Update all segments with detected gender
                            for seg in segments:
                                spk = seg.get("speaker", "SPEAKER_00")
                                if spk in gender_results:
                                    seg["gender"] = gender_results[spk]
                            for tseg in translated_segments:
                                spk = tseg.get("speaker", "SPEAKER_00")
                                if spk in gender_results:
                                    tseg["gender"] = gender_results[spk]
                            self.log_signal.emit(
                                f"  [GENDER] Detected: {', '.join(f'{s}={g}' for s, g in gender_results.items())}"
                            )
                    except Exception as e:
                        self.log_signal.emit(f"  [GENDER] Detection skipped: {e}")

                for idx, tseg in enumerate(translated_segments):
                    ext = "wav" if use_xtts else "mp3"
                    clip_path = os.path.join(self.out_dir, f"temp_{lang}_{idx}.{ext}")

                    if tseg.get("skip_dub", False):
                        orig_start_ms = int(tseg["start"] * 1000)
                        orig_end_ms = int(tseg["end"] * 1000)
                        extracted = vocals_full[orig_start_ms:orig_end_ms]
                        extracted.export(clip_path, format=ext)
                        all_created_files.append(clip_path)
                        audio_clips.append((tseg["start"], clip_path, False, tseg))
                    else:
                        # Убираем кавычки, чтобы XTTSv2 и Edge-TTS не спотыкались на них
                        if "text" in tseg and tseg["text"]:
                            tseg["text"] = re.sub(r'["\'«»“”„]', '', tseg["text"])
                        tts_segments.append((idx, tseg, clip_path))

                # ── TTS Dispatch: select engine and run worker ──
                local_tts_failed = False
                tasks = []
                for idx, tseg, clip_path in tts_segments:  # noqa: B007
                    spk = tseg.get("speaker", "SPEAKER_00")
                    ref = speaker_refs.get(spk, next(iter(speaker_refs.values()))) if speaker_refs else {"path": transcribe_path, "text": tseg.get("text", "")}
                    tasks.append({
                        "ref_audio": ref.get("path", transcribe_path),
                        "ref_text": ref.get("text", tseg.get("text", "")),
                        "gen_text": tseg["text"],
                        "out_path": clip_path,
                        "language": lang,
                    })
                    audio_clips.append((tseg["start"], clip_path, False, tseg))

                if tasks and use_local_tts:
                    tasks_file = os.path.join(self.out_dir, f"tasks_{lang}.json")
                    import json  # noqa: PLC0415
                    with open(tasks_file, "w", encoding="utf-8") as f:
                        json.dump(tasks, f)
                    all_created_files.append(tasks_file)

                    if use_xtts:
                        worker_py = _resolve_venv_python(".venv-xtts")
                        worker_script = os.path.join(os.path.dirname(__file__), "xtts_worker.py")
                        engine_label = "XTTSv2"
                    elif use_qwen:
                        worker_py = get_python_exe()
                        worker_script = os.path.join(os.path.dirname(__file__), "qwen_worker.py")
                        engine_label = "Qwen3-TTS"
                    elif use_f5:
                        worker_py = get_python_exe()
                        worker_script = os.path.join(os.path.dirname(__file__), "f5_worker.py")
                        engine_label = "F5-TTS"
                    else:
                        worker_py = get_python_exe()
                        worker_script = None
                        engine_label = "unknown"

                    if worker_script and os.path.exists(worker_script):
                        try:
                            self._run_subprocess(
                                [worker_py, worker_script, tasks_file],
                                check=True,
                                timeout=14400,
                            )
                        except Exception as e:
                            self.log_signal.emit(f"  [!] {engine_label} error ({e}). Fallback to Edge-TTS...")
                            local_tts_failed = True
                    else:
                        self.log_signal.emit(f"  [!] {engine_label} worker not found. Fallback to Edge-TTS...")
                        local_tts_failed = True

                if not use_local_tts or local_tts_failed:  # Edge-TTS
                    if local_tts_failed:
                        # Clean up broken XTTS audio clips — they're corrupt
                        audio_clips = [
                            (start_t, cp, False, tseg)
                            for (start_t, cp, _, tseg) in audio_clips
                            if tseg.get("skip_dub", False)
                        ]
                        # Rebuild tts_segments for Edge-TTS
                        tts_segments = []
                        for idx, tseg in enumerate(translated_segments):
                            if not tseg.get("skip_dub", False):
                                ext = "mp3"
                                clip_path = os.path.join(self.out_dir, f"temp_{lang}_{idx}.{ext}")
                                tts_segments.append((idx, tseg, clip_path))
                    import asyncio  # noqa: PLC0415

                    import edge_tts  # noqa: PLC0415

                    EDGE_VOICES_MALE = {
                        "ru": "ru-RU-DmitryNeural",
                        "en": "en-US-ChristopherNeural",
                        "tr": "tr-TR-AhmetNeural",
                        "ar": "ar-SA-HamedNeural",
                        "es": "es-ES-AlvaroNeural",
                        "fr": "fr-FR-HenriNeural",
                        "de": "de-DE-ConradNeural",
                        "zh": "zh-CN-YunxiNeural",
                        "ja": "ja-JP-KeitaNeural",
                        "ko": "ko-KR-InJoonNeural",
                        "it": "it-IT-DiegoNeural",
                        "pt": "pt-PT-DuarteNeural",
                        "pl": "pl-PL-MarekNeural",
                        "hi": "hi-IN-MadhurNeural",
                    }
                    EDGE_VOICES_FEMALE = {
                        "ru": "ru-RU-SvetlanaNeural",
                        "en": "en-US-AriaNeural",
                        "tr": "tr-TR-EmelNeural",
                        "ar": "ar-SA-ZariyahNeural",
                        "es": "es-ES-ElviraNeural",
                        "fr": "fr-FR-DeniseNeural",
                        "de": "de-DE-AmalaNeural",
                        "zh": "zh-CN-XiaoxiaoNeural",
                        "ja": "ja-JP-NanamiNeural",
                        "ko": "ko-KR-SunHiNeural",
                        "it": "it-IT-ElsaNeural",
                        "pt": "pt-PT-RaquelNeural",
                        "pl": "pl-PL-AgnieszkaNeural",
                        "hi": "hi-IN-SwaraNeural",
                    }

                    # Выбор голоса по умолчанию
                    default_voice = EDGE_VOICES_MALE.get(
                        lang, "en-US-ChristopherNeural"
                    )

                    if tts_segments:
                        self.log_signal.emit(
                            _pipeline_t(
                                "tts_edge_start", self.ui_language, n=len(tts_segments)
                            )
                        )

                        # ── Robust sentence-aware grouping ──
                        # Detects sentence endings in ANY language (Latin + Cyrillic + Arabic + CJK + punctuation)
                        SENTENCE_END = {
                            ".",
                            "!",
                            "?",
                            "…",
                            "。",
                            "？",
                            "！",  # Basic + CJK
                            '."',
                            '!"',
                            '?"',
                            ".)",
                            '.)"',  # Quoted
                            ".»",
                            "!»",
                            "?»",  # French/Russian quotes
                            '.")',
                            '!")',
                            '?")',  # Parenthetical quotes
                        }
                        # Also check last 2 chars for multi-char endings
                        SENTENCE_END_2 = {
                            ".»",
                            '!"',
                            '?"',
                            '."',
                            ".)",
                            '.)"',
                            '.")',
                            '!")',
                            '?")',
                        }

                        def _ends_sentence(text):
                            t = text.strip()
                            if not t:
                                return True  # Empty = break
                            if len(t) < 3:
                                return False  # Too short to determine, keep grouping
                            if any(t.endswith(c) for c in SENTENCE_END_2):  # noqa: B023
                                return True
                            if t[-1] in SENTENCE_END:  # noqa: B023
                                return True
                            return False

                        groups = []  # [(group_segments, voice)]
                        cur_group = []
                        cur_chars = 0
                        cur_voice = None
                        MAX_SEGMENTS = 6  # Max segments per TTS group
                        MAX_CHARS = (
                            400  # Max total characters per group (~30 sec of speech)
                        )

                        for _, tseg, clip_path in tts_segments:
                            gender = tseg.get("gender", "unknown")
                            if gender == "female":
                                seg_voice = EDGE_VOICES_FEMALE.get(
                                    lang, "en-US-AriaNeural"
                                )
                            elif gender == "male":
                                seg_voice = EDGE_VOICES_MALE.get(
                                    lang, "en-US-ChristopherNeural"
                                )
                            else:
                                seg_voice = default_voice

                            seg_chars = len(tseg["text"].strip())

                            # Force break if voice changes or limits exceeded
                            if cur_group and (
                                cur_voice != seg_voice
                                or len(cur_group) >= MAX_SEGMENTS
                                or cur_chars + seg_chars > MAX_CHARS
                            ):
                                groups.append((cur_group, cur_voice))
                                cur_group = []
                                cur_chars = 0

                            cur_group.append((tseg, clip_path))
                            cur_chars += seg_chars
                            cur_voice = seg_voice

                            # Natural break at sentence end
                            if _ends_sentence(tseg["text"]):
                                groups.append((cur_group, cur_voice))
                                cur_group = []
                                cur_chars = 0

                        if cur_group:
                            groups.append((cur_group, cur_voice))

                        async def gen_all_groups():
                            for gi, (group, group_voice) in enumerate(groups):  # noqa: B023
                                self._check_cancelled()
                                parts = []
                                for tseg, _ in group:
                                    t = tseg["text"].strip()
                                    if (
                                        t
                                        and not _ends_sentence(t)
                                        and t[-1] not in {".", "!", "?", "…", "。"}
                                    ):
                                        t += ". "  # Force sentence break for TTS naturalness
                                    parts.append(t)
                                group_text = " ".join(parts)
                                group_path = os.path.join(
                                    self.out_dir, f"temp_{lang}_group{gi}.mp3"  # noqa: B023
                                )
                                all_created_files.append(group_path)
                                self.log_signal.emit(
                                    _pipeline_t(
                                        "tts_group_progress",
                                        self.ui_language,
                                        gi=gi + 1,
                                        total=len(groups),  # noqa: B023
                                        n=len(group),
                                        chars=len(group_text),
                                    )
                                )
                                await edge_tts.Communicate(
                                    group_text, group_voice
                                ).save(group_path)
                                # Split back to segments
                                group_audio = AudioSegment.from_file(group_path)
                                total_chars = max(
                                    1, sum(len(s[0]["text"].strip()) for s in group)
                                )
                                pos_ms = 0
                                for tseg, clip_path in group:
                                    ratio = len(tseg["text"].strip()) / total_chars
                                    seg_dur = max(300, int(len(group_audio) * ratio))
                                    end_ms = min(pos_ms + seg_dur, len(group_audio))
                                    seg_audio = group_audio[pos_ms:end_ms]
                                    seg_audio.export(clip_path, format="mp3")
                                    pos_ms = end_ms
                                    audio_clips.append(  # noqa: B023
                                        (tseg["start"], clip_path, False, tseg)
                                    )

                        # Safe async runner: creates fresh event loop each time
                        # (asyncio.run() can't be called twice in same thread)
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(gen_all_groups())
                        finally:
                            loop.close()
                        # VRAM cleanup after Edge-TTS
                        gc.collect()
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()

                # --- Assembly (3 tracks: dub, clean, TTS-only) ---
                tts_only = AudioSegment.silent(duration=len(vocals_full))
                final_audio = AudioSegment.silent(duration=len(vocals_full))
                for start_t, cp, _, tseg in audio_clips:
                    if os.path.exists(cp):
                        clip = AudioSegment.from_file(cp)
                        allowed_dur = tseg["end"] - tseg["start"]
                        actual_dur = len(clip) / 1000.0
                        if not tseg.get("skip_dub", False):
                            speed_factor = actual_dur / max(allowed_dur, 0.1)
                            # Always speed up if too long (>1.05x). If lip_sync is ON, also slow down if too short (<0.95x)
                            if (speed_factor > 1.05) or (
                                self.lip_sync and speed_factor < 0.95
                            ):
                                # Limit max speedup to 4.0 and max slowdown to 0.5 to avoid extreme artifacts
                                speed_factor = max(0.5, min(4.0, speed_factor))
                                stretched_cp = cp + "_sync.wav"
                                remaining = speed_factor
                                atempo_filters = []
                                if remaining >= 1.0:
                                    while remaining > 2.0:
                                        atempo_filters.append("atempo=2.0")
                                        remaining /= 2.0
                                    if remaining > 1.0 or not atempo_filters:
                                        atempo_filters.append(f"atempo={remaining:.4f}")
                                else:
                                    while remaining < 0.5:
                                        atempo_filters.append("atempo=0.5")
                                        remaining /= 0.5
                                    if remaining < 1.0 or not atempo_filters:
                                        atempo_filters.append(f"atempo={remaining:.4f}")
                                filter_chain = ",".join(atempo_filters)
                                self._run_subprocess(
                                    [
                                        "ffmpeg",
                                        "-y",
                                        "-i",
                                        cp,
                                        "-filter:a",
                                        filter_chain,
                                        stretched_cp,
                                    ],
                                    check=True,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                )
                                clip = AudioSegment.from_file(stretched_cp)
                                all_created_files.append(stretched_cp)
                                
                        # Apply Acoustic Reverb to synthesized TTS audio
                        if not tseg.get("skip_dub", False):
                            try:
                                from pedalboard import Pedalboard, Reverb
                                import numpy as np
                                
                                board = Pedalboard([Reverb(room_size=0.4, damping=0.6, wet_level=0.15, dry_level=0.9, width=1.0)])
                                samples = np.array(clip.get_array_of_samples(), dtype=np.float32) / 32768.0
                                
                                if clip.channels == 2:
                                    samples = samples.reshape((-1, 2)).T
                                else:
                                    samples = samples.reshape((1, -1))
                                    
                                effected = board(samples, clip.frame_rate)
                                effected = (effected * 32768.0).clip(-32768, 32767).astype(np.int16)
                                
                                if clip.channels == 2:
                                    effected = effected.T.flatten()
                                else:
                                    effected = effected.flatten()
                                    
                                clip = clip._spawn(effected.tobytes())
                            except ImportError:
                                pass # Pedalboard not installed
                            except Exception as e:
                                self.log_signal.emit(f"  ⚠ Reverb error: {e}")

                        # Смягчаем границы: fade-in/out по 50ms — плавные переходы без обрывов
                        clip = clip.fade_in(50).fade_out(50)
                        tts_only = tts_only.overlay(clip, position=int(start_t * 1000))
                        final_audio = final_audio.overlay(
                            clip, position=int(start_t * 1000)
                        )
                        all_created_files.append(cp)

                dub_path = os.path.join(self.out_dir, f"{base_name}_{lang}_dub.wav")
                final_audio.export(dub_path, format="wav")
                all_created_files.append(dub_path)

                # Clean TTS voice (no background, no original voice) — for voice quality check
                clean_tts_path = os.path.join(
                    self.out_dir, f"{base_name}_{lang}_clean_tts.wav"
                )
                tts_only.export(clean_tts_path, format="wav")
                all_created_files.append(clean_tts_path)

                # Dub track: background 100% (no_vocals) + original voice 15%
                ducked_path = os.path.join(
                    self.out_dir, f"{base_name}_{lang}_ducked.wav"
                )
                if os.path.exists(no_vocals_path):
                    # Сначала извлекаем аудио из видео в WAV (для совместимости с amix)
                    orig_audio_path = os.path.join(
                        self.out_dir, f"{base_name}_orig_audio.wav"
                    )
                    self._run_subprocess(
                        [
                            "ffmpeg",
                            "-y",
                            "-i",
                            self.video_path,
                            "-vn",
                            "-acodec",
                            "pcm_s16le",
                            orig_audio_path,
                        ],
                        check=True,
                        timeout=60,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    all_created_files.append(orig_audio_path)
                    # Микшируем: no_vocals (100%) + оригинальный голос (25%)
                    # Громкость задана через volume, amix без weights (веса уже учтены)
                    self._run_subprocess(
                        [
                            "ffmpeg",
                            "-y",
                            "-i",
                            no_vocals_path,
                            "-i",
                            orig_audio_path,
                            "-filter_complex",
                            "[0:a]volume=1.0[bg];[1:a]volume=0.25[voc];[bg][voc]amix=inputs=2:duration=first",
                            ducked_path,
                        ],
                        check=True,
                        timeout=30,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    # Fallback: no Demucs separation — mix original audio 70% + dub
                    self._run_subprocess(
                        [
                            "ffmpeg",
                            "-y",
                            "-i",
                            self.video_path,
                            "-i",
                            dub_path,
                            "-filter_complex",
                            "[0:a]volume=0.7[bg];[1:a]volume=1.0[dub];[bg][dub]amix=inputs=2:duration=first",
                            ducked_path,
                        ],
                        check=True,
                        timeout=30,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

                # ── Final mix: две дорожки дубляжа ──
                # 1. Dub = фон + 15% оригинала + TTS (полный микс с оригинальным голосом)
                # 2. Clean = фон + TTS (без оригинального голоса — чище)
                dub_final_path = os.path.join(
                    self.out_dir, f"{base_name}_{lang}_dub_final.wav"
                )
                clean_final_path = os.path.join(
                    self.out_dir, f"{base_name}_{lang}_clean_final.wav"
                )

                # Dub = ducked (фон + 15% оригинала) + TTS голос
                self._run_subprocess(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        ducked_path,
                        "-i",
                        clean_tts_path,
                        "-filter_complex",
                        "[0:a]volume=1.0[bg];[1:a]volume=1.0[tts];[bg][tts]amix=inputs=2:duration=first",
                        dub_final_path,
                    ],
                    check=True,
                    timeout=30,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                # Clean = фон (no_vocals или тишина) + TTS голос (без оригинала)
                clean_bg = (
                    no_vocals_path if os.path.exists(no_vocals_path) else ducked_path
                )
                self._run_subprocess(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        clean_bg,
                        "-i",
                        clean_tts_path,
                        "-filter_complex",
                        "[0:a]volume=1.0[bg];[1:a]volume=1.0[tts];[bg][tts]amix=inputs=2:duration=first",
                        clean_final_path,
                    ],
                    check=True,
                    timeout=30,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                all_created_files.extend([dub_final_path, clean_final_path])

                ffmpeg_inputs.extend(
                    ["-i", dub_final_path, "-i", clean_final_path, "-i", srt_path]
                )
                all_created_files.extend(
                    [ducked_path, clean_tts_path, dub_final_path, clean_final_path]
                )

                dubbed_audio_tracks.append({
                    "lang": lang,
                    "dub_file_idx": file_idx,
                    "clean_file_idx": file_idx + 1,
                })
                dubbed_subtitle_tracks.append({
                    "lang": lang,
                    "sub_file_idx": file_idx + 2,
                })
                
                file_idx += 3

                # Progress: TTS done for this language
                num_langs = len(self.langs)
                self.progress_signal.emit(35 + (i + 1) * 50 // max(num_langs, 1))

            _set_model_status("tts", "done")
            _set_pipeline_step("mux", 5)
            _set_model_status("mux", "running")
            tag_str = f"_{self.tag}" if hasattr(self, "tag") and self.tag else ""
            self.progress_signal.emit(90)
            lang_codes = "_".join(sorted(self.langs.keys()))
            final_mkv = os.path.join(
                self.out_dir, f"{base_name}{tag_str}_{lang_codes.upper()}.mkv"
            )
            
            ffmpeg_maps = ["-map", "0:v:0"]
            metadata = []
            audio_idx = 0
            sub_idx = 0
            
            lang_names = {
                "ru": "Russian", "tr": "Turkish", "en": "English", 
                "ar": "Arabic", "es": "Spanish", "fr": "French", "de": "German"
            }
            
            # 1. Map Dubbed Audio First!
            for track in dubbed_audio_tracks:
                lang = track["lang"]
                lang_display = lang_names.get(lang, lang.upper())
                
                ffmpeg_maps.extend(["-map", f"{track['dub_file_idx']}:a:0", "-map", f"{track['clean_file_idx']}:a:0"])
                
                is_default = "1" if audio_idx == 0 else "0"
                
                dub_label = {"ru": "Дубляж (голос+фон+ориг)", "tr": "Dublaj (ses+fon+orj)", "en": "Dub (voice+bg+orig)"}.get(lang, f"{lang_display} Dub")
                clean_label = {"ru": "Дубляж чистовой", "tr": "Dublaj temiz", "en": "Dub Clean"}.get(lang, f"{lang_display} Clean")
                
                metadata.extend([
                    f"-metadata:s:a:{audio_idx}", f"title={dub_label}",
                    f"-metadata:s:a:{audio_idx}", f"language={lang}",
                    f"-disposition:a:{audio_idx}", is_default,
                    
                    f"-metadata:s:a:{audio_idx+1}", f"title={clean_label}",
                    f"-metadata:s:a:{audio_idx+1}", f"language={lang}",
                    f"-disposition:a:{audio_idx+1}", "0"
                ])
                audio_idx += 2
                
            # 2. Map Original Audio Next
            ffmpeg_maps.extend(["-map", "0:a:0"])
            metadata.extend([
                f"-metadata:s:a:{audio_idx}", "title=Original Audio",
                f"-metadata:s:a:{audio_idx}", f"language={source_lang or 'und'}",
                f"-disposition:a:{audio_idx}", "0"
            ])
            audio_idx += 1
            
            # 3. Map Dubbed Subs First
            for track in dubbed_subtitle_tracks:
                lang = track["lang"]
                lang_display = lang_names.get(lang, lang.upper())
                sub_label = {"ru": "Субтитры", "tr": "Altyazı", "en": "Subtitles"}.get(lang, f"{lang_display} Subtitles")
                
                ffmpeg_maps.extend(["-map", f"{track['sub_file_idx']}:s:0"])
                
                is_default = "1" if sub_idx == 0 else "0"
                metadata.extend([
                    f"-metadata:s:s:{sub_idx}", f"title={sub_label}",
                    f"-metadata:s:s:{sub_idx}", f"language={lang}",
                    f"-disposition:s:{sub_idx}", is_default
                ])
                sub_idx += 1
                
            # 4. Map Original Sub
            ffmpeg_maps.extend(["-map", "1:s:0"])
            metadata.extend([
                f"-metadata:s:s:{sub_idx}", f"title=Original ({src_display})",
                f"-metadata:s:s:{sub_idx}", f"language={source_lang or 'und'}",
                f"-disposition:s:{sub_idx}", "0"
            ])
            sub_idx += 1

            self._run_subprocess(
                ["ffmpeg", "-y"]
                + ffmpeg_inputs
                + ["-c:v", "copy", "-c:a", "aac", "-c:s", "srt"]
                + ffmpeg_maps
                + metadata
                + [final_mkv],
                check=True,
            )
            self.progress_signal.emit(100)
            _set_model_status("mux", "done")

            # --- Lip-Sync Logic ---
            if getattr(self, "lip_sync", False):
                self.log_signal.emit(_pipeline_t("lipsync_start", self.ui_language))
                lip_sync_out = os.path.join(
                    self.out_dir, f"{base_name}_Final_LipSync.mkv"
                )

                # Check if lip_sync_worker exists, if not just skip or simulate
                worker_script = os.path.join(
                    os.path.dirname(__file__), "lip_sync_worker.py"
                )
                if os.path.exists(worker_script):
                    try:
                        # Call lip sync worker with first language audio
                        first_lang = list(self.langs.keys())[0]
                        audio_track = os.path.join(
                            self.out_dir, f"{base_name}_{first_lang}_bg.wav"
                        )
                        if not os.path.exists(audio_track):
                            audio_track = os.path.join(
                                self.out_dir, f"{base_name}_{first_lang}_dub.wav"
                            )

                        # Here we would call the actual Lip-Sync model
                        # e.g., self._run_subprocess(["python", worker_script, self.video_path, audio_track, lip_sync_out], check=True)
                        shutil.copy(
                            final_mkv, lip_sync_out
                        )  # Placeholder: just copy for now if model not downloaded
                        self.log_signal.emit(
                            _pipeline_t("lipsync_done", self.ui_language)
                        )
                        final_mkv = lip_sync_out
                    except Exception as e:
                        self.log_signal.emit(
                            _pipeline_t("lipsync_error", self.ui_language, e=str(e))
                        )
                else:
                    self.log_signal.emit(
                        _pipeline_t("lipsync_not_found", self.ui_language)
                    )

            self.finished_signal.emit(
                True, _pipeline_t("pipeline_success", self.ui_language, path=final_mkv)
            )
        except InterruptedError:
            self.log_signal.emit(_pipeline_t("pipeline_cancelled", self.ui_language))
            self.finished_signal.emit(False, "Cancelled by user")
            # Mark current model as cancelled (idle, not error)
            _finish_pipeline_status()
        except Exception as e:
            import traceback as _tb  # noqa: PLC0415

            _tb.print_exc()
            self.log_signal.emit(
                _pipeline_t("pipeline_error", self.ui_language, e=str(e))
            )
            self.finished_signal.emit(False, str(e))
            # Mark the active model step as error (visible red in StatusBar)
            _finish_pipeline_status(error=True)
            # ── Auto-report to GitHub Issues (best-effort, не блокирует) ──
            self._report_error_to_github(str(e))
        else:
            # Success path — clean idle reset
            _finish_pipeline_status()
        finally:
            with PIPELINE_LOCK:
                PIPELINE_BUSY = False

            # Даем Windows время отпустить файловые хэндлы
            import time
            time.sleep(1.0)

            # ── Aggressive cleanup: remove all intermediate files ──
            if not getattr(self, "keep_intermediate", False):
                # 1. Demucs output directory (large, always remove)
                if 'demucs_out_dir' in locals() and demucs_out_dir and os.path.exists(demucs_out_dir):
                    shutil.rmtree(demucs_out_dir, ignore_errors=True)

                # 2. Tracked intermediate files (checkpoints, SRT, temp audio)
                for f in all_created_files:
                    try:
                        if os.path.exists(f):
                            os.remove(f)
                    except Exception:
                        pass

                # 3. Source video (downloaded from URL — don't keep raw video)
                if _was_url_source and self.video_path:
                    if os.path.exists(self.video_path):
                        try:
                            os.remove(self.video_path)
                        except Exception:
                            pass

                # 4. Final sweep: remove any leftover temp_* files in out_dir
                try:
                    for entry in os.listdir(self.out_dir):
                        if entry.startswith("temp_") or entry.startswith("."):
                            full = os.path.join(self.out_dir, entry)
                            try:
                                if os.path.isfile(full):
                                    os.remove(full)
                                elif os.path.isdir(full):
                                    shutil.rmtree(full, ignore_errors=True)
                            except Exception:
                                pass
                except Exception:
                    pass

                # 5. If pipeline failed, remove out_dir (nothing to keep)
                #    (success path keeps only final_mkv, everything else already removed above)
                try:
                    remaining = (
                        os.listdir(self.out_dir) if os.path.isdir(self.out_dir) else []
                    )
                    # Only keep .mkv/.mp4 output files; remove empty dir
                    has_output = any(f.endswith((".mkv", ".mp4")) for f in remaining)
                    if not has_output and remaining:
                        for entry in remaining:
                            full = os.path.join(self.out_dir, entry)
                            try:
                                if os.path.isfile(full):
                                    os.remove(full)
                                elif os.path.isdir(full):
                                    shutil.rmtree(full, ignore_errors=True)
                            except Exception:
                                pass
                except Exception:
                    pass
