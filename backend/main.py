import asyncio
import json
import logging
import os
import secrets
import sys
import tempfile
import time

import httpx
import uvicorn
from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# ── Logging to file (with fallback for installed app) ──
def _resolve_log_path() -> str:
    """Find a writable log location. Tries project dir first, then AppData."""
    # Primary: next to the project root (works in dev mode)
    candidate = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "autodub_backend.log"
    )
    try:
        os.makedirs(os.path.dirname(candidate), exist_ok=True)
        with open(candidate, "a", encoding="utf-8") as _f:
            _f.write("")
        return candidate
    except (OSError, PermissionError):
        pass
    # Fallback: AppData/Local (works in installed app)
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    candidate = os.path.join(local_appdata, "AutoDub Studio", "autodub_backend.log")
    try:
        os.makedirs(os.path.dirname(candidate), exist_ok=True)
        with open(candidate, "a", encoding="utf-8") as _f:
            _f.write("")
        return candidate
    except (OSError, PermissionError):
        pass
    # Last resort: temp directory
    candidate = os.path.join(tempfile.gettempdir(), "autodub_backend.log")
    return candidate


LOG_FILE = _resolve_log_path()

# In-memory log buffer (ring buffer, last 5000 lines)
_LOG_BUFFER: list[str] = []
_LOG_BUFFER_MAX = 5000


class _BufferHandler(logging.Handler):
    """Captures log records into an in-memory ring buffer."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            _LOG_BUFFER.append(msg)
            if len(_LOG_BUFFER) > _LOG_BUFFER_MAX:
                del _LOG_BUFFER[:-5000]  # drop oldest
        except Exception:
            self.handleError(record)


class SanitizingFormatter(logging.Formatter):
    """Apply secret/PII redaction to ALL log output before it hits disk or console."""

    def format(self, record):
        original = super().format(record)
        # Import locally to avoid circular import (redact_secrets is defined below)
        return _redact_log(original)


import re as _re

_REGEX_API_KEYS = _re.compile(
    r"(HF_TOKEN|GITHUB_TOKEN|GEMINI_API_KEY|DEEPSEEK_API_KEY|DEEPL_API_KEY|OPENAI_API_KEY|AZURE_OPENAI_KEY)[\s:=]+[\w\-]+",
    _re.IGNORECASE,
)
_REGEX_HF_TOKEN = _re.compile(r"hf_[a-zA-Z0-9]{34}")
_REGEX_GH_TOKEN_1 = _re.compile(r"ghp_[a-zA-Z0-9]{36}")
_REGEX_GH_TOKEN_2 = _re.compile(r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}")
_REGEX_DEEPL = _re.compile(r"[a-f0-9\-]{36}:fx")
_REGEX_WIN_PATH = _re.compile(r"C:\\Users\\[^\\]+")
_REGEX_LINUX_PATH = _re.compile(r"/home/[^/]+")


def _redact_log(text: str) -> str:
    """Redact secrets and PII from a log string. Used by SanitizingFormatter and WS logs."""
    if not text:
        return text
    text = _REGEX_API_KEYS.sub(r"\1=***", text)
    text = _REGEX_HF_TOKEN.sub(r"hf_***", text)
    text = _REGEX_GH_TOKEN_1.sub(r"ghp_***", text)
    text = _REGEX_GH_TOKEN_2.sub(r"github_pat_***", text)
    text = _REGEX_DEEPL.sub(r"***:fx", text)

    # Оптимизированная замена домашней директории
    home_dir = os.path.expanduser("~")
    if home_dir in text:
        text = text.replace(home_dir, "~")

    text = _REGEX_WIN_PATH.sub(r"C:\\Users\\***", text)
    text = _REGEX_LINUX_PATH.sub(r"/home/***", text)
    return text


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
        _BufferHandler(),
    ],
)
# Apply sanitizing formatter to ALL handlers
for handler in logging.root.handlers:
    handler.setFormatter(
        SanitizingFormatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
logger = logging.getLogger("autodub")
import threading
from queue import Empty, Queue

download_semaphore = threading.Semaphore(2)

# ── Safe subprocess environment (security: don't leak API keys to child processes) ──
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


def _safe_subprocess_env(**extra) -> dict:
    """Return a minimal environment dict for subprocess calls — no API keys, no secrets."""
    env = {}
    for key in _SUBPROCESS_SAFE_VARS:
        val = os.environ.get(key)
        if val:
            env[key] = val
    # Whitelist: pass GPU-related vars
    for key, val in os.environ.items():
        if (
            key.startswith(("CUDA_", "NVIDIA_", "TORCH_", "HF_", "OLLAMA_"))
            and key not in env
        ):
            env[key] = val
    env.update(extra)
    return env


# ── Clean up old zombie backend instances ──
# (Cleanup is now delegated to Tauri in gui/src-tauri/src/lib.rs on exit)


# Add parent directory to path to import engine.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import PIPELINE_BUSY, AutoDubWorker

APP_VERSION = "0.0.1"

app = FastAPI(
    title="AutoDubStudio Backend",
    description="Local API for AutoDubStudio Desktop Application",
    version=APP_VERSION,
)

# ── Security: max request body size (prevents memory exhaustion DoS) ──
MAX_BODY_SIZE = 2 * 1024 * 1024  # 2 MB — enough for error reports, too small for abuse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with bodies larger than MAX_BODY_SIZE."""

    async def dispatch(self, request, call_next):
        if request.headers.get("transfer-encoding", "").lower() == "chunked":
            return JSONResponse(
                {"detail": "Chunked encoding not supported"}, status_code=411
            )
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(
                {"detail": "Request body too large"},
                status_code=413,
            )
        return await call_next(request)


app.add_middleware(BodySizeLimitMiddleware)


