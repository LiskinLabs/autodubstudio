from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import json
import os
import sys
import time
import logging
import asyncio
import secrets
import httpx
from datetime import datetime

# ── Logging to file ──
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "autodub_backend.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("autodub")
from queue import Queue, Empty
import psutil

# ── Clean up old zombie backend instances ──
try:
    current_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            if cmdline and 'uvicorn' in cmdline and 'backend.main:app' in cmdline and proc.info['pid'] != current_pid:
                print(f"[CLEANUP] Killing old zombie uvicorn process {proc.info['pid']}...")
                proc.terminate()
                proc.wait(timeout=3)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
except Exception as e:
    print(f"[CLEANUP] Error during zombie cleanup: {e}")

# Add parent directory to path to import engine.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import AutoDubWorker

app = FastAPI(
    title="AutoDubStudio Backend",
    description="Local API for AutoDubStudio Desktop Application",
    version="0.0.1-beta",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:1420",
        "tauri://localhost",
        "https://tauri.localhost",
        "http://tauri.localhost"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", "Authorization"],
)

# ── WebSocket auth token (generated fresh each backend startup) ──
WS_AUTH_TOKEN = secrets.token_urlsafe(32)
print(f"[SECURITY] WebSocket auth token: {WS_AUTH_TOKEN[:8]}... (full token shared with frontend)")
print(f"[SECURITY] Backend bound to 127.0.0.1:8000 — no external network access")

class StatusResponse(BaseModel):
    status: str
    message: str

@app.get("/", response_model=StatusResponse)
async def read_root():
    return {"status": "ok", "message": "AutoDubStudio Backend is running"}

@app.get("/api/models")
async def get_models():
    return {
        "models": [
            {"id": "qwen3-tts", "name": "Qwen3-TTS (Русский)", "type": "local"},
            {"id": "xttsv2", "name": "XTTSv2 (Турецкий)", "type": "local"},
            {"id": "f5-tts", "name": "F5-TTS (Мультиязычный Zero-Shot)", "type": "local"},
        ]
    }

@app.get("/api/token")
async def get_ws_token():
    """Frontend fetches this token once to authenticate the WebSocket connection."""
    return {"token": WS_AUTH_TOKEN}

