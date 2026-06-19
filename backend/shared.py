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
    "translate_engine": "",  # google / deepl / gemma4 / deepseek / gemini
    "tts_engine": "",        # f5-tts / f5-onnx / xttsv2 / qwen3-tts / edge-tts / azure
    "vram_used_gb": 0.0,
    "vram_total_gb": 0.0,
    "gpu_name": "",
}