# ── Security: CSP headers for webview ──
class CSPMiddleware(BaseHTTPMiddleware):
    """Add Content-Security-Policy headers to all HTTP responses."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # For desktop app: connect to local services + external APIs
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "connect-src 'self' http://127.0.0.1:* http://localhost:* "
            "https://api.deepseek.com https://api-free.deepl.com https://api.deepl.com "
            "https://generativelanguage.googleapis.com https://api.openai.com "
            "https://huggingface.co https://api.github.com; "
            "script-src 'self' 'unsafe-inline'; "  # Tauri webview needs inline scripts
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:;"
        )
        return response


app.add_middleware(CSPMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:1420",
        "tauri://localhost",
        "https://tauri.localhost",
        "http://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# ── Shared state (imported by engine.py without circular import) ──
from shared import pipeline_status, reset_pipeline_status

# ── WebSocket auth token (generated fresh each backend startup) ──
WS_AUTH_TOKEN = secrets.token_urlsafe(32)
print(f"[SECURITY] WebSocket auth token generated (len={len(WS_AUTH_TOKEN)} chars)")
print("[SECURITY] Backend bound to 127.0.0.1:8000 — no external network access")


class StatusResponse(BaseModel):
    status: str
    message: str


@app.get("/", response_model=StatusResponse)
async def read_root():
    return {"status": "ok", "message": "AutoDubStudio Backend is running"}


@app.get("/api/models")
def get_models():
    return {
        "models": [
            {
                "id": "xttsv2",
                "name": "XTTS v2 (Мультиязычный, 14 языков)",
                "type": "local",
            },
        ]
    }


# ── GPU Status endpoint (polled by StatusBar every 5s) ──
@app.get("/api/system/gpu")
def get_gpu_status():
    """Return CUDA availability, VRAM, and GPU name for the StatusBar component."""
    try:
        import torch  # noqa: PLC0415

        cuda_available = torch.cuda.is_available()
        if cuda_available:
            gpu_name = torch.cuda.get_device_name(0)
            vram_used_gb = 0.0
            vram_total_gb = 0.0

            # Try nvidia-smi first for accurate Windows Task Manager equivalent
            import shutil  # noqa: PLC0415
            import subprocess  # noqa: PLC0415

            try:
                smi_path = (
                    shutil.which("nvidia-smi") or r"C:\Windows\System32\nvidia-smi.exe"
                )
                out = subprocess.check_output(
                    [
                        smi_path,
                        "--query-gpu=memory.used,memory.total",
                        "--format=csv,nounits,noheader",
                    ],
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                used_mb, total_mb = map(float, out.strip().split(","))
                vram_used_gb = round(used_mb / 1024.0, 2)
                vram_total_gb = round(total_mb / 1024.0, 2)
            except Exception:
                # Fallback to torch (can be slightly off on Windows WDDM)
                free_bytes, total_bytes = torch.cuda.mem_get_info(0)
                vram_used_gb = round((total_bytes - free_bytes) / (1024**3), 2)
                vram_total_gb = round(total_bytes / (1024**3), 2)
        else:
            gpu_name = ""
            vram_used_gb = 0.0
            vram_total_gb = 0.0
    except Exception:
        cuda_available = False
        gpu_name = ""
        vram_used_gb = 0.0
        vram_total_gb = 0.0
    try:
        import psutil  # noqa: PLC0415

        cpu_pct = psutil.cpu_percent()
        ram = psutil.virtual_memory()
        sys_ram_used_gb = round(ram.used / (1024**3), 2)
        sys_ram_total_gb = round(ram.total / (1024**3), 2)
    except Exception:
        cpu_pct = 0.0
        sys_ram_used_gb = 0.0
        sys_ram_total_gb = 0.0

    return {
        "cuda_available": cuda_available,
        "gpu_name": gpu_name,
        "vram_used_gb": vram_used_gb,
        "vram_total_gb": vram_total_gb,
        "sys_cpu_pct": cpu_pct,
        "sys_ram_used_gb": sys_ram_used_gb,
        "sys_ram_total_gb": sys_ram_total_gb,
    }


@app.get("/api/pipeline/status")
def get_pipeline_status():
    """Live model status during dubbing — polled by StatusBar every 2s."""
    try:
        import torch  # noqa: PLC0415

        if torch.cuda.is_available():
            # Use nvidia-smi for accurate driver-level memory info (matches Task Manager)
            import shutil  # noqa: PLC0415
            import subprocess  # noqa: PLC0415

            try:
                smi_path = (
                    shutil.which("nvidia-smi") or r"C:\Windows\System32\nvidia-smi.exe"
                )
                out = subprocess.check_output(
                    [
                        smi_path,
                        "--query-gpu=memory.used,memory.total",
                        "--format=csv,nounits,noheader",
                    ],
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                used_mb, total_mb = map(float, out.strip().split(","))
                pipeline_status["vram_used_gb"] = round(used_mb / 1024.0, 2)
                pipeline_status["vram_total_gb"] = round(total_mb / 1024.0, 2)
            except Exception:
                free_bytes, total_bytes = torch.cuda.mem_get_info(0)
                used_bytes = total_bytes - free_bytes
                pipeline_status["vram_used_gb"] = round(used_bytes / (1024**3), 2)
                pipeline_status["vram_total_gb"] = round(total_bytes / (1024**3), 2)

            pipeline_status["gpu_name"] = torch.cuda.get_device_name(0)
            # Also report PyTorch-specific allocations
            allocated = torch.cuda.memory_allocated(0) / (1024**3)
            reserved = torch.cuda.memory_reserved(0) / (1024**3)
            pipeline_status["pytorch_allocated_gb"] = round(allocated, 2)
            pipeline_status["pytorch_reserved_gb"] = round(reserved, 2)
    except Exception:
        pipeline_status["vram_used_gb"] = 0
        pipeline_status["vram_total_gb"] = 0
    return pipeline_status


@app.post("/api/pipeline/reset")
async def reset_pipeline():
    """Сброс индикаторов пайплайна в idle (серые). Вызывается при 'New Project'."""
    reset_pipeline_status()
    return {"status": "ok", "message": "Pipeline status reset"}


# Safe-to-terminate process names (browsers, media, chat apps)
SAFE_TO_KILL = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "spotify.exe",
    "discord.exe",
    "teams.exe",
    "slack.exe",
    "zoom.exe",
    "vlc.exe",
    "wmplayer.exe",
    "msrdc.exe",
    "mstsc.exe",
}


@app.get("/api/system/processes")
def get_heavy_processes():
    """Return top VRAM/RAM-consuming SAFE-TO-KILL processes for the cleaner dialog."""
    import getpass  # noqa: PLC0415

    current_user = getpass.getuser()
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_info", "username"]):  # noqa: F821
        try:
            mi = p.info["memory_info"]
            name = (p.info["name"] or "").lower()
            # Only show processes owned by current user AND in the safe-to-kill list
            if (
                mi
                and mi.rss > 50 * 1024 * 1024
                and p.info["username"] == current_user
                and name in SAFE_TO_KILL
            ):
                procs.append(
                    {
                        "pid": p.info["pid"],
                        "name": p.info["name"],
                        "ram_mb": round(mi.rss / (1024 * 1024), 1),
                    }
                )
        except Exception:
            pass
    procs.sort(key=lambda x: x["ram_mb"], reverse=True)
    return {
        "processes": procs[:20],
        "vram_used_gb": pipeline_status.get("vram_used_gb", 0),
        "vram_total_gb": pipeline_status.get("vram_total_gb", 0),
    }


@app.post("/api/system/kill-process")
async def kill_process(request: Request):
    """Force-kill a process by PID — only processes owned by the same user."""
    try:
        body = await request.json()
        pid = body.get("pid")
        if not pid or not isinstance(pid, int) or pid <= 0:
            raise HTTPException(status_code=400, detail="Invalid pid")
        import getpass  # noqa: PLC0415

        import psutil  # noqa: PLC0415

        proc = psutil.Process(pid)
        # Only allow killing processes owned by the current user
        if proc.username() != getpass.getuser():
            raise HTTPException(status_code=403, detail="Not your process")
        proc.terminate()
        return {"status": "ok", "pid": pid}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"kill-process failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to terminate process")  # noqa: B904


@app.get("/api/token")
async def get_ws_token(request: Request):
    """Frontend fetches this token once to authenticate the WebSocket connection.

    The backend is bound to 127.0.0.1:8000 and does NOT listen on external interfaces.
    Tauri webviews use a custom protocol (tauri://localhost) that may not send an Origin
    header for cross-scheme fetch() calls. In production, the Tauri app is the only client.
    """
    return {"token": WS_AUTH_TOKEN}


@app.get("/api/ollama/status")
def ollama_status():
    """Check if Ollama is running and accessible."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            env=_safe_subprocess_env(),
        )
        return {"available": result.returncode == 0, "models": result.stdout.strip()}
    except Exception:
        return {"available": False, "models": ""}


@app.post("/api/ollama/start")
async def start_ollama(request: Request):
    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    if origin and not (
        "tauri://localhost" in origin
        or "http://localhost" in origin
        or "http://127.0.0.1" in origin
    ):
        raise HTTPException(status_code=403, detail="Forbidden: Invalid origin")
    try:
        import subprocess  # noqa: PLC0415

        # Try to start ollama serve detached
        subprocess.Popen(
            ["ollama", "serve"],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=_safe_subprocess_env(),
        )
        return {"status": "ok", "message": "Ollama started"}
    except Exception as e:
        logger.error(f"Failed to start Ollama: {e}")
        raise HTTPException(status_code=500, detail="Failed to start Ollama")  # noqa: B904


@app.post("/api/ollama/stop")
async def stop_ollama(request: Request):
    origin = request.headers.get("origin") or request.headers.get("referer") or ""
    if origin and not (
        "tauri://localhost" in origin
        or "http://localhost" in origin
        or "http://127.0.0.1" in origin
    ):
        raise HTTPException(status_code=403, detail="Forbidden: Invalid origin")
    try:
        import psutil  # noqa: PLC0415

        for proc in psutil.process_iter(["name"]):
            if proc.info.get("name") in ["ollama.exe", "ollama"]:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except Exception:
                    pass
        return {"status": "ok", "message": "Ollama stopped"}
    except Exception as e:
        logger.error(f"Failed to stop Ollama: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop Ollama")  # noqa: B904