@app.post("/api/ollama/start")
async def start_ollama():
    try:
        import subprocess
        # Try to start ollama serve detached
        subprocess.Popen(
            ["ollama", "serve"],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return {"status": "ok", "message": "Ollama started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ollama/stop")
async def stop_ollama():
    try:
        import psutil
        for proc in psutil.process_iter(['name']):
            if proc.info.get('name') in ['ollama.exe', 'ollama']:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except:
                    pass
        return {"status": "ok", "message": "Ollama stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

active_worker = None

@app.websocket("/ws/pipeline")
async def websocket_pipeline(websocket: WebSocket):
    # ── Authentication: first message must be {"auth": "<token>"} ──
    await websocket.accept()
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        if auth_msg.get("auth") != WS_AUTH_TOKEN:
            await websocket.send_json({"type": "error", "message": "Authentication failed. Invalid token."})
            await websocket.close(code=4001, reason="Unauthorized")
            return
    except asyncio.TimeoutError:
        await websocket.close(code=4001, reason="Auth timeout")
        return

    global active_worker

    event_queue = Queue()
    
    def on_progress(val):
        event_queue.put({"type": "progress", "data": val})
    def on_log(text):
        try:
            print(f"[ENGINE LOG] {text}".encode("utf-8", "replace").decode("utf-8"))
        except Exception:
            pass
        event_queue.put({"type": "log", "data": text})
    def on_finished(success, msg):
        event_queue.put({"type": "finished", "success": success, "message": msg})
    def on_manual_edit(manual_subs):
        orig = [s["orig"] for s in manual_subs]
        trans = [s["trans"] for s in manual_subs]
        event_queue.put({"type": "review_ready", "original": orig, "translated": trans, "segments": manual_subs})
        
    try:
        while True:
            # Handle incoming messages with a timeout
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=0.1)
                
                if data.get("action") == "start":
                    cfg = data.get("config", {})
                    if active_worker and active_worker.is_alive():
                        await websocket.send_json({"type": "error", "message": "Pipeline already running"})
                        continue
                        
                    active_worker = AutoDubWorker(cfg)
                    active_worker.progress_signal.connect(on_progress)
                    active_worker.log_signal.connect(on_log)
                    active_worker.finished_signal.connect(on_finished)
                    active_worker.manual_edit_signal.connect(on_manual_edit)
                    
                    active_worker.start()
                    await websocket.send_json({"type": "info", "message": "Pipeline started"})
                    
                elif data.get("action") == "resume":
                    if PIPELINE_BUSY and active_worker:
                        if "segments" in data:
                            edited = []
                            for s in data["segments"]:
                                edited.append({
                                    "start": s.get("start", 0),
                                    "end": s.get("end", 0),
                                    "text": s.get("trans", s.get("text", "")),
                                    "speaker": s.get("speaker", "SPEAKER_00")
                                })
                            active_worker.edited_segments = edited
                        active_worker.pause_event.set()
                        await websocket.send_json({"type": "info", "message": "Pipeline resumed"})
                        
                elif data.get("action") == "stop":
                    if active_worker:
                        active_worker.requestInterruption()
                        await websocket.send_json({"type": "info", "message": "Stopping..."})
                        
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

# ── Model Download / Status ──
import subprocess
import threading
import time

_model_download_status: dict = {}
_model_download_lock = threading.Lock()
_model_cancel_flags: dict = {}

VALID_MODEL_IDS = {
    "whisper-tiny", "whisper-base", "whisper-small", "whisper-medium",
    "whisper-large-v2", "whisper-large-v3",
    "pyannote-segmentation", "xttsv2", "qwen3-tts", "f5-tts",
    "htdemucs", "gemma4"
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

def _monitor_file_progress(model_id: str, file_path: str, expected_size: int, stop_event: threading.Event):
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
async def get_logs(lines: int = 200):
    """Return recent backend log lines."""
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
                return {"logs": recent, "total": len(all_lines)}
    except Exception:
        pass
    return {"logs": [], "total": 0}


@app.get("/api/models/status")
async def get_model_status():
    """Check which models are cached locally."""
    models_status = {}

    # Check Faster-Whisper cache
    hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
    whisper_ids = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
    for w_id in whisper_ids:
        cache_path = os.path.join(hf_cache, f"models--Systran--faster-whisper-{w_id}")
        models_status[f"whisper-{w_id}"] = os.path.exists(cache_path)

    # Check Pyannote cache (in torch hub, not HF hub)
    torch_pyannote = os.path.expanduser("~/.cache/torch/pyannote")
    pyannote_ok = False
    if os.path.exists(torch_pyannote):
        for root, dirs, _ in os.walk(torch_pyannote):
            if "speaker-diarization" in root.lower():
                pyannote_ok = any(f.endswith(".bin") or f.endswith(".safetensors") for f in os.listdir(root) if os.path.isfile(os.path.join(root, f)))
                if pyannote_ok:
                    break
    models_status["pyannote-segmentation"] = pyannote_ok

    # Check XTTS cache (Windows: %LOCALAPPDATA%/tts, Linux: ~/.local/share/tts)
    xtts_cache = os.environ.get("LOCALAPPDATA", os.path.expanduser("~/.local/share"))
    xtts_cache = os.path.join(xtts_cache, "tts")
    models_status["xttsv2"] = os.path.exists(os.path.join(xtts_cache, "tts_models--multilingual--multi-dataset--xtts_v2"))

    # Check Qwen3-TTS (skip .locks)
    qwen3_cache = os.path.expanduser("~/.cache/huggingface/hub")
    models_status["qwen3-tts"] = False
    if os.path.exists(qwen3_cache):
        for root, dirs, _ in os.walk(qwen3_cache):
            dirs[:] = [d for d in dirs if d != ".locks"]
            if "qwen" in root.lower() and "tts" in root.lower():
                models_status["qwen3-tts"] = True
                break

    # Check F5-TTS (skip .locks dirs — they're not model data)
    models_status["f5-tts"] = False
    if os.path.exists(qwen3_cache):
        for root, dirs, _ in os.walk(qwen3_cache):
            dirs[:] = [d for d in dirs if d != ".locks"]  # skip lock files
            if "f5" in root.lower() and "tts" in root.lower():
                models_status["f5-tts"] = True
                break

    # Check Demucs — model saved as .th file in torch hub checkpoints (~80 MB)
    demucs_cache = os.path.expanduser("~/.cache/torch/hub/checkpoints")
    models_status["htdemucs"] = False
    if os.path.exists(demucs_cache):
        for f in os.listdir(demucs_cache):
            fp = os.path.join(demucs_cache, f)
            if f.endswith(".th") and os.path.isfile(fp) and os.path.getsize(fp) > 50_000_000:
                models_status["htdemucs"] = True
                break

    # Check Gemma 4 via Ollama
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
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
        _model_download_status[model_id] = {"done": False, "progress": 0, "error": "Cancelled"}

    # Clean up partial files
    import shutil
    if model_id.startswith("whisper"):
        size = model_id.replace("whisper-", "")
        cache_dir = os.path.expanduser(f"~/.cache/huggingface/hub/models--Systran--faster-whisper-{size}")
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir, ignore_errors=True)
    elif model_id == "pyannote-segmentation":
        torch_pyannote = os.path.expanduser("~/.cache/torch/pyannote")
        if os.path.exists(torch_pyannote):
            shutil.rmtree(torch_pyannote, ignore_errors=True)

    else:
        return {"status": "error", "message": f"Unknown model: {model_id}"}

    # Clear download status so model shows as not installed
    with _model_download_lock:
        _model_download_status.pop(model_id, None)

    if errors:
        return {"status": "partial", "deleted": deleted_paths, "errors": errors}
    return {"status": "deleted", "paths": deleted_paths}


@app.post("/api/models/preload/{model_id}")
async def preload_model(model_id: str, hf_token: str = ""):
    """Trigger model download via the actual ML library (auto-caches)."""
    if model_id not in VALID_MODEL_IDS:
        raise HTTPException(status_code=400, detail=f"Invalid model ID: {model_id}")
    token = hf_token or os.environ.get("HF_TOKEN", os.environ.get("HUGGINGFACE_TOKEN", ""))

    with _model_download_lock:
        _model_download_status[model_id] = {"done": False, "progress": 0, "error": None}

    def _monitor_dir_size(cache_dir: str, expected_mb: int, start_pct: int = 5, max_pct: int = 95):
        """Shared progress monitor: track directory size growth."""
        os.makedirs(cache_dir, exist_ok=True)
        for _ in range(180):  # Max 6 minutes
            time.sleep(2)
            if _model_cancel_flags.get(model_id):
                return
            try:
                total = 0
                for dirpath, _, filenames in os.walk(cache_dir):
                    for fn in filenames:
                        fp = os.path.join(dirpath, fn)
                        if os.path.isfile(fp):
                            total += os.path.getsize(fp)
                current_mb = total / (1024 * 1024)
                pct = min(start_pct + int((current_mb / max(expected_mb, 1)) * (max_pct - start_pct)), max_pct)
                with _model_download_lock:
                    if _model_download_status.get(model_id, {}).get("done"):
                        return
                    _model_download_status[model_id]["progress"] = max(pct, start_pct)
            except Exception:
                pass

    def _download():
        try:
            if model_id.startswith("whisper"):
                from faster_whisper import WhisperModel
                size = model_id.replace("whisper-", "")

                SIZES_MB = {"tiny": 75, "base": 145, "small": 465, "medium": 1536, "large-v2": 3174, "large-v3": 3174}
                expected_mb = SIZES_MB.get(size, 1500)
                cache_path = os.path.expanduser(f"~/.cache/huggingface/hub/models--Systran--faster-whisper-{size}")

                threading.Thread(target=_monitor_dir_size, args=(cache_path, expected_mb, 1, 90), daemon=True).start()

                try:
                    with _model_download_lock:
                        _model_download_status[model_id]["progress"] = 1
                    WhisperModel(size, device="cpu", compute_type="int8")
                finally:
                    with _model_download_lock:
                        _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}

            elif model_id == "pyannote-segmentation":
                # Run in subprocess to isolate DLL/import issues
                if not token:
                    raise ValueError("HuggingFace token required. Add it in Settings → API Keys → HuggingFace Token.")
                cache_dir = os.path.expanduser("~/.cache/torch/pyannote")
                threading.Thread(target=_monitor_dir_size, args=(cache_dir, 220, 5, 95), daemon=True).start()
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                result = subprocess.run(
                [sys.executable, "-c", """import sys, types
# Fix speechbrain broken lazy imports
import speechbrain.utils.importutils as sb_imports
_orig_getattr = sb_imports.LazyModule.__getattr__
def _safe_getattr(self, attr):
    try: return _orig_getattr(self, attr)
    except ImportError: return types.ModuleType(self.target)
sb_imports.LazyModule.__getattr__ = _safe_getattr

from pyannote.audio import Pipeline
import os
Pipeline.from_pretrained('pyannote/speaker-diarization-3.1', use_auth_token=os.environ['HF_TOKEN'])
print('PYANNOTE_OK')
"""],
                capture_output=True, text=True, timeout=1800,
                env={**os.environ, "HF_TOKEN": token}
            )
                if result.returncode == 0:
                    with _model_download_lock:
                        _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}
                else:
                    raise RuntimeError(result.stderr[:200] or result.stdout[:200] or "Pyannote download failed")

            elif model_id == "xttsv2":
                xtts_venv = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".venv-xtts", "Scripts", "python.exe")
                if not os.path.exists(xtts_venv):
                    xtts_venv = sys.executable
                xtts_cache = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~/.local/share")), "tts")
                threading.Thread(target=_monitor_dir_size, args=(xtts_cache, 1800, 5, 95), daemon=True).start()
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                result = subprocess.run(
                    [xtts_venv, "-c", "from TTS.api import TTS; TTS(model_name='tts_models/multilingual/multi-dataset/xtts_v2', progress_bar=False)"],
                    capture_output=True, text=True, timeout=1800,
                    env={**os.environ, "COQUI_TOS_AGREED": "1"}
                )
                if result.returncode == 0:
                    with _model_download_lock:
                        _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}
                else:
                    raise RuntimeError(result.stderr[:200] or result.stdout[:200] or "XTTS download failed")

            elif model_id == "qwen3-tts":
                from huggingface_hub import snapshot_download
                qwen3_cache = os.path.expanduser("~/.cache/huggingface/hub")
                threading.Thread(target=_monitor_dir_size, args=(qwen3_cache, 2400, 5, 95), daemon=True).start()
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                snapshot_download("Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice")
                snapshot_download("Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
                with _model_download_lock:
                    _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}

            elif model_id == "f5-tts":
                from huggingface_hub import snapshot_download
                f5_cache = os.path.expanduser("~/.cache/huggingface/hub")
                threading.Thread(target=_monitor_dir_size, args=(f5_cache, 1300, 5, 95), daemon=True).start()
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                snapshot_download("SWivid/F5-TTS")
                with _model_download_lock:
                    _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}

            elif model_id == "htdemucs":
                demucs_cache = os.path.expanduser("~/.cache/torch/hub/checkpoints")
                threading.Thread(target=_monitor_dir_size, args=(demucs_cache, 80, 5, 95), daemon=True).start()
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                result = subprocess.run(
                    [sys.executable, "-c", "from demucs import pretrained; pretrained.get_model('htdemucs'); print('htdemucs ready')"],
                    capture_output=True, text=True, timeout=1800
                )
                if result.returncode == 0:
                    with _model_download_lock:
                        _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}
                else:
                    raise RuntimeError(result.stderr[:200] or result.stdout[:200] or "Demucs download failed")

            elif model_id == "gemma4":
                ollama_models = os.path.expanduser("~/.ollama/models")
                threading.Thread(target=_monitor_dir_size, args=(ollama_models, 9600, 5, 95), daemon=True).start()
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                result = subprocess.run(["ollama", "pull", "gemma4:e4b"], capture_output=True, text=True, timeout=3600)
                if result.returncode == 0:
                    with _model_download_lock:
                        _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}
                else:
                    raise RuntimeError(result.stderr[:200] or "ollama pull failed")

            else:
                raise ValueError(f"Unknown model: {model_id}")

        except Exception as e:
            logger.error(f"Download failed: {model_id} — {e}")
            with _model_download_lock:
                _model_download_status[model_id] = {"done": False, "progress": 0, "error": str(e)[:200]}
            # Write crash report AND try to send immediately
            report_crash_to_github(f"Model download failed ({model_id}): {e}")
            # Try sending now (backend is still alive)
            try:
                if GITHUB_TOKEN:
                    title = f"[Bug] Model download failed: {model_id}"
                    body = f"**Model:** {model_id}\n**Error:** {e}\n**Time:** {time.strftime('%Y-%m-%dT%H:%M:%S')}"
                    resp = httpx.post(
                        f"https://api.github.com/repos/{GITHUB_REPO}/issues",
                        json={"title": title, "body": body, "labels": ["bug", "auto-reported"]},
                        headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"},
                        timeout=10
                    )
                    if resp.status_code == 201:
                        logger.info(f"GitHub Issue #{resp.json().get('number')} created for {model_id} failure")
            except Exception:
                pass

    threading.Thread(target=_download, daemon=True).start()
    logger.info(f"Download started: {model_id} (token={'yes' if token else 'no'})")
    return {"status": "started", "model": model_id}


