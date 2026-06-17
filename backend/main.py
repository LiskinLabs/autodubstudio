from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import json
import os
import sys
import asyncio
import secrets
import httpx
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
    allow_methods=["GET", "POST", "OPTIONS"],
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

    # Check Pyannote cache
    hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
    pyannote_ok = False
    if os.path.exists(hf_cache):
        for root, dirs, _ in os.walk(hf_cache):
            if "pyannote" in root.lower() and "speaker-diarization" in root.lower():
                pyannote_ok = any(f.endswith(".bin") or f.endswith(".safetensors") for f in os.listdir(root) if os.path.isfile(os.path.join(root, f)))
    models_status["pyannote-segmentation"] = pyannote_ok

    # Check XTTS cache
    xtts_cache = os.path.expanduser("~/.local/share/tts")
    models_status["xttsv2"] = os.path.exists(os.path.join(xtts_cache, "tts_models--multilingual--multi-dataset--xtts_v2"))

    # Check Qwen3-TTS (checks if model files exist)
    qwen3_cache = os.path.expanduser("~/.cache/huggingface/hub")
    models_status["qwen3-tts"] = False
    if os.path.exists(qwen3_cache):
        for root, dirs, _ in os.walk(qwen3_cache):
            if "qwen" in root.lower() and "tts" in root.lower():
                models_status["qwen3-tts"] = True
                break

    # Check F5-TTS
    models_status["f5-tts"] = False
    if os.path.exists(qwen3_cache):
        for root, dirs, _ in os.walk(qwen3_cache):
            if "f5" in root.lower() and "tts" in root.lower():
                models_status["f5-tts"] = True
                break

    # Check Demucs (htdemucs model)
    demucs_cache = os.path.expanduser("~/.cache/torch/hub/checkpoints")
    models_status["htdemucs"] = False
    if os.path.exists(demucs_cache):
        for f in os.listdir(demucs_cache):
            if "htdemucs" in f.lower() or "demucs" in f.lower():
                models_status["htdemucs"] = True
                break
    # Also check if demucs package is installed (model auto-downloads on first use)
    if not models_status["htdemucs"]:
        try:
            result = subprocess.run([sys.executable, "-m", "demucs", "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                models_status["htdemucs"] = True  # Package installed = model available
        except Exception:
            pass

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

@app.post("/api/models/preload/{model_id}")
async def preload_model(model_id: str):
    """Trigger model download via the actual ML library (auto-caches)."""
    with _model_download_lock:
        _model_download_status[model_id] = {"done": False, "progress": 0, "error": None}

    def _download():
        try:
            if model_id.startswith("whisper"):
                from faster_whisper import WhisperModel
                size = model_id.replace("whisper-", "")

                try:
                    with _model_download_lock:
                        _model_download_status[model_id]["progress"] = 1
                    WhisperModel(size, device="cpu", compute_type="int8")
                finally:
                    pass

                with _model_download_lock:
                    _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}

            elif model_id == "pyannote-segmentation":
                from pyannote.audio import Pipeline
                token = os.environ.get("HF_TOKEN", os.environ.get("HUGGINGFACE_TOKEN", ""))
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token or True)
                with _model_download_lock:
                    _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}

            elif model_id == "xttsv2":
                # XTTS must run in its own venv (TTS package not in main venv)
                xtts_venv = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".venv-xtts", "Scripts", "python.exe")
                if not os.path.exists(xtts_venv):
                    xtts_venv = sys.executable  # fallback
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
                # Qwen3-TTS must run in its own venv
                qwen3_venv = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".venv-qwen3-tts", "Scripts", "python.exe")
                if not os.path.exists(qwen3_venv):
                    qwen3_venv = sys.executable
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                result = subprocess.run(
                    [qwen3_venv, "-c", "from qwen3_worker import Qwen3TTSWorker; w = Qwen3TTSWorker(); w.load_model()"],
                    capture_output=True, text=True, timeout=1800,
                    env={**os.environ, "PYTHONPATH": os.path.dirname(os.path.dirname(__file__))}
                )
                if result.returncode == 0:
                    with _model_download_lock:
                        _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}
                else:
                    raise RuntimeError(result.stderr[:200] or result.stdout[:200] or "Qwen3-TTS download failed")

            elif model_id == "f5-tts":
                # F5-TTS must run in its own venv
                f5_venv = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".venv-f5", "Scripts", "python.exe")
                if not os.path.exists(f5_venv):
                    f5_venv = sys.executable
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                result = subprocess.run(
                    [f5_venv, "-c", "from f5_worker import F5TTSWorker; w = F5TTSWorker(); w.load_model()"],
                    capture_output=True, text=True, timeout=1800,
                    env={**os.environ, "PYTHONPATH": os.path.dirname(os.path.dirname(__file__))}
                )
                if result.returncode == 0:
                    with _model_download_lock:
                        _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}
                else:
                    raise RuntimeError(result.stderr[:200] or result.stdout[:200] or "F5-TTS download failed")

            elif model_id == "htdemucs":
                # Demucs downloads automatically on first use
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 5
                result = subprocess.run(
                    [sys.executable, "-m", "demucs", "--version"],
                    capture_output=True, text=True, timeout=30
                )
                # Just verifying demucs is installed triggers model availability check
                # The actual model downloads on first separation run
                if result.returncode == 0:
                    with _model_download_lock:
                        _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}
                else:
                    # Demucs not installed in main venv either, try pip install
                    result2 = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "demucs"],
                        capture_output=True, text=True, timeout=300
                    )
                    if result2.returncode == 0:
                        with _model_download_lock:
                            _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}
                    else:
                        raise RuntimeError(f"Demucs install failed: {result2.stderr[:200]}")

            elif model_id == "gemma4":
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
            with _model_download_lock:
                _model_download_status[model_id] = {"done": False, "progress": 0, "error": str(e)[:200]}

    threading.Thread(target=_download, daemon=True).start()
    return {"status": "started", "model": model_id}


# ── Error Reporting ──
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not GITHUB_TOKEN:
    print("[WARNING] GITHUB_TOKEN not set — error reporting disabled")
GITHUB_REPO = "LiskinLabs/autodubstudio"

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


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
