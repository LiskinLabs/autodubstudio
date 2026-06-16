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

# Add parent directory to path to import engine.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import AutoDubWorker

app = FastAPI(
    title="AutoDubStudio Backend",
    description="Local API for AutoDubStudio Desktop Application",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:1420",
        "tauri://localhost",
        "https://tauri.localhost",
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
    def on_translation_ready(orig, translated, text_segments):
        event_queue.put({"type": "review_ready", "original": orig, "translated": translated, "segments": text_segments})
        
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
                    active_worker.translation_ready_signal.connect(on_translation_ready)
                    
                    active_worker.start()
                    await websocket.send_json({"type": "info", "message": "Pipeline started"})
                    
                elif data.get("action") == "resume":
                    edited_segments = data.get("segments", [])
                    if active_worker:
                        active_worker.resume_with_translations(edited_segments)
                        await websocket.send_json({"type": "info", "message": "Resuming pipeline..."})
                        
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

_model_download_status: dict = {}
_model_download_lock = threading.Lock()

@app.get("/api/models/status")
async def get_model_status():
    """Check which models are cached locally."""
    models_status = {}

    # Check Whisper cache
    whisper_cache = os.path.expanduser("~/.cache/whisper")
    models_status["whisper-large-v3"] = os.path.exists(os.path.join(whisper_cache, "large-v3.pt"))
    models_status["whisper-base"] = os.path.exists(os.path.join(whisper_cache, "base.pt"))

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
                import whisper
                size = model_id.replace("whisper-", "")
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 10
                whisper.load_model(size)
                with _model_download_lock:
                    _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}

            elif model_id == "pyannote-segmentation":
                from pyannote.audio import Pipeline
                token = os.environ.get("HF_TOKEN", os.environ.get("HUGGINGFACE_TOKEN", ""))
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 10
                Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token or True)
                with _model_download_lock:
                    _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}

            elif model_id == "xttsv2":
                from TTS.api import TTS
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 10
                TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False)
                with _model_download_lock:
                    _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}

            elif model_id == "qwen3-tts":
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 10
                # Qwen3-TTS auto-downloads on first use
                from qwen3_worker import Qwen3TTSWorker
                worker = Qwen3TTSWorker()
                worker.load_model()
                with _model_download_lock:
                    _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}

            elif model_id == "f5-tts":
                with _model_download_lock:
                    _model_download_status[model_id]["progress"] = 10
                # F5-TTS auto-downloads on first use
                from f5_worker import F5TTSWorker
                worker = F5TTSWorker()
                worker.load_model()
                with _model_download_lock:
                    _model_download_status[model_id] = {"done": True, "progress": 100, "error": None}

            elif model_id == "gemma4":
                # Pull via Ollama CLI
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