active_worker = None
active_worker_lock = threading.Lock()


@app.websocket("/ws/pipeline")
async def websocket_pipeline(websocket: WebSocket):
    # ── Authentication: first message must be {"auth": "<token>"} ──
    await websocket.accept()
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        if auth_msg.get("auth") != WS_AUTH_TOKEN:
            await websocket.send_json(
                {"type": "error", "message": "Authentication failed. Invalid token."}
            )
            await websocket.close(code=4001, reason="Unauthorized")
            return
    except asyncio.TimeoutError:
        await websocket.close(code=4001, reason="Auth timeout")
        return

    global active_worker, active_worker_lock

    event_queue = Queue()

    def on_progress(val):
        event_queue.put({"type": "progress", "data": val})

    def on_log(text):
        try:
            print(
                f"[ENGINE LOG] {redact_secrets(text)}".encode(
                    "utf-8", "replace"
                ).decode("utf-8")
            )
        except Exception:
            pass
        event_queue.put({"type": "log", "data": redact_secrets(text)})

    def on_finished(success, msg):
        event_queue.put({"type": "finished", "success": success, "message": msg})

    def on_manual_edit(manual_subs):
        orig = [s["orig"] for s in manual_subs]
        trans = [s["trans"] for s in manual_subs]
        event_queue.put(
            {
                "type": "review_ready",
                "original": orig,
                "translated": trans,
                "segments": manual_subs,
            }
        )

    try:
        while True:
            # Handle incoming messages with a timeout
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=0.1)

                if data.get("action") == "start":
                    cfg = data.get("config", {})
                    try:
                        with active_worker_lock:
                            if active_worker and active_worker.is_alive():
                                await websocket.send_json(
                                    {
                                        "type": "error",
                                        "message": "Pipeline already running",
                                    }
                                )
                                continue

                            active_worker = AutoDubWorker(cfg)
                            active_worker.progress_signal.connect(on_progress)
                            active_worker.log_signal.connect(on_log)
                            active_worker.finished_signal.connect(on_finished)
                            active_worker.manual_edit_signal.connect(on_manual_edit)

                            active_worker.start()
                        await websocket.send_json(
                            {"type": "info", "message": "Pipeline started"}
                        )
                    except Exception as e:
                        import traceback  # noqa: PLC0415

                        logger.error(
                            f"Failed to start pipeline: {e}\n{traceback.format_exc()}"
                        )
                        # Безопасность: не передаём сырой exception текст на фронтенд (может содержать пути/секреты)
                        safe_msg = redact_secrets(str(e)[:120])
                        await websocket.send_json(
                            {"type": "error", "message": f"Server error: {safe_msg}"}
                        )

                elif data.get("action") == "resume":
                    if PIPELINE_BUSY and active_worker:
                        if "segments" in data:
                            edited = []
                            for s in data["segments"]:
                                edited.append(
                                    {
                                        "start": s.get("start", 0),
                                        "end": s.get("end", 0),
                                        "text": s.get("trans", s.get("text", "")),
                                        "speaker": s.get("speaker", "SPEAKER_00"),
                                    }
                                )
                            active_worker.edited_segments = edited
                        active_worker.pause_event.set()
                        await websocket.send_json(
                            {"type": "info", "message": "Pipeline resumed"}
                        )

                elif data.get("action") == "stop":
                    if active_worker:
                        active_worker.requestInterruption()
                        await websocket.send_json(
                            {"type": "info", "message": "Stopping..."}
                        )

            except asyncio.TimeoutError:
                pass

            # Handle outgoing messages from thread
            while not event_queue.empty():
                try:
                    event = event_queue.get_nowait()
                    await websocket.send_json(event)
                except Empty:
                    break

    except WebSocketDisconnect:
        print("Client disconnected from WebSocket")
        # Do NOT stop the worker automatically on disconnect. The user might refresh the page.


# ── Live Subtitles WebSocket ──
_live_thread = None
_live_stop_event = None


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    global _live_thread, _live_stop_event

    # No auth required — live subtitles only stream non-sensitive text to localhost
    await websocket.accept()
    await websocket.send_json({"type": "status", "active": False})

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=0.5)

                if data.get("action") == "start":
                    # Stop any existing capture
                    if _live_stop_event:
                        _live_stop_event.set()
                        if _live_thread:
                            _live_thread.join(timeout=2)

                    config = data.get("config", {})
                    _live_stop_event = threading.Event()

                    # Start live capture in a background thread
                    loop = asyncio.get_running_loop()
                    _live_thread = threading.Thread(
                        target=_run_live_capture,
                        args=(websocket, config, _live_stop_event, loop),
                        daemon=True,
                    )
                    _live_thread.start()
                    await websocket.send_json({"type": "status", "active": True})

                elif data.get("action") == "stop":
                    if _live_stop_event:
                        _live_stop_event.set()
                    await websocket.send_json({"type": "status", "active": False})

            except asyncio.TimeoutError:
                pass

    except WebSocketDisconnect:
        if _live_stop_event:
            _live_stop_event.set()
        print("Live subtitles client disconnected")


def _run_live_capture(websocket, config, stop_event, loop):
    """Background thread: capture system audio, transcribe, translate, stream subtitles."""
    import queue as qmod  # noqa: PLC0415

    target_lang = config.get("targetLanguage", "ru")
    source_lang = config.get("sourceLanguage", "auto")
    engine = config.get("translationEngine", "Google Translate (Free)")  # noqa: F841
    position = config.get("subtitlePosition", "bottom")  # noqa: F841
    font_size = config.get("fontSize", "medium")  # noqa: F841

    try:
        import numpy as np  # noqa: PLC0415
        import sounddevice as sd  # noqa: PLC0415
        import torch  # noqa: PLC0415
        from faster_whisper import WhisperModel  # noqa: PLC0415

        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute = "float16" if device == "cuda" else "int8"

        model = WhisperModel("small", device=device, compute_type=compute)

        sample_rate = 16000
        chunk_seconds = 3.0
        chunk_samples = int(sample_rate * chunk_seconds)

        audio_queue = qmod.Queue()

        def audio_callback(indata, frames, time_info, status):
            if status:
                return
            audio_queue.put(indata.copy())

        # Determine source language for Whisper
        whisper_lang = None if source_lang == "auto" else source_lang

        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            callback=audio_callback,
            dtype="float32",
        ):
            buffer = np.zeros((0, 1), dtype=np.float32)

            while not stop_event.is_set():
                try:
                    data = audio_queue.get(timeout=0.3)
                    buffer = np.vstack((buffer, data))

                    if len(buffer) >= chunk_samples:
                        audio_data = buffer[:chunk_samples].flatten()

                        if np.max(np.abs(audio_data)) > 0.01:
                            segments, info = model.transcribe(
                                audio_data,
                                beam_size=5,
                                vad_filter=True,
                                vad_parameters={"min_silence_duration_ms": 500},
                                condition_on_previous_text=False,
                                language=whisper_lang,
                            )
                            text = " ".join(s.text for s in segments).strip()

                            if text:
                                # Simple translation via deep-translator
                                translated = text
                                if target_lang != source_lang:
                                    try:
                                        from deep_translator import (  # noqa: PLC0415
                                            GoogleTranslator,
                                        )

                                        translated = GoogleTranslator(
                                            source="auto", target=target_lang
                                        ).translate(text)
                                    except Exception:
                                        pass

                                subtitle = f"{text}\n---\n{translated}"

                                # Send via asyncio.run_coroutine_threadsafe equivalent
                                try:
                                    import asyncio  # noqa: PLC0415

                                    if loop.is_running():
                                        asyncio.run_coroutine_threadsafe(
                                            websocket.send_json(
                                                {"type": "subtitle", "text": subtitle}
                                            ),
                                            loop,
                                        )
                                except Exception:
                                    pass

                        buffer = np.zeros((0, 1), dtype=np.float32)

                except qmod.Empty:
                    continue

    except ImportError as e:
        print(f"[Live] Missing dependency: {e}")
    except Exception as e:
        print(f"[Live] Capture error: {e}")
    finally:
        try:
            import asyncio  # noqa: PLC0415

            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    websocket.send_json({"type": "status", "active": False}), loop
                )
        except Exception:
            pass


