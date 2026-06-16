from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import json
import os
import sys
import asyncio
import secrets
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

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
