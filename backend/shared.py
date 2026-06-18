"""Shared state between main.py and engine.py — avoids circular imports."""

pipeline_status = {
    "active": False,
    "step": "",
    "step_index": 0,
    "total_steps": 6,
    "models": {
        "demucs": "idle",      # idle | running | done | error
        "whisper": "idle",
        "pyannote": "idle",
        "translate": "idle",
        "tts": "idle",
        "mux": "idle",
    },
    "vram_used_gb": 0.0,
    "vram_total_gb": 0.0,
    "gpu_name": "",
}