# ── Model Download / Status ──
import subprocess
import threading

_model_download_status: dict = {}
_model_download_lock = threading.Lock()
_model_cancel_flags: dict = {}

VALID_MODEL_IDS = {
    "whisper-tiny",
    "whisper-base",
    "whisper-small",
    "whisper-medium",
    "whisper-large-v2",
    "whisper-large-v3",
    "pyannote-segmentation",
    "xttsv2",
    "qwen3-tts",
    "f5-tts-onnx-tr",
    "htdemucs",
    "gemma4",
}

# Expected model sizes in bytes (for progress tracking)
_MODEL_SIZES = {
    "tiny": 75_000_000,
    "base": 290_000_000,
    "small": 483_000_000,
    "medium": 1_500_000_000,
    "large-v2": 3_100_000_000,
    "large-v3": 3_100_000_000,
    "xttsv2": 1_900_000_000,
    "gemma4": 9_600_000_000,
}


def _monitor_file_progress(
    model_id: str, file_path: str, expected_size: int, stop_event: threading.Event
):
    """Monitor file size during download and update progress."""
    while not stop_event.is_set():
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            pct = min(99, int(size / expected_size * 100))
            with _model_download_lock:
                if _model_download_status.get(model_id, {}).get("progress", 0) < pct:
                    _model_download_status[model_id]["progress"] = pct
        time.sleep(2)


@app.get("/api/logs")
async def get_logs(lines: int = 200, authorization: str = Header("")):
    """Return recent backend log lines (from file or in-memory buffer)."""
    if not verify_error_report_token(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        recent: list[str] = []
        total = 0
        # Prefer file if it exists and has content
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                total = len(all_lines)
                recent = [line.rstrip("\n") for line in all_lines[-lines:]]
        # Fall back to in-memory buffer
        if not recent and _LOG_BUFFER:
            total = len(_LOG_BUFFER)
            recent = _LOG_BUFFER[-lines:]
        return {"logs": recent, "total": total, "log_file": LOG_FILE}
    except Exception as e:
        return {"logs": [], "total": 0, "error": str(e)}


@app.get("/api/models/status")
def get_model_status():
    """Check which models are cached locally."""
    models_status = {}

    # Check Faster-Whisper cache
    hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
    whisper_ids = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
    for w_id in whisper_ids:
        cache_path = os.path.join(hf_cache, f"models--Systran--faster-whisper-{w_id}")
        models_status[f"whisper-{w_id}"] = os.path.exists(cache_path)

    # Check Pyannote cache (HF format, but pyannote puts it in torch hub sometimes)
    torch_pyannote = os.path.expanduser("~/.cache/torch/pyannote")
    pyannote_ok = False
    if os.path.exists(torch_pyannote):
        for root, dirs, files in os.walk(torch_pyannote):  # noqa: B007
            # speaker-diarization 3.1 only has a config.yaml, the actual weights are in segmentation and wespeaker
            if "speaker-diarization" in root.lower():
                if any(f == "config.yaml" for f in files):
                    pyannote_ok = True
                    break
    models_status["pyannote-segmentation"] = pyannote_ok

    # Check XTTS cache (Windows: %LOCALAPPDATA%/tts, Linux: ~/.local/share/tts)
    xtts_cache = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/.local/share"))
    xtts_cache = os.path.join(xtts_cache, "tts")
    models_status["xttsv2"] = os.path.exists(
        os.path.join(xtts_cache, "tts_models--multilingual--multi-dataset--xtts_v2")
    )

    # Check Qwen3-TTS (skip .locks)
    qwen3_cache = os.path.expanduser("~/.cache/huggingface/hub")
    models_status["qwen3-tts"] = False
    if os.path.exists(qwen3_cache):
        for root, dirs, _ in os.walk(qwen3_cache):
            dirs[:] = [d for d in dirs if d != ".locks"]
            if "qwen" in root.lower() and "tts" in root.lower():
                models_status["qwen3-tts"] = True
                break

    # Check F5-TTS
    models_status["f5-tts"] = False
    f5_cache = os.path.expanduser("~/.cache/huggingface/hub/models--SWivid--F5-TTS")
    if os.path.exists(f5_cache):
        for root, dirs, files in os.walk(f5_cache):  # noqa: B007
            if "snapshots" in root:
                models_status["f5-tts"] = True

    # Check F5-TTS ONNX Turkish
    models_status["f5-tts-onnx-tr"] = False
    f5_onnx_tr_cache = os.path.expanduser(
        "~/.cache/huggingface/hub/models--patientxtr--F5_TTS_ONNX_Turkish"
    )
    if os.path.exists(f5_onnx_tr_cache):
        for root, dirs, files in os.walk(f5_onnx_tr_cache):  # noqa: B007
            if "snapshots" in root:
                models_status["f5-tts-onnx-tr"] = True

    # Check Demucs — model saved as .th file in torch hub checkpoints (~80 MB)
    demucs_cache = os.path.expanduser("~/.cache/torch/hub/checkpoints")
    models_status["htdemucs"] = False
    if os.path.exists(demucs_cache):
        for f in os.listdir(demucs_cache):
            fp = os.path.join(demucs_cache, f)
            if (
                f.endswith(".th")
                and os.path.isfile(fp)
                and os.path.getsize(fp) > 50_000_000
            ):
                models_status["htdemucs"] = True
                break

    # Check Gemma 4 via Ollama
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            env=_safe_subprocess_env(),
        )
        models_status["gemma4"] = "gemma4" in result.stdout
    except Exception:
        models_status["gemma4"] = False

    # Merge with in-progress downloads
    with _model_download_lock:
        for k, v in _model_download_status.items():
            models_status[k] = v.get("done", models_status.get(k, False))

    return {"models": models_status, "downloading": _model_download_status}


@app.post("/api/models/cancel/{model_id}")
async def cancel_download(model_id: str):
    """Cancel an in-progress download and clean up partial files."""
    if model_id not in VALID_MODEL_IDS:
        raise HTTPException(status_code=400, detail=f"Invalid model ID: {model_id}")
    with _model_download_lock:
        _model_cancel_flags[model_id] = True
        _model_download_status[model_id] = {
            "done": False,
            "progress": 0,
            "error": "Cancelled",
        }

    await delete_model(model_id)

    # Clear download status so model shows as not installed
    with _model_download_lock:
        _model_download_status.pop(model_id, None)

    return {"status": "cancelled", "model": model_id}


