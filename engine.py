import os
import re
import shutil
import subprocess
import sys
import threading

import torch

os.environ["PYTHONIOENCODING"] = "utf-8"

# ── Venv resolution with fallback for installed app ──
# In the installed version (AppData), only .venv is bundled.
# Other venvs (.venv-f5, .venv-xtts, .venv-qwen3-tts) may only
# exist in the dev project directory.
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

def _resolve_venv_python(venv_name: str) -> str:
    """Return the python.exe inside venv_name, searching possible root dirs."""
    for root in _POSSIBLE_ROOTS:
        candidate = os.path.join(root, venv_name, "Scripts", "python.exe")
        if os.path.exists(candidate):
            return candidate
    # Last resort: return relative to engine dir (will fail with clear error)
    return os.path.join(_ENGINE_DIR, venv_name, "Scripts", "python.exe")
# WhisperX will be imported locally inside the worker

from pydub import AudioSegment

from backend.translator import Translator
from backend.vram_manager import free_up_vram, get_free_vram_mb

# ── Safe subprocess environment (security: don't leak API keys to child processes) ──
_SUBPROCESS_SAFE_VARS = {
    "PATH", "SystemRoot", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "HOME",
    "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA", "ProgramData",
    "PYTHONPATH", "PYTHONIOENCODING", "PYTHONUNBUFFERED",
    "CUDA_PATH", "CUDA_VISIBLE_DEVICES", "HF_HOME", "TORCH_HOME",
    "OLLAMA_HOST", "COQUI_TOS_AGREED",
    "COMSPEC", "PATHEXT", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE",
}

def _safe_subprocess_env(**extra) -> dict:
    """Return a minimal environment dict for subprocess calls — no API keys, no secrets."""
    import os as _os
    env = {}
    for key in _SUBPROCESS_SAFE_VARS:
        val = _os.environ.get(key)
        if val:
            env[key] = val
    for key, val in _os.environ.items():
        if key.startswith(("CUDA_", "NVIDIA_", "TORCH_", "HF_", "OLLAMA_")) and key not in env:
            env[key] = val
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
        "ru": "🔄 Загрузка Faster-Whisper ({model}) на {device}...",
        "en": "🔄 Loading Faster-Whisper ({model}) on {device}...",
        "tr": "🔄 Faster-Whisper ({model}) {device} üzerinde yükleniyor...",
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
        "ru": "✅ Диаризация: {n} спикеров определено.",
        "en": "✅ Diarization: {n} speakers identified.",
        "tr": "✅ Diarizasyon: {n} konuşmacı belirlendi.",
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
        from shared import pipeline_status
        pipeline_status["models"][model] = state
        pipeline_status["active"] = True
    except Exception:
        pass

def _finish_pipeline_status(error: bool = False):
    """Finalize pipeline status. On error, mark active model red; else reset all to idle."""
    try:
        from shared import pipeline_status
        pipeline_status["active"] = False
        pipeline_status["step"] = ""
        pipeline_status["step_index"] = 0
        if error:
            # Find the running/pending model and mark it as error
            found = False
            step_order = ["demucs", "whisper", "pyannote", "translate", "tts", "mux"]
            for m in step_order:
                if pipeline_status["models"].get(m) == "running":
                    pipeline_status["models"][m] = "error"
                    found = True
                    break
            if not found:
                # Fallback: mark the next pending model
                for m in step_order:
                    if pipeline_status["models"].get(m) == "idle":
                        pipeline_status["models"][m] = "error"
                        break
        else:
            for k in pipeline_status["models"]:
                pipeline_status["models"][k] = "idle"
    except Exception:
        pass

def _set_engine_info(model: str, engine_id: str):
    """Set which engine is used for translate/TTS (for StatusBar display)."""
    try:
        from shared import pipeline_status
        if model == "translate":
            pipeline_status["translate_engine"] = engine_id.lower()
        elif model == "tts":
            pipeline_status["tts_engine"] = engine_id.lower()
    except Exception:
        pass

def _set_pipeline_step(step_name: str, step_index: int):
    try:
        from shared import pipeline_status
        pipeline_status["step"] = step_name
        pipeline_status["step_index"] = step_index
    except Exception:
        pass

class InterruptedError(Exception):
    """Raised when user cancels pipeline — triggers clean finally-block cleanup."""
    pass