# ── Error Reporting ──
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not GITHUB_TOKEN:
    # Try reading from config.json
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
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
async def set_github_token(data: dict):
    """Receive GitHub token from frontend settings for crash reporting."""
    global GITHUB_TOKEN
    token = data.get("token", "")
    if token:
        GITHUB_TOKEN = token
        print("[CONFIG] GitHub token configured — crash reporting enabled")
        # Send any pending crash report
        send_pending_crash_report()
        return {"status": "ok"}
    return {"status": "error", "message": "No token provided"}

# Rate limiter: max 5 reports per backend session
_error_report_count = 0
_MAX_ERROR_REPORTS = 5

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
        return {"status": "error", "message": "Too many reports this session. Restart backend to reset."}
    _error_report_count += 1

    if not GITHUB_TOKEN:
        return {"status": "error", "message": "GitHub token not configured on backend"}

    title = f"[Bug] {report.error_message[:80]}"
    body = f"""## 🐛 Auto-Reported Error

**Time:** {report.timestamp}
**Version:** {report.version}
**Platform:** {report.platform}
**Language:** {report.language} | Theme: {report.theme}
**Route:** {report.route}

### Error
```
{report.error_message}
```

### Stack Trace
```
{report.error_stack or 'No stack trace'}
```

{chr(10) + '### Component Stack' + chr(10) + '```' + chr(10) + report.error_component_stack + chr(10) + '```' + chr(10) if report.error_component_stack else ''}
### Recent Logs
```
{chr(10).join(report.logs[-40:]) if report.logs else 'No logs captured'}
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
            return {"status": "ok", "message": "Error reported successfully", "url": issue_url}
        else:
            return {"status": "error", "message": f"GitHub API returned {resp.status_code}: {resp.text[:200]}"}

    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}


CRASH_LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "crash_report.json")


def report_crash_to_github(error_msg: str):
    """Write crash info to a file for next-startup reporting."""
    try:
        # Redact PII: replace home dir path with ~
        safe = error_msg[:500].replace(os.path.expanduser("~"), "~")
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


def send_pending_crash_report():
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
        resp = httpx.post(
            f"https://api.github.com/repos/{GITHUB_REPO}/issues",
            json={"title": title, "body": body, "labels": ["bug", "crash"]},
            headers={"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"},
            timeout=10
        )
        resp.encoding = "utf-8"
        if resp.status_code == 201:
            print(f"[CRASH] Sent crash report → GitHub Issue #{resp.json().get('number')}")
        else:
            print(f"[CRASH] Failed to send: HTTP {resp.status_code}")
    except Exception as e:
        print(f"[CRASH] Failed to send crash report: {e}")


if __name__ == "__main__":
    # Send any pending crash reports from previous runs
    send_pending_crash_report()

    try:
        uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
    except Exception as e:
        report_crash_to_github(str(e))
        raise