@app.delete("/api/models/delete/{model_id}")
async def delete_model(model_id: str):
    """Delete a downloaded model."""
    if model_id not in VALID_MODEL_IDS:
        raise HTTPException(status_code=400, detail=f"Invalid model ID: {model_id}")

    logger.warning("AUDIT: Model deletion requested | model=%s", model_id)

    import shutil  # noqa: PLC0415

    deleted_paths = []
    errors = []

    def try_remove_dir(path):
        if os.path.exists(path):
            try:
                shutil.rmtree(path, ignore_errors=True)
                deleted_paths.append(path)
            except Exception as e:
                errors.append(f"Failed to delete {path}: {str(e)}")

    def try_remove_file(path):
        if os.path.exists(path):
            try:
                os.remove(path)
                deleted_paths.append(path)
            except Exception as e:
                errors.append(f"Failed to delete {path}: {str(e)}")

    if model_id.startswith("whisper"):
        size = model_id.replace("whisper-", "")
        cache_dir = os.path.expanduser(
            f"~/.cache/huggingface/hub/models--Systran--faster-whisper-{size}"
        )
        try_remove_dir(cache_dir)

    elif model_id == "pyannote-segmentation":
        torch_pyannote = os.path.expanduser("~/.cache/torch/pyannote")
        try_remove_dir(torch_pyannote)

    elif model_id == "xttsv2":
        xtts_cache = os.environ.get(
            "LOCALAPPDATA", os.path.expanduser("~/.local/share")
        )
        xtts_dir = os.path.join(
            xtts_cache, "tts", "tts_models--multilingual--multi-dataset--xtts_v2"
        )
        try_remove_dir(xtts_dir)

    elif model_id == "qwen3-tts":
        hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
        try_remove_dir(
            os.path.join(hf_cache, "models--Qwen--Qwen3-TTS-12Hz-0.6B-CustomVoice")
        )
        try_remove_dir(
            os.path.join(hf_cache, "models--Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice")
        )

    elif model_id == "f5-tts":
        hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
        try_remove_dir(os.path.join(hf_cache, "models--SWivid--F5-TTS"))
    elif model_id == "f5-tts-onnx-tr":
        hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
        try_remove_dir(
            os.path.join(hf_cache, "models--patientxtr--F5_TTS_ONNX_Turkish")
        )

    elif model_id == "htdemucs":
        demucs_cache = os.path.expanduser("~/.cache/torch/hub/checkpoints")
        if os.path.exists(demucs_cache):
            for f in os.listdir(demucs_cache):
                fp = os.path.join(demucs_cache, f)
                if (
                    f.endswith(".th")
                    and os.path.isfile(fp)
                    and os.path.getsize(fp) > 50_000_000
                ):
                    try_remove_file(fp)

    elif model_id == "gemma4":
        try:
            import subprocess  # noqa: PLC0415

            subprocess.run(
                ["ollama", "rm", "gemma4:e4b"],
                capture_output=True,
                env=_safe_subprocess_env(),
            )
            deleted_paths.append("ollama: gemma4:e4b")
        except Exception as e:
            errors.append(str(e))

    if errors:
        return {"status": "partial", "deleted": deleted_paths, "errors": errors}
    return {"status": "deleted", "paths": deleted_paths}


@app.post("/api/models/preload/{model_id}")
async def preload_model(model_id: str, request: Request, hf_token: str = ""):
    """Trigger model download via the actual ML library (auto-caches).

    hf_token принимается из query params (GET) или POST body для безопасности
    (query параметры логируются серверами, POST body — нет).
    """
    if model_id not in VALID_MODEL_IDS:
        raise HTTPException(status_code=400, detail=f"Invalid model ID: {model_id}")

    # Также принимаем hf_token из POST body (безопаснее чем query param)
    try:
        body = await request.json()
        body_token = body.get("hf_token", "")
        if body_token:
            hf_token = body_token
    except Exception:
        pass  # body не JSON — используем query param значение

    token = hf_token or os.environ.get(
        "HF_TOKEN", os.environ.get("HUGGINGFACE_TOKEN", "")
    )

    with _model_download_lock:
        _model_download_status[model_id] = {"done": False, "progress": 1, "error": None}

    def _monitor_dir_size(
        cache_dir, expected_mb: int, start_pct: int = 5, max_pct: int = 95
    ):
        """Shared progress monitor: track directory size growth."""
        dirs_to_check = cache_dir if isinstance(cache_dir, list) else [cache_dir]
        for d in dirs_to_check:
            os.makedirs(d, exist_ok=True)
        for _ in range(180):  # Max 6 minutes
            time.sleep(2)
            if _model_cancel_flags.get(model_id):
                return
            try:
                total = 0
                for d in dirs_to_check:
                    for dirpath, _, filenames in os.walk(d):
                        for fn in filenames:
                            fp = os.path.join(dirpath, fn)
                            if os.path.isfile(fp):
                                total += os.path.getsize(fp)
                current_mb = total / (1024 * 1024)
                pct = min(
                    start_pct
                    + int((current_mb / max(expected_mb, 1)) * (max_pct - start_pct)),
                    max_pct,
                )
                with _model_download_lock:
                    if _model_download_status.get(model_id, {}).get("done"):
                        return
                    _model_download_status[model_id]["progress"] = max(pct, start_pct)
            except Exception:
                pass

    def _download():
        try:
            if model_id.startswith("whisper"):
                from faster_whisper import WhisperModel  # noqa: PLC0415

                size = model_id.replace("whisper-", "")

                SIZES_MB = {
                    "tiny": 75,
                    "base": 145,
                    "small": 465,
                    "medium": 1536,
                    "large-v2": 3174,
                    "large-v3": 3174,
                }
                expected_mb = SIZES_MB.get(size, 1500)
                cache_path = os.path.expanduser(
                    f"~/.cache/huggingface/hub/models--Systran--faster-whisper-{size}"
                )

                threading.Thread(
                    target=_monitor_dir_size,
                    args=(cache_path, expected_mb, 1, 90),
                    daemon=True,
                ).start()

                try:
                    with _model_download_lock:
                        _model_download_status[model_id]["progress"] = 1
                    WhisperModel(size, device="cpu", compute_type="int8")
                finally:
                    with _model_download_lock:
                        _model_download_status[model_id] = {
                            "done": True,
                            "progress": 100,
                            "error": None,
                        }

            elif model_id == "pyannote-segmentation":
                # Run in subprocess to isolate DLL/import issues
                if not token:
                    raise ValueError(
                        "HuggingFace token required. Add it in Settings -> API Keys -> HuggingFace Token."
                    )
                cache_dir = os.path.expanduser("~/.cache/torch/pyannote")
                threading.Thread(
                    target=_monitor_dir_size, args=(cache_dir, 220, 5, 95), daemon=True
                ).start()
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        """import sys, types
import torchvision
# Fix speechbrain broken lazy imports
import speechbrain.utils.importutils as sb_imports
_orig_getattr = sb_imports.LazyModule.__getattr__
def _safe_getattr(self, attr):
    if attr.startswith('__'): raise AttributeError(attr)
    try: return _orig_getattr(self, attr)
    except ImportError: return types.ModuleType(self.target)
sb_imports.LazyModule.__getattr__ = _safe_getattr

from pyannote.audio import Pipeline
import os
try:
    Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', token=os.environ['HF_TOKEN'])
except TypeError:
    Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', use_auth_token=os.environ['HF_TOKEN'])
print('PYANNOTE_OK')
""",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=1800,
                    env=_safe_subprocess_env(HF_TOKEN=token),
                )
                if result.returncode == 0:
                    with _model_download_lock:
                        _model_download_status[model_id] = {
                            "done": True,
                            "progress": 100,
                            "error": None,
                        }
                else:
                    raise RuntimeError(
                        result.stderr[:200]
                        or result.stdout[:200]
                        or "Pyannote download failed"
                    )

            elif model_id == "xttsv2":
                xtts_venv = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    ".venv-xtts",
                    "Scripts",
                    "python.exe",
                )
                if not os.path.exists(xtts_venv):
                    xtts_venv = sys.executable
                xtts_cache = os.path.join(
                    os.environ.get(
                        "LOCALAPPDATA", os.path.expanduser("~/.local/share")
                    ),
                    "tts",
                )
                threading.Thread(
                    target=_monitor_dir_size,
                    args=(xtts_cache, 1800, 5, 95),
                    daemon=True,
                ).start()
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                result = subprocess.run(
                    [
                        xtts_venv,
                        "-c",
                        "from TTS.api import TTS; TTS(model_name='tts_models/multilingual/multi-dataset/xtts_v2', progress_bar=False)",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=1800,
                    env=_safe_subprocess_env(COQUI_TOS_AGREED="1"),
                )
                if result.returncode == 0:
                    with _model_download_lock:
                        _model_download_status[model_id] = {
                            "done": True,
                            "progress": 100,
                            "error": None,
                        }
                else:
                    raise RuntimeError(
                        result.stderr[:200]
                        or result.stdout[:200]
                        or "XTTS download failed"
                    )

            elif model_id == "qwen3-tts":
                from huggingface_hub import snapshot_download  # noqa: PLC0415

                qwen3_cache_1 = os.path.expanduser(
                    "~/.cache/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-0.6B-CustomVoice"
                )
                qwen3_cache_2 = os.path.expanduser(
                    "~/.cache/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-CustomVoice"
                )
                threading.Thread(
                    target=_monitor_dir_size,
                    args=([qwen3_cache_1, qwen3_cache_2], 2300, 5, 95),
                    daemon=True,
                ).start()
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                snapshot_download("Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice", max_workers=1)
                snapshot_download("Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", max_workers=1)
                with _model_download_lock:
                    _model_download_status[model_id] = {
                        "done": True,
                        "progress": 100,
                        "error": None,
                    }

            elif model_id == "f5-tts-onnx-tr":
                from huggingface_hub import snapshot_download  # noqa: PLC0415

                f5_onnx_tr_cache = os.path.expanduser(
                    "~/.cache/huggingface/hub/models--patientxtr--F5_TTS_ONNX_Turkish"
                )
                threading.Thread(
                    target=_monitor_dir_size,
                    args=(f5_onnx_tr_cache, 500, 5, 95),
                    daemon=True,
                ).start()
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                snapshot_download("patientxtr/F5_TTS_ONNX_Turkish", max_workers=1)
                with _model_download_lock:
                    _model_download_status[model_id] = {
                        "done": True,
                        "progress": 100,
                        "error": None,
                    }

            elif model_id == "htdemucs":
                demucs_cache = os.path.expanduser("~/.cache/torch/hub/checkpoints")
                threading.Thread(
                    target=_monitor_dir_size,
                    args=(demucs_cache, 80, 5, 95),
                    daemon=True,
                ).start()
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "from demucs import pretrained; pretrained.get_model('htdemucs'); print('htdemucs ready')",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=1800,
                    env=_safe_subprocess_env(),
                )
                if result.returncode == 0:
                    with _model_download_lock:
                        _model_download_status[model_id] = {
                            "done": True,
                            "progress": 100,
                            "error": None,
                        }
                else:
                    raise RuntimeError(
                        result.stderr[:200]
                        or result.stdout[:200]
                        or "Demucs download failed"
                    )

            elif model_id == "gemma4":
                import re  # noqa: PLC0415

                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5

                process = subprocess.Popen(
                    ["ollama", "pull", "gemma4:e4b"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                    env=_safe_subprocess_env(),
                )

                buffer = ""
                while True:
                    char = process.stdout.read(1)
                    if not char and process.poll() is not None:
                        break
                    if char == "\r" or char == "\n":
                        match = re.search(r"(\d+)%", buffer)
                        if match:
                            pct = int(match.group(1))
                            with _model_download_lock:
                                _model_download_status[model_id]["progress"] = max(
                                    5, min(99, pct)
                                )
                        buffer = ""
                    else:
                        buffer += char

                process.wait()
                if process.returncode == 0:
                    with _model_download_lock:
                        _model_download_status[model_id] = {
                            "done": True,
                            "progress": 100,
                            "error": None,
                        }
                else:
                    raise RuntimeError(
                        f"ollama pull failed with code {process.returncode}"
                    )

            else:
                raise ValueError(f"Unknown model: {model_id}")

        except Exception as e:
            logger.error(f"Download failed: {model_id} — {e}")
            with _model_download_lock:
                _model_download_status[model_id] = {
                    "done": False,
                    "progress": 0,
                    "error": str(e)[:200],
                }
            # Write crash report AND try to send immediately
            report_crash_to_github(f"Model download failed ({model_id}): {e}")
            # Try sending now (backend is still alive)
            try:
                if GITHUB_TOKEN:
                    safe_error = str(e)[:300].replace(os.path.expanduser("~"), "~")
                    title = f"[Bug] Model download failed: {model_id}"
                    body = f"**Model:** {model_id}\n**Error:** {safe_error}\n**Time:** {time.strftime('%Y-%m-%dT%H:%M:%S')}"
                    resp = httpx.post(
                        f"https://api.github.com/repos/{GITHUB_REPO}/issues",
                        json={
                            "title": title,
                            "body": body,
                            "labels": ["bug", "auto-reported"],
                        },
                        headers={
                            "Authorization": f"Bearer {GITHUB_TOKEN}",
                            "Accept": "application/vnd.github+json",
                        },
                        timeout=10,
                    )
                    if resp.status_code == 201:
                        logger.info(
                            f"GitHub Issue #{resp.json().get('number')} created for {model_id} failure"
                        )
            except Exception:
                pass

    def _download_task():
        with download_semaphore:
            if _model_cancel_flags.get(model_id):
                return
            _download()

    threading.Thread(target=_download_task, daemon=True).start()
    logger.info(f"Download started: {model_id} (token={'yes' if token else 'no'})")
    return {"status": "started", "model": model_id}


# ── Error Reporting ──
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not GITHUB_TOKEN:
    # Try reading from config.json
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config.json"
    )
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            GITHUB_TOKEN = cfg.get("github_token", "")
            if GITHUB_TOKEN:
                print("[CONFIG] GitHub token loaded from config.json")
    except Exception:
        pass