class AutoDubWorker(threading.Thread):
    def __init__(self, video_path=None, out_dir=None, langs=None, model_size=None, device=None, translator_engine=None, gemini_key="", deepseek_key="", deepl_key="", dub_engine="", hf_key="", manual_mode=False):
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
            is_url_input = bool(self.video_path and (
                self.video_path.startswith("http://") or
                self.video_path.startswith("https://")
            ))
            if is_url_input:
                default_out = os.path.join(os.getcwd(), "downloads")
            else:
                default_out = os.path.dirname(self.video_path) if self.video_path else os.getcwd()

            # Safe makedirs with validation (defence against URL-as-path)
            def _safe_makedirs(path: str):
                """Only create directories on local filesystem, never for URLs."""
                if not path or any(path.startswith(p) for p in ("http://", "https://", "ftp://")):
                    raise ValueError(f"Refusing to create directory from URL/empty path: {path!r}")
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
                        "C:\\users\\public"
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
            self.device = cfg.get("device", "cpu")
            self.translator_engine = cfg.get("translation_engine", "Google Translate (Free)")
            self.gemini_key = cfg.get("gemini_key", "")
            self.deepseek_key = cfg.get("deepseek_key", "")
            self.deepl_key = cfg.get("deepl_key", "")
            self.dub_engine = cfg.get("dub_engine", "Edge-TTS (Cloud, Free, Fast)")
            self.hf_key = cfg.get("hf_key", "")
            self.manual_mode = cfg.get("manual_mode", False)
            self.lip_sync = cfg.get("lip_sync", False)
            self.tag = cfg.get("tag", "")
            self.demucs_model = cfg.get("demucs_model", "htdemucs_ft")
            self.ui_language = cfg.get("ui_language", "ru")
        else:
            self.video_path = video_path
            # ── Reject URL-like out_dir even in positional mode ──
            if out_dir and str(out_dir).startswith(("http://", "https://", "ftp://")):
                print(f"[SECURITY] Blocked URL as out_dir (positional): {out_dir}")
                out_dir = os.path.join(os.getcwd(), "downloads")
            self.out_dir = out_dir
            self.ui_language = "ru"
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
            self.lip_sync = False

        self.translator = Translator(self.translator_engine, self.gemini_key, self.deepseek_key, self.deepl_key, self.device)

        self.pause_event = threading.Event()
        self.edited_segments = None
        self.active_processes = []

    def isInterruptionRequested(self):
        return self._stop_event.is_set()

    def requestInterruption(self):
        self._stop_event.set()
        self.pause_event.set()
        for p in self.active_processes:
            try: p.terminate()
            except: pass

    def _run_subprocess(self, cmd, **kwargs):
        check = kwargs.pop("check", False)
        timeout = kwargs.pop("timeout", None)  # Popped — handled via polling loop below
        _ = timeout  # timeout is used implicitly via process.wait(timeout=0.5) polling

        # ── Security: don't leak API keys to child processes ──
        if "env" not in kwargs:
            kwargs["env"] = _safe_subprocess_env()
        else:
            # Merge caller-provided extras into safe base (caller's keys take precedence)
            base = _safe_subprocess_env()
            base.update(kwargs["env"])
            kwargs["env"] = base

        # Don't override if explicitly devnull
        if kwargs.get('stdout') != subprocess.DEVNULL:
            kwargs['stdout'] = subprocess.PIPE
            kwargs['stderr'] = subprocess.STDOUT
            kwargs['bufsize'] = 1
            kwargs['text'] = True
            kwargs['encoding'] = 'utf-8'
            kwargs['errors'] = 'replace'

        process = subprocess.Popen(cmd, **kwargs)
        self.active_processes.append(process)

        def _read_output(pipe):
            for line in pipe:
                if line.strip():
                    self.log_signal.emit(f"  > {line.strip()}")

        reader_thread = None
        if kwargs.get('stdout') == subprocess.PIPE:
            reader_thread = threading.Thread(target=_read_output, args=(process.stdout,), daemon=True)
            reader_thread.start()

        while process.poll() is None:
            if self._stop_event.is_set():
                try: process.terminate()
                except: pass
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
            edited.append({
                "text": s.get("trans", s.get("text", "")),
                "start": float(s.get("start", 0)),
                "end": float(s.get("end", 0)),
                "speaker": s.get("speaker", "SPEAKER_00"),
                "skip_dub": s.get("skip_dub", False),
                "gender": s.get("gender", "unknown")
            })
        self.resume_with_translations(edited)

    def format_timestamp(self, seconds):
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        msecs = int((seconds - int(seconds)) * 1000)
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"

    def _download_youtube(self, url, out_dir):
        """Download video from YouTube/TikTok/Vimeo URL using yt-dlp."""
        from urllib.parse import urlparse

        import yt_dlp

        # SSRF Protection: Validate URL scheme and domain
        parsed = urlparse(url)
        allowed_domains = ["youtube.com", "youtu.be", "www.youtube.com", "tiktok.com", "www.tiktok.com", "vimeo.com", "www.vimeo.com"]
        if parsed.scheme not in ["http", "https"] or parsed.hostname not in allowed_domains:
            raise ValueError(f"URL domain '{parsed.hostname}' is not allowed or invalid scheme. Only YouTube, TikTok, and Vimeo are supported.")

        self.log_signal.emit(_pipeline_t("downloading_video", self.ui_language, url=url[:60]))
        ydl_opts = {
            'outtmpl': os.path.join(out_dir, '%(title)s.%(ext)s'),
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            if not filepath.endswith('.mp4'):
                filepath = filepath.rsplit('.', 1)[0] + '.mp4'
            if os.path.exists(filepath):
                self.log_signal.emit(_pipeline_t("downloaded", self.ui_language, name=os.path.basename(filepath)))
                return filepath
        raise RuntimeError(f"Failed to download: {url}")

    def _check_cancelled(self):
        """Raise InterruptedError if stop was requested — allows clean finally-block cleanup."""
        if self._stop_event.is_set():
            raise InterruptedError("Pipeline cancelled by user")

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
        try:
            # Handle YouTube/TikTok/Vimeo URLs — download first
            if self.video_path.startswith("http://") or self.video_path.startswith("https://"):
                _was_url_source = True
                self.video_path = self._download_youtube(self.video_path, self.out_dir)

            self._check_cancelled()
            # Security: validate and normalize video path
            if not self.video_path or not os.path.isfile(self.video_path):
                self.finished_signal.emit(False, "Invalid video file path")
                return
            self.video_path = os.path.realpath(self.video_path)

            # Language-TTS compatibility check
            # Use IDs for internal logic to match frontend config
            TTS_COMPAT = {
                "edge-tts": {"ru", "en", "tr", "ar", "es", "fr", "de", "zh", "ja", "ko", "it", "pt", "pl", "hi"},
                "azure": {"ru", "en", "tr", "ar", "es", "fr", "de", "zh", "ja", "ko", "it", "pt", "pl", "hi"},
                "qwen3-tts": {"ru", "en", "es", "fr", "zh"},
                "xttsv2": {"ru", "en", "tr", "ar", "es", "fr", "de", "zh", "ja", "ko", "it", "pt", "pl", "hi"},
                "f5-tts": {"ru", "en", "tr", "ar", "zh"},
                "f5-onnx": {"ru", "en", "tr", "ar", "zh"},
            }
            # Fallback for display names if sent instead of IDs
            DISPLAY_TO_ID = {
                "Edge-TTS (Cloud, Free, Fast)": "edge-tts",
                "Qwen3-TTS Local": "qwen3-tts",
                "XTTSv2 Local": "xttsv2",
                "F5-TTS Local": "f5-tts",
                "F5-TTS ONNX Local": "f5-onnx",
                "Azure OpenAI (Cloud)": "azure"
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
            base_name = re.sub(r'[^\w\-]', '_', base_name)  # sanitize: no path traversal

            # ── Checkpoint helper ──
            def _save_checkpoint(name, data):
                cp_path = os.path.join(self.out_dir, f".autodub_{base_name}_{name}.json")
                import json as _json
                with open(cp_path, "w", encoding="utf-8") as f:
                    _json.dump(data, f, ensure_ascii=False)
                all_created_files.append(cp_path)
                return cp_path

            def _load_checkpoint(name):
                cp_path = os.path.join(self.out_dir, f".autodub_{base_name}_{name}.json")
                if os.path.exists(cp_path):
                    import json as _json
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
            _ALLOWED_DEMUCS = {"htdemucs", "htdemucs_ft", "htdemucs_6s", "mdx_extra_q", "mdx_extra"}
            demucs_model = getattr(self, "demucs_model", None) or "htdemucs_ft"
            if demucs_model not in _ALLOWED_DEMUCS:
                raise ValueError(f"Invalid demucs model: {demucs_model}")
            vocals_path = os.path.join(demucs_out_dir, demucs_model, base_name, "vocals.wav")
            no_vocals_path = os.path.join(demucs_out_dir, demucs_model, base_name, "no_vocals.wav")

            if not (os.path.exists(vocals_path) and os.path.exists(no_vocals_path)):
                demucs_cmd = [
                    sys.executable, "-m", "demucs.separate",
                    "-n", demucs_model,
                    "-d", self.device,  # Force CUDA/CPU
                    "--two-stems=vocals",
                    "-o", demucs_out_dir,
                    self.video_path
                ]
                self._run_subprocess(demucs_cmd, check=True)
            else:
                self.log_signal.emit(_pipeline_t("demucs_skip", self.ui_language))

            _set_model_status("demucs", "done")
            self.progress_signal.emit(15)

            transcribe_path = vocals_path if os.path.exists(vocals_path) else self.video_path

            if self.device == "cuda":
                if get_free_vram_mb() < 3000:
                    self.log_signal.emit(_pipeline_t("low_vram_cleaning", self.ui_language))
                    free_up_vram(self.log_signal.emit)
                if get_free_vram_mb() < 2000:
                    self.log_signal.emit(_pipeline_t("low_vram_cpu_fallback", self.ui_language))
                    self.device = "cpu"
                else:
                    torch.cuda.empty_cache()

            # 2. Транскрибация (Whisper) — или загрузка из чекпойнта
            self._check_cancelled()
            _set_pipeline_step("whisper", 2)
            _set_model_status("whisper", "running")
            segments = _load_checkpoint("segments")
            if segments:
                self.log_signal.emit(_pipeline_t("segments_from_cache", self.ui_language, n=len(segments)))
            else:
                self.log_signal.emit(_pipeline_t("whisper_loading", self.ui_language, model=self.model_size, device=self.device))
                # ── Run Whisper in subprocess for guaranteed VRAM cleanup ──
                import json as _json
                whisper_json_path = os.path.join(self.out_dir, f".autodub_{base_name}_whisper_out.json")
                # Write params as JSON to avoid escaping issues with paths
                whisper_params = _json.dumps({
                    "model_size": self.model_size,
                    "device": self.device,
                    "audio_path": transcribe_path,
                    "output_path": whisper_json_path,
                })
                whisper_code = (
                    "import sys,json; p=json.loads(sys.argv[1]);"
                    "from faster_whisper import WhisperModel;"
                    "ct='float16' if p['device']=='cuda' else 'int8';"
                    "m=WhisperModel(p['model_size'],device=p['device'],compute_type=ct);"
                    "segs,info=m.transcribe(p['audio_path'],beam_size=5);"
                    "print('LANG:'+info.language);"
                    "out={'segments':[{'start':s.start,'end':s.end,'text':s.text,'speaker':'SPEAKER_00'} for s in segs],'language':info.language};"
                    "json.dump(out,open(p['output_path'],'w',encoding='utf-8'),ensure_ascii=False);"
                    "print(f'DONE:{len(out[\"segments\"])}')"
                )
                self._run_subprocess(
                    [sys.executable, "-c", whisper_code, whisper_params],
                    check=True, timeout=600,
                )
                with open(whisper_json_path, "r", encoding="utf-8") as f:
                    whisper_data = _json.load(f)
                segments = whisper_data["segments"]
                source_lang = whisper_data.get("language", "en")
                all_created_files.append(whisper_json_path)
                self.log_signal.emit(_pipeline_t("segments_found", self.ui_language, n=len(segments)))
                _save_checkpoint("segments", segments)

            _set_model_status("whisper", "done")
            self.progress_signal.emit(30)

            # 3. Диаризация (определение спикеров) — опционально, если есть HF токен
            if self.hf_key:
                _set_model_status("pyannote", "running")
                self.log_signal.emit(_pipeline_t("diarization_start", self.ui_language))
                diar_json = os.path.join(self.out_dir, f"{base_name}_diarization.json")
                try:
                    diar_script = os.path.join(os.path.dirname(__file__), "diarization_worker.py")
                    # Pyannote НЕ умеет читать .mp4 — нужен WAV.
                    # Используем vocals.wav (Demucs) если есть, иначе извлекаем аудио из видео
                    diar_audio = vocals_path if os.path.exists(vocals_path) else None
                    if diar_audio is None:
                        # Извлекаем аудиодорожку во временный WAV для диаризации
                        diar_audio = os.path.join(self.out_dir, f"{base_name}_diar_audio.wav")
                        if not os.path.exists(diar_audio):
                            self._run_subprocess(
                                ["ffmpeg", "-y", "-i", self.video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", diar_audio],
                                check=True, timeout=120, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                            )
                        all_created_files.append(diar_audio)
                    self._run_subprocess(
                        [sys.executable, diar_script, diar_audio, diar_json],
                        check=True, timeout=600,
                        env={"HF_TOKEN": self.hf_key},
                    )
                    if os.path.exists(diar_json):
                        import json as _json
                        with open(diar_json, "r", encoding="utf-8") as f:
                            diar_data = _json.load(f)
                        # Map diarization speakers to whisper segments by time overlap
                        for seg in segments:
                            seg_mid = (seg["start"] + seg["end"]) / 2
                            for d in diar_data:
                                if d["start"] <= seg_mid <= d["end"]:
                                    seg["speaker"] = d["speaker"]
                                    break
                        unique = len(set(s["speaker"] for s in segments))
                        self.log_signal.emit(_pipeline_t("diarization_done", self.ui_language, n=unique))
                        all_created_files.append(diar_json)
                except Exception as e:
                    self.log_signal.emit(_pipeline_t("diarization_failed", self.ui_language, e=str(e)))

            _set_model_status("pyannote", "done")
            self.progress_signal.emit(35)

            # 3.5 — Save original English subtitles
            orig_srt_path = os.path.join(self.out_dir, f"{base_name}_original.srt")
            all_created_files.append(orig_srt_path)
            with open(orig_srt_path, "w", encoding="utf-8") as f:
                for idx, s in enumerate(segments):
                    f.write(f"{idx+1}\n{self.format_timestamp(s['start'])} --> {self.format_timestamp(s['end'])}\n{s['text'].strip()}\n\n")
            self.log_signal.emit(_pipeline_t("subtitles_saved", self.ui_language))

            # 4. Обработка языков
            ffmpeg_inputs = ["-i", self.video_path, "-i", orig_srt_path]
            ffmpeg_maps = ["-map", "0:v:0", "-map", "0:a:0", "-map", "1:s:0"]
            src_display = source_lang.upper() if source_lang else "ORIG"
            metadata = [
                "-metadata:s:a:0", f"title=Original Audio", "-metadata:s:a:0", f"language={source_lang or 'und'}",
                "-metadata:s:s:0", f"title=Original ({src_display})", "-metadata:s:s:0", f"language={source_lang or 'und'}",
            ]
            audio_track_idx, subtitle_track_idx = 1, 1

            # Start tracking input files for ffmpeg map
            file_idx = 2  # 0=video, 1=original audio+subs

            for i, (lang, _) in enumerate(self.langs.items()):
                self._check_cancelled()
                _set_pipeline_step("translate", 3)
                _set_model_status("translate", "running")
                _set_engine_info("translate", getattr(self, "translator_engine", ""))
                self.log_signal.emit(_pipeline_t("processing_lang", self.ui_language, lang=lang))
                srt_path = os.path.join(self.out_dir, f"{base_name}_{lang}.srt")
                all_created_files.append(srt_path)

                # Check for cached translation
                cached = _load_checkpoint(f"translated_{lang}")
                if cached:
                    translated_segments = cached
                    self.log_signal.emit(_pipeline_t("translation_from_cache", self.ui_language, n=len(translated_segments)))
                else:
                    self.log_signal.emit(_pipeline_t("translation_start", self.ui_language, lang=lang))
                    translated_segments = self.translator.smart_translate_segments([dict(s) for s in segments], lang, self.log_signal.emit, self._check_cancelled, ui_language=self.ui_language)
                    _save_checkpoint(f"translated_{lang}", translated_segments)

                # Progress: 35% + translation portion (15% of total range per lang)
                num_langs = len(self.langs)
                self.progress_signal.emit(35 + (i + 1) * (15 // max(num_langs, 1)))

                if self.manual_mode:
                    manual_subs = []
                    for idx, s in enumerate(translated_segments):
                        manual_subs.append({
                            "time": f"{self.format_timestamp(s['start'])} → {self.format_timestamp(s['end'])}",
                            "orig": segments[idx]['text'],
                            "trans": s['text'],
                            "start": s['start'],
                            "end": s['end'],
                            "speaker": s.get('speaker', 'SPEAKER_00'),
                            "gender": s.get('gender', 'unknown'),
                            "skip_dub": s.get('skip_dub', False)
                        })
                    self.manual_edit_signal.emit(manual_subs)
                    while not self.pause_event.is_set():
                        if getattr(self, "isInterruptionRequested", lambda: False)():
                            self.finished_signal.emit(False, "Aborted")
                            return
                        self.pause_event.wait(0.5)
                    self.pause_event.clear()
                    if self.edited_segments: translated_segments = self.edited_segments

                with open(srt_path, "w", encoding="utf-8") as f:
                    for idx, tseg in enumerate(translated_segments):
                        f.write(f"{idx+1}\n{self.format_timestamp(tseg['start'])} --> {self.format_timestamp(tseg['end'])}\n{tseg['text'].strip()}\n\n")

                # --- TTS Logic ---
                _set_model_status("translate", "done")
                _set_pipeline_step("tts", 4)
                _set_model_status("tts", "running")
                _set_engine_info("tts", engine_id)
                use_f5 = "f5-tts" in engine_id
                use_f5_onnx = "f5-onnx" in engine_id
                use_xtts = "xttsv2" in engine_id
                use_qwen = "qwen3-tts" in engine_id
                audio_clips = []

                # Pre-extract skip_dub segments
                vocals_full = AudioSegment.from_file(transcribe_path)
                tts_segments = []

                for idx, tseg in enumerate(translated_segments):
                    ext = "mp3" if not (use_f5 or use_f5_onnx or use_xtts or use_qwen) else "wav"
                    clip_path = os.path.join(self.out_dir, f"temp_{lang}_{idx}.{ext}")

                    if tseg.get("skip_dub", False):
                        orig_start_ms = int(tseg["start"] * 1000)
                        orig_end_ms = int(tseg["end"] * 1000)
                        extracted = vocals_full[orig_start_ms:orig_end_ms]
                        extracted.export(clip_path, format=ext)
                        all_created_files.append(clip_path)
                        audio_clips.append((tseg["start"], clip_path, False, tseg))
                    else:
                        tts_segments.append((idx, tseg, clip_path))

                if use_f5 or use_f5_onnx or use_xtts:
                    speaker_refs = {}
                    for s in segments:
                        spk = s.get("speaker", "SPEAKER_00")
                        dur = s["end"] - s["start"]
                        if spk not in speaker_refs or dur > speaker_refs[spk]["dur"]:
                            speaker_refs[spk] = {"dur": dur, "start": s["start"], "end": s["end"], "text": s["text"]}

                    for spk, ref in speaker_refs.items():
                        ref_path = os.path.join(self.out_dir, f"ref_{spk}.wav")
                        vocals_full[int(ref["start"]*1000):int(ref["end"]*1000)].export(ref_path, format="wav")
                        ref["path"] = ref_path
                        all_created_files.append(ref_path)

                if use_f5 or use_f5_onnx or use_xtts:
                    tasks = []
                    for idx, tseg, clip_path in tts_segments:
                        spk = tseg.get("speaker", "SPEAKER_00")
                        ref = speaker_refs.get(spk, list(speaker_refs.values())[0])
                        tasks.append({"ref_audio": ref["path"], "ref_text": ref["text"], "gen_text": tseg["text"], "out_path": clip_path, "language": lang})
                        audio_clips.append((tseg["start"], clip_path, False, tseg))

                    if tasks:
                        tasks_file = os.path.join(self.out_dir, f"tasks_{lang}.json")
                        import json
                        with open(tasks_file, "w", encoding="utf-8") as f: json.dump(tasks, f)

                        if use_f5:
                            f5_py = _resolve_venv_python(".venv-f5")
                            f5_worker_script = os.path.join(os.path.dirname(__file__), "f5_worker.py")
                            self._run_subprocess([f5_py, f5_worker_script, tasks_file], check=True)
                        elif use_f5_onnx:
                            onnx_py = _resolve_venv_python(".venv")
                            onnx_worker = os.path.join(os.path.dirname(__file__), "f5_onnx_worker.py")
                            self._run_subprocess([onnx_py, onnx_worker, tasks_file], check=True)
                        else:
                            xtts_py = _resolve_venv_python(".venv-xtts")
                            xtts_worker_script = os.path.join(os.path.dirname(__file__), "xtts_worker.py")
                            self._run_subprocess([xtts_py, xtts_worker_script, tasks_file], check=True)

                        all_created_files.append(tasks_file)

                elif use_qwen:
                    tasks = []
                    for idx, tseg, clip_path in tts_segments:
                        tasks.append({"gen_text": tseg["text"], "out_path": clip_path})
                        audio_clips.append((tseg["start"], clip_path, False, tseg))

                    if tasks:
                        tasks_file = os.path.join(self.out_dir, f"tasks_qwen_{lang}.json")
                        import json
                        with open(tasks_file, "w", encoding="utf-8") as f: json.dump(tasks, f)

                        qwen_py = _resolve_venv_python(".venv-qwen3-tts")
                        qwen_worker_script = os.path.join(os.path.dirname(__file__), "qwen3_worker.py")
                        lang_map = {"ru": "Russian", "en": "English", "tr": "Turkish"}
                        qwen_lang = lang_map.get(lang, "Russian")
                        self._run_subprocess([qwen_py, qwen_worker_script, tasks_file, "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice", qwen_lang, "Vivian"], check=True)
                        all_created_files.append(tasks_file)

                else: # Edge-TTS
                    import asyncio

                    import edge_tts
                    EDGE_VOICES_MALE = {
                        "ru": "ru-RU-DmitryNeural", "en": "en-US-ChristopherNeural",
                        "tr": "tr-TR-AhmetNeural",  "ar": "ar-SA-HamedNeural",
                        "es": "es-ES-AlvaroNeural",  "fr": "fr-FR-HenriNeural",
                        "de": "de-DE-ConradNeural",  "zh": "zh-CN-YunxiNeural",
                        "ja": "ja-JP-KeitaNeural",   "ko": "ko-KR-InJoonNeural",
                        "it": "it-IT-DiegoNeural",   "pt": "pt-PT-DuarteNeural",
                        "pl": "pl-PL-MarekNeural",   "hi": "hi-IN-MadhurNeural",
                    }
                    EDGE_VOICES_FEMALE = {
                        "ru": "ru-RU-SvetlanaNeural", "en": "en-US-AriaNeural",
                        "tr": "tr-TR-EmelNeural",  "ar": "ar-SA-ZariyahNeural",
                        "es": "es-ES-ElviraNeural",  "fr": "fr-FR-DeniseNeural",
                        "de": "de-DE-AmalaNeural",  "zh": "zh-CN-XiaoxiaoNeural",
                        "ja": "ja-JP-NanamiNeural",   "ko": "ko-KR-SunHiNeural",
                        "it": "it-IT-ElsaNeural",   "pt": "pt-PT-RaquelNeural",
                        "pl": "pl-PL-AgnieszkaNeural",   "hi": "hi-IN-SwaraNeural",
                    }

                    if tts_segments:
                        self.log_signal.emit(_pipeline_t("tts_edge_start", self.ui_language, n=len(tts_segments)))

                        # ── Robust sentence-aware grouping ──
                        # Detects sentence endings in ANY language (Latin + Cyrillic + Arabic + CJK + punctuation)
                        SENTENCE_END = {
                            '.', '!', '?', '…', '。', '？', '！',  # Basic + CJK
                            '."', '!"', '?"', '.)', '.)"',          # Quoted
                            '.»', '!»', '?»',                        # French/Russian quotes
                            '.")', '!")', '?")',                     # Parenthetical quotes
                        }
                        # Also check last 2 chars for multi-char endings
                        SENTENCE_END_2 = {'.»', '!"', '?"', '."', '.)', '.)"', '.")', '!")', '?")'}

                        def _ends_sentence(text):
                            t = text.strip()
                            if not t:
                                return True  # Empty = break
                            if len(t) < 3:
                                return False  # Too short to determine, keep grouping
                            # Check multi-char endings first
                            if any(t.endswith(c) for c in SENTENCE_END_2):
                                return True
                            # Check single-char endings
                            if t[-1] in SENTENCE_END:
                                return True
                            return False

                        groups = []  # [(group_segments, combined_text)]
                        cur_group = []
                        cur_chars = 0
                        MAX_SEGMENTS = 6     # Max segments per TTS group
                        MAX_CHARS = 400       # Max total characters per group (~30 sec of speech)

                        for _, tseg, clip_path in tts_segments:
                            seg_chars = len(tseg["text"].strip())
                            # Force break if adding this segment would exceed limits
                            if cur_group and (
                                len(cur_group) >= MAX_SEGMENTS or
                                cur_chars + seg_chars > MAX_CHARS
                            ):
                                groups.append(cur_group)
                                cur_group = []
                                cur_chars = 0
                            cur_group.append((tseg, clip_path))
                            cur_chars += seg_chars
                            # Natural break at sentence end
                            if _ends_sentence(tseg["text"]):
                                groups.append(cur_group)
                                cur_group = []
                                cur_chars = 0
                        if cur_group:
                            if groups:
                                groups[-1].extend(cur_group)
                            else:
                                groups.append(cur_group)

                        async def gen_all_groups():
                            for gi, group in enumerate(groups):
                                self._check_cancelled()
                                parts = []
                                for tseg, _ in group:
                                    t = tseg["text"].strip()
                                    if t and not _ends_sentence(t) and t[-1] not in {'.', '!', '?', '…', '。'}:
                                        t += '. '  # Force sentence break for TTS naturalness
                                    parts.append(t)
                                group_text = ' '.join(parts)
                                group_path = os.path.join(self.out_dir, f"temp_{lang}_group{gi}.mp3")
                                all_created_files.append(group_path)
                                self.log_signal.emit(_pipeline_t("tts_group_progress", self.ui_language, gi=gi+1, total=len(groups), n=len(group), chars=len(group_text)))
                                await edge_tts.Communicate(group_text, voice).save(group_path)
                                # Split back to segments
                                group_audio = AudioSegment.from_file(group_path)
                                total_chars = max(1, sum(len(s[0]["text"].strip()) for s in group))
                                pos_ms = 0
                                for tseg, clip_path in group:
                                    ratio = len(tseg["text"].strip()) / total_chars
                                    seg_dur = max(300, int(len(group_audio) * ratio))
                                    end_ms = min(pos_ms + seg_dur, len(group_audio))
                                    seg_audio = group_audio[pos_ms:end_ms]
                                    seg_audio.export(clip_path, format="mp3")
                                    pos_ms = end_ms
                                    audio_clips.append((tseg["start"], clip_path, False, tseg))

                        asyncio.run(gen_all_groups())

                # --- Assembly (3 tracks: dub, clean, TTS-only) ---
                tts_only = AudioSegment.silent(duration=len(vocals_full))
                final_audio = AudioSegment.silent(duration=len(vocals_full))
                for start_t, cp, _, tseg in audio_clips:
                    if os.path.exists(cp):
                        clip = AudioSegment.from_file(cp)
                        allowed_dur = tseg["end"] - tseg["start"]
                        actual_dur = len(clip) / 1000.0
                        if actual_dur > allowed_dur + 0.1 and not tseg.get("skip_dub", False):
                            speed_factor = min(4.0, actual_dur / allowed_dur)
                            stretched_cp = cp + "_fast.wav"
                            remaining = speed_factor
                            atempo_filters = []
                            while remaining > 2.0:
                                atempo_filters.append("atempo=2.0")
                                remaining /= 2.0
                            if remaining > 1.0 or not atempo_filters:
                                atempo_filters.append(f"atempo={remaining:.4f}")
                            filter_chain = ",".join(atempo_filters)
                            self._run_subprocess(["ffmpeg", "-y", "-i", cp, "-filter:a", filter_chain, stretched_cp], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            clip = AudioSegment.from_file(stretched_cp)
                            all_created_files.append(stretched_cp)
                        tts_only = tts_only.overlay(clip, position=int(start_t * 1000))
                        final_audio = final_audio.overlay(clip, position=int(start_t * 1000))
                        all_created_files.append(cp)

                dub_path = os.path.join(self.out_dir, f"{base_name}_{lang}_dub.wav")
                final_audio.export(dub_path, format="wav")
                all_created_files.append(dub_path)

                # Clean TTS voice (no background, no original voice) — for voice quality check
                clean_tts_path = os.path.join(self.out_dir, f"{base_name}_{lang}_clean_tts.wav")
                tts_only.export(clean_tts_path, format="wav")
                all_created_files.append(clean_tts_path)

                # Dub track: background 100% (no_vocals) + original voice 15%
                ducked_path = os.path.join(self.out_dir, f"{base_name}_{lang}_ducked.wav")
                if os.path.exists(no_vocals_path):
                    # Сначала извлекаем аудио из видео в WAV (для совместимости с amix)
                    orig_audio_path = os.path.join(self.out_dir, f"{base_name}_orig_audio.wav")
                    self._run_subprocess(["ffmpeg", "-y", "-i", self.video_path, "-vn", "-acodec", "pcm_s16le",
                        orig_audio_path], check=True, timeout=60,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    all_created_files.append(orig_audio_path)
                    # Микшируем: no_vocals (100%) + оригинальный голос (15%)
                    # Громкость задана через volume, amix без weights (веса уже учтены)
                    self._run_subprocess(["ffmpeg", "-y", "-i", no_vocals_path, "-i", orig_audio_path,
                        "-filter_complex", "[0:a]volume=1.0[bg];[1:a]volume=0.15[voc];[bg][voc]amix=inputs=2:duration=first",
                        ducked_path], check=True, timeout=30,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    # Fallback: no Demucs separation — mix original audio 70% + dub
                    self._run_subprocess(["ffmpeg", "-y", "-i", self.video_path, "-i", dub_path,
                        "-filter_complex", "[0:a]volume=0.7[bg];[1:a]volume=1.0[dub];[bg][dub]amix=inputs=2:duration=first",
                        ducked_path], check=True, timeout=30,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                ffmpeg_inputs.extend(["-i", ducked_path, "-i", clean_tts_path, "-i", srt_path])
                all_created_files.extend([ducked_path, clean_tts_path])

                ffmpeg_maps.extend(["-map", f"{file_idx}:a:0", "-map", f"{file_idx+1}:a:0", "-map", f"{file_idx+2}:s:0"])
                lang_names = {"ru": "Russian", "tr": "Turkish", "en": "English", "ar": "Arabic",
                              "es": "Spanish", "fr": "French", "de": "German"}
                lang_display = lang_names.get(lang, lang.upper())
                metadata.extend([
                    f"-metadata:s:a:{audio_track_idx}", f"title={lang_display} Dub",
                    f"-metadata:s:a:{audio_track_idx}", f"language={lang}",
                    f"-metadata:s:a:{audio_track_idx+1}", f"title={lang_display} Clean",
                    f"-metadata:s:a:{audio_track_idx+1}", f"language={lang}",
                    f"-metadata:s:s:{subtitle_track_idx}", f"title={lang_display} Subtitles",
                    f"-metadata:s:s:{subtitle_track_idx}", f"language={lang}",
                ])
                audio_track_idx += 2; subtitle_track_idx += 1
                file_idx += 3

                # Progress: TTS done for this language
                num_langs = len(self.langs)
                self.progress_signal.emit(35 + (i + 1) * 50 // max(num_langs, 1))


            _set_model_status("tts", "done")
            _set_pipeline_step("mux", 5)
            _set_model_status("mux", "running")
            tag_str = f"_{self.tag}" if hasattr(self, 'tag') and self.tag else ""
            self.progress_signal.emit(90)
            lang_codes = "_".join(sorted(self.langs.keys()))
            final_mkv = os.path.join(self.out_dir, f"{base_name}{tag_str}_{lang_codes.upper()}.mkv")
            self._run_subprocess(["ffmpeg", "-y"] + ffmpeg_inputs + ["-c:v", "copy", "-c:a", "aac", "-c:s", "srt"] + ffmpeg_maps + metadata + [final_mkv], check=True)
            self.progress_signal.emit(100)
            _set_model_status("mux", "done")

            # --- Lip-Sync Logic ---
            if getattr(self, "lip_sync", False):
                self.log_signal.emit(_pipeline_t("lipsync_start", self.ui_language))
                lip_sync_out = os.path.join(self.out_dir, f"{base_name}_Final_LipSync.mkv")

                # Check if lip_sync_worker exists, if not just skip or simulate
                worker_script = os.path.join(os.path.dirname(__file__), "lip_sync_worker.py")
                if os.path.exists(worker_script):
                    try:
                        # Call lip sync worker with first language audio
                        first_lang = list(self.langs.keys())[0]
                        audio_track = os.path.join(self.out_dir, f"{base_name}_{first_lang}_bg.wav")
                        if not os.path.exists(audio_track):
                            audio_track = os.path.join(self.out_dir, f"{base_name}_{first_lang}_dub.wav")

                        # Here we would call the actual Lip-Sync model
                        # e.g., self._run_subprocess(["python", worker_script, self.video_path, audio_track, lip_sync_out], check=True)
                        shutil.copy(final_mkv, lip_sync_out) # Placeholder: just copy for now if model not downloaded
                        self.log_signal.emit(_pipeline_t("lipsync_done", self.ui_language))
                        final_mkv = lip_sync_out
                    except Exception as e:
                        self.log_signal.emit(_pipeline_t("lipsync_error", self.ui_language, e=str(e)))
                else:
                    self.log_signal.emit(_pipeline_t("lipsync_not_found", self.ui_language))

            self.finished_signal.emit(True, _pipeline_t("pipeline_success", self.ui_language, path=final_mkv))
        except InterruptedError:
            self.log_signal.emit(_pipeline_t("pipeline_cancelled", self.ui_language))
            self.finished_signal.emit(False, "Cancelled by user")
            # Mark current model as cancelled (idle, not error)
            _finish_pipeline_status()
        except Exception as e:
            import traceback as _tb
            _tb.print_exc()
            self.log_signal.emit(_pipeline_t("pipeline_error", self.ui_language, e=str(e)))
            self.finished_signal.emit(False, str(e))
            # Mark the active model step as error (visible red in StatusBar)
            _finish_pipeline_status(error=True)
        else:
            # Success path — clean idle reset
            _finish_pipeline_status()
        finally:
            with PIPELINE_LOCK:
                PIPELINE_BUSY = False
            # ── Aggressive cleanup: remove all intermediate files ──
            # 1. Demucs output directory (large, always remove)
            if demucs_out_dir:
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
                remaining = os.listdir(self.out_dir) if os.path.isdir(self.out_dir) else []
                # Only keep .mkv/.mp4 output files; remove empty dir
                has_output = any(f.endswith(('.mkv', '.mp4')) for f in remaining)
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