if not GITHUB_TOKEN:
    print("[WARNING] GITHUB_TOKEN not set — error reporting disabled")
GITHUB_REPO = "LiskinLabs/autodubstudio"


@app.post("/api/config/github-token")
async def set_github_token(data: dict, authorization: str = Header("")):
    """Receive GitHub token from frontend settings for crash reporting."""
    if not verify_error_report_token(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    global GITHUB_TOKEN
    token = data.get("token", "")
    if token:
        GITHUB_TOKEN = token
        print("[CONFIG] GitHub token configured — crash reporting enabled")
        # Send any pending crash report
        await send_pending_crash_report()
        return {"status": "ok"}
    return {"status": "error", "message": "No token provided"}


# Rate limiter: max 5 reports per backend session
_error_report_count = 0
_MAX_ERROR_REPORTS = 5


def redact_secrets(text: str) -> str:
    """Thin wrapper around _redact_log for backward compatibility — WebSocket log events."""
    return _redact_log(text)


def verify_error_report_token(authorization: str = Header("")) -> bool:
    """Reuse WS auth token — frontend already has it from /api/token."""
    if not authorization.startswith("Bearer "):
        return False
    token = authorization[7:]
    return token == WS_AUTH_TOKEN


class ErrorReport(BaseModel):
    timestamp: str = ""
    version: str = "1.0.0"
    platform: str = ""
    language: str = ""
    theme: str = ""
    error_message: str = ""
    error_stack: str = ""
    error_component_stack: str = ""
    logs: list[str] = []
    route: str = ""


@app.post("/api/report-error")
async def report_error(report: ErrorReport, authorization: str = Header("")):
    """Send error report to GitHub Issues. Requires same auth token as WebSocket."""
    global _error_report_count
    global GITHUB_TOKEN

    # Auth check — must present valid Bearer token
    if not verify_error_report_token(authorization):
        raise HTTPException(status_code=401, detail="Invalid or missing auth token")

    # Rate limit: prevent abuse
    if _error_report_count >= _MAX_ERROR_REPORTS:
        return {
            "status": "error",
            "message": "Too many reports this session. Restart backend to reset.",
        }
    _error_report_count += 1

    if not GITHUB_TOKEN:
        return {"status": "error", "message": "GitHub token not configured on backend"}

    safe_error_msg = redact_secrets(report.error_message)
    safe_error_stack = redact_secrets(report.error_stack or "No stack trace")
    safe_logs = redact_secrets(
        chr(10).join(report.logs[-40:]) if report.logs else "No logs captured"
    )
    safe_component_stack = redact_secrets(report.error_component_stack or "")

    title = f"[Bug] {safe_error_msg[:80]}"
    body = f"""## 🐛 Auto-Reported Error

**Time:** {report.timestamp}
**Version:** {report.version}
**Platform:** {report.platform}
**Language:** {report.language} | Theme: {report.theme}
**Route:** {report.route}

### Error
```
{safe_error_msg}
```

### Stack Trace
```
{safe_error_stack}
```

{chr(10) + '### Component Stack' + chr(10) + '```' + chr(10) + safe_component_stack + chr(10) + '```' + chr(10) if safe_component_stack else ''}
### Recent Logs
```
{safe_logs}
```

---
🤖 *Auto-generated by AutoDub Studio Error Reporter*"""

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{GITHUB_REPO}/issues",
                headers={
                    "Authorization": f"Bearer {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={
                    "title": title,
                    "body": body,
                    "labels": ["bug", "auto-reported"],
                },
            )

        if resp.status_code in (200, 201):
            issue_url = resp.json().get("html_url", "")
            return {
                "status": "ok",
                "message": "Error reported successfully",
                "url": issue_url,
            }
        else:
            return {
                "status": "error",
                "message": f"GitHub API returned {resp.status_code}: {resp.text[:200]}",
            }

    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}


CRASH_LOG = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "crash_report.json"
)


def report_crash_to_github(error_msg: str):
    """Write crash info to a file for next-startup reporting."""
    try:
        # Redact secrets and PII
        safe = redact_secrets(error_msg[:500])
        crash_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "error": safe,
            "version": "0.0.1-beta",
            "platform": sys.platform,
        }
        with open(CRASH_LOG, "w", encoding="utf-8") as f:
            json.dump(crash_data, f)
        print(f"[CRASH] Crash report written to {CRASH_LOG}")
    except Exception:
        pass


async def send_pending_crash_report():
    """On startup, check for a previous crash report and send to GitHub."""
    if not os.path.exists(CRASH_LOG):
        return
    try:
        with open(CRASH_LOG, "r", encoding="utf-8") as f:
            crash_data = json.load(f)
        os.remove(CRASH_LOG)

        if not GITHUB_TOKEN:
            return

        title = f"[Crash] Backend crash — {crash_data.get('timestamp', 'unknown')}"
        body = f"""## Backend Crash Report

**Time:** {crash_data.get('timestamp', 'unknown')}
**Version:** {crash_data.get('version', 'unknown')}
**Platform:** {crash_data.get('platform', 'unknown')}

**Error:**
```
{crash_data.get('error', 'unknown')}
```
"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{GITHUB_REPO}/issues",
                json={"title": title, "body": body, "labels": ["bug", "crash"]},
                headers={
                    "Authorization": f"Bearer {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github+json",
                },
            )

        if resp.status_code == 201:
            print(
                f"[CRASH] Sent crash report -> GitHub Issue #{resp.json().get('number')}"
            )
        else:
            print(f"[CRASH] Failed to send: HTTP {resp.status_code}")
    except Exception as e:
        print(f"[CRASH] Failed to send crash report: {e}")


@app.post("/api/youtube/login")
async def youtube_login():
    """Opens a local WebView for the user to log into YouTube and extracts cookies."""
    import os  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "youtube_login.py"
    )
    try:
        # Run non-blocking using subprocess.Popen
        subprocess.Popen(
            ["uv", "run", "python", script_path],
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        return {
            "status": "ok",
            "message": "Browser opened for login. Please close it after logging in.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904


@app.get("/api/youtube/has_cookies")
async def youtube_has_cookies():
    cookie_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "youtube_cookies.txt"
    )
    return {"has_cookies": os.path.exists(cookie_file)}


@app.get("/api/debug/test-error")
async def test_error_logging(authorization: str = Header("")):
    """[DEV ONLY] Verify that errors are correctly captured in logs. Requires auth token."""
    if not verify_error_report_token(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")
    logger.error("DEBUG: Manual test error triggered for logging verification")
    return {"status": "logged"}


from pydantic import BaseModel


class YouTubeScanRequest(BaseModel):
    url: str


@app.post("/api/youtube/scan")
async def scan_youtube(req: YouTubeScanRequest):
    """Scans a YouTube URL for available subtitles and audio dubs."""
    import asyncio  # noqa: PLC0415

    import yt_dlp  # noqa: PLC0415

    def _scan():
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "js_runtimes": {"node": {"path": "node"}},
            "remote_components": {"ejs": ["github", "npm"]},
            # We only need metadata
        }

        cookie_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "youtube_cookies.txt"
        )
        if os.path.exists(cookie_file):
            ydl_opts["cookiefile"] = cookie_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=False)

            subs = []
            if "subtitles" in info:
                for lang, sub_info in info["subtitles"].items():  # noqa: B007
                    subs.append(
                        {"lang": lang, "name": f"{lang} (Official)", "is_auto": False}
                    )
            if "automatic_captions" in info:
                for lang, sub_info in info["automatic_captions"].items():  # noqa: B007
                    # Check if already added as official
                    if not any(s["lang"] == lang for s in subs):
                        subs.append(
                            {"lang": lang, "name": f"{lang} (Auto)", "is_auto": True}
                        )

            audio_tracks = []
            if "formats" in info:
                for f in info["formats"]:
                    # Look at formats with audio, prioritize those with explicit language metadata
                    if f.get("acodec") != "none":
                        lang = f.get("language")
                        # Only include it if we know the language, or if it's strictly audio-only
                        if lang or f.get("vcodec") == "none":
                            audio_tracks.append(
                                {
                                    "format_id": f.get("format_id"),
                                    "lang": lang or "unknown",
                                    "name": f"{lang or 'original'} (Audio: {f.get('format_note', '')} {f.get('ext')})",
                                    "ext": f.get("ext", "m4a"),
                                    "vcodec": f.get("vcodec"),
                                }
                            )

            # Deduplicate audio tracks by language, preferring audio-only if available, otherwise just highest quality
            unique_audio = {}
            for t in audio_tracks:
                l = t["lang"]  # noqa: E741
                # If we already have a track for this language, prefer the one with no video codec
                if l in unique_audio:
                    if unique_audio[l]["vcodec"] != "none" and t["vcodec"] == "none":
                        unique_audio[l] = t
                else:
                    unique_audio[l] = t

            return {
                "subtitles": subs,
                "audio_tracks": list(unique_audio.values()),
                "title": info.get("title", "Unknown Video"),
            }

    try:
        data = await asyncio.to_thread(_scan)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904


class YouTubeDownloadRequest(BaseModel):
    url: str
    subtitle_langs: list[str]
    audio_format_ids: list[str]
    mux: bool


@app.post("/api/youtube/download")
async def download_youtube(req: YouTubeDownloadRequest):
    """Downloads selected tracks and optionally muxes them."""
    import asyncio  # noqa: PLC0415
    import os  # noqa: PLC0415
    from urllib.parse import urlparse  # noqa: PLC0415

    import yt_dlp  # noqa: PLC0415

    # Simple validation
    parsed = urlparse(req.url)
    if parsed.hostname not in ["youtube.com", "youtu.be", "www.youtube.com"]:
        raise HTTPException(status_code=400, detail="Only YouTube URLs supported")

    out_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "downloads",
        "youtube_dl",
    )
    os.makedirs(out_dir, exist_ok=True)

    def _download():
        import glob  # noqa: PLC0415
        import time  # noqa: PLC0415

        ts = int(time.time())
        # First download the requested audio formats
        formats_to_dl = req.audio_format_ids.copy()

        # If they just want to download the selected tracks WITHOUT muxing into the video
        if not req.mux:
            if not formats_to_dl:
                f_str = "bestaudio"  # fallback if only subs selected
            else:
                f_str = ",".join(formats_to_dl)
        else:
            # They want to mux into a video
            if not formats_to_dl:
                # No specific audio track selected, just get best video + best audio
                f_str = "bestvideo+bestaudio/best"
            elif len(formats_to_dl) == 1:
                # Only 1 audio track, yt-dlp can merge it perfectly
                f_str = f"bestvideo+{formats_to_dl[0]}"
            else:
                # Multiple audio tracks + video. yt-dlp is bad at this.
                # Download them all as separate files using comma.
                f_str = f"bestvideo,bestaudio/best,{','.join(formats_to_dl)}"

        ydl_opts = {
            "outtmpl": os.path.join(out_dir, f"%(title)s_{ts}_%(format_id)s.%(ext)s"),
            "format": f_str,
            "quiet": False,
            "ignoreerrors": True,  # Prevents subtitle 429 Too Many Requests from crashing the entire download
            "subtitleslangs": req.subtitle_langs if req.subtitle_langs else None,
            "writesubtitles": len(req.subtitle_langs) > 0,
            "writeautomaticsub": len(req.subtitle_langs) > 0,
            "js_runtimes": {"node": {"path": "node"}},
            "remote_components": {"ejs": ["github", "npm"]},
        }

        cookie_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "youtube_cookies.txt"
        )
        if os.path.exists(cookie_file):
            ydl_opts["cookiefile"] = cookie_file

        # Download subtitles separately to avoid YouTube 429 rate limits from yt-dlp spamming them for every format
        if req.subtitle_langs and len(formats_to_dl) > 1:
            sub_opts = {
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": req.subtitle_langs,
                "outtmpl": os.path.join(out_dir, f"%(title)s_{ts}_subs.%(ext)s"),
                "quiet": True,
                "ignoreerrors": True,
                "js_runtimes": {"node": {"path": "node"}},
                "remote_components": {"ejs": ["github", "npm"]},
            }
            if os.path.exists(cookie_file):
                sub_opts["cookiefile"] = cookie_file
            try:
                with yt_dlp.YoutubeDL(sub_opts) as sub_ydl:
                    sub_ydl.extract_info(req.url, download=True)
            except Exception as e:
                print(f"Sub download error: {e}")

            ydl_opts["writesubtitles"] = False
            ydl_opts["writeautomaticsub"] = False

        if req.mux and len(formats_to_dl) <= 1:
            ydl_opts["merge_output_format"] = "mkv"
            ydl_opts["outtmpl"] = os.path.join(out_dir, f"%(title)s_{ts}.%(ext)s")
            if req.subtitle_langs:
                ydl_opts["postprocessors"] = [
                    {
                        "key": "FFmpegEmbedSubtitle",
                        "already_have_subtitle": False,
                    }
                ]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(req.url, download=True)

            safe_title = "".join(
                [
                    c
                    for c in info.get("title", "Video")
                    if c.isalpha() or c.isdigit() or c == " " or c == "-" or c == "_"
                ]
            ).strip()
            if not safe_title:
                safe_title = f"Muxed_Video_{ts}"

            downloaded_files = glob.glob(os.path.join(out_dir, f"*{ts}*"))
            format_dict = {str(f.get("format_id")): f for f in info.get("formats", [])}

            # Custom ffmpeg muxing for multiple audio tracks
            if req.mux and len(formats_to_dl) > 1:
                import subprocess  # noqa: PLC0415

                video_file = None
                audio_inputs = []  # dicts: {'file': ..., 'lang': ..., 'title': ...}
                subtitle_inputs = []  # dicts: {'file': ..., 'lang': ...}

                # Classify downloaded files
                seen_sub_langs = set()
                for f in downloaded_files:
                    basename = os.path.basename(f)

                    if basename.endswith(".vtt") or basename.endswith(".srt"):
                        parts = basename.split(".")
                        lang = parts[-2] if len(parts) >= 3 else "und"
                        if lang not in seen_sub_langs:
                            subtitle_inputs.append(
                                {"file": f, "lang": lang, "title": lang}
                            )
                            seen_sub_langs.add(lang)
                        continue

                    name_without_ext = os.path.splitext(basename)[0]
                    parts = name_without_ext.split("_")
                    if len(parts) < 2:
                        continue
                    fmt_id = parts[-1]

                    fmt_info = format_dict.get(fmt_id, {})
                    vcodec = fmt_info.get("vcodec", "none")
                    lang = fmt_info.get("language")

                    if fmt_id in req.audio_format_ids:
                        # It's a selected dub
                        audio_inputs.append(
                            {
                                "file": f,
                                "lang": lang if lang else "und",
                                "title": lang if lang else "Dub",
                            }
                        )
                    else:
                        # It's either bestvideo or bestaudio
                        if vcodec != "none":
                            video_file = f
                        else:
                            # bestaudio
                            audio_inputs.insert(
                                0,
                                {
                                    "file": f,
                                    "lang": info.get("language", "orig"),
                                    "title": "Original",
                                },
                            )

                if video_file and audio_inputs:
                    output_mkv = os.path.join(out_dir, f"{safe_title}.mkv")
                    cmd = ["ffmpeg", "-y", "-i", video_file]

                    for a in audio_inputs:
                        cmd.extend(["-i", a["file"]])
                    for s in subtitle_inputs:
                        cmd.extend(["-i", s["file"]])

                    cmd.extend(["-map", "0:v:0"])

                    # Map audio
                    for i, a in enumerate(audio_inputs):
                        idx = i + 1
                        cmd.extend(["-map", f"{idx}:a:0"])
                        cmd.extend([f"-metadata:s:a:{i}", f"language={a['lang']}"])
                        cmd.extend([f"-metadata:s:a:{i}", f"title={a['title']}"])

                    # Map subtitles
                    sub_start_idx = 1 + len(audio_inputs)
                    for i, s in enumerate(subtitle_inputs):
                        idx = sub_start_idx + i
                        cmd.extend(["-map", f"{idx}:s?"])
                        cmd.extend([f"-metadata:s:s:{i}", f"language={s['lang']}"])
                        cmd.extend([f"-metadata:s:s:{i}", f"title={s['title']}"])
                        # Convert to SRT for better compatibility in MKV
                        cmd.extend([f"-c:s:{i}", "srt"])

                    # Set default audio (Original)
                    cmd.extend(["-disposition:a:0", "default"])
                    for i in range(1, len(audio_inputs)):
                        cmd.extend([f"-disposition:a:{i}", "0"])

                    cmd.extend(["-c:v", "copy", "-c:a", "copy", output_mkv])
                    subprocess.run(cmd, check=True)

                    # Cleanup separate files
                    try:
                        os.remove(video_file)
                        for a in audio_inputs:
                            os.remove(a["file"])
                        for s in subtitle_inputs:
                            os.remove(s["file"])
                    except:  # noqa: E722
                        pass

                    downloaded_files = [output_mkv]

        except Exception as e:
            return {"error": str(e)}
        return {"status": "ok", "downloaded_files": downloaded_files, "folder": out_dir}

    try:
        # Note: In a real app this should be a background task because it takes a long time.
        # But we'll run it in a thread and await it for simplicity since it's just audio/subs.
        data = await asyncio.to_thread(_download)
        if "error" in data:
            raise HTTPException(status_code=500, detail=data["error"])
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # noqa: B904


async def background_self_test():
    """Continuous background task to monitor backend health and log anomalies."""
    logger.info("[SELF-TEST] Background monitor started")
    while True:
        try:
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"[CRITICAL SELF-TEST ERROR] {redact_secrets(str(e))}")
            # Write crash flag to a proper temp location, not cwd
            crash_flag = os.path.join(
                tempfile.gettempdir(), "_autodub_backend_crashed.flag"
            )
            try:
                with open(crash_flag, "w") as f:
                    f.write(redact_secrets(str(e)))
            except Exception:
                pass
            await asyncio.sleep(10)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_self_test())
    asyncio.create_task(send_pending_crash_report())


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
