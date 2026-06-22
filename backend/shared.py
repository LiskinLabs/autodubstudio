"""Shared state between main.py and engine.py — avoids circular imports."""

import threading

_pipeline_lock = threading.Lock()

# Исходное состояние — все модели idle (серые индикаторы)
_INITIAL_PIPELINE_STATUS = {
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

pipeline_status = dict(_INITIAL_PIPELINE_STATUS)


def reset_pipeline_status():
    """Сброс статуса пайплайна в исходное состояние (все индикаторы серые).
    Вызывается при 'New Project' и после завершения/ошибки пайплайна."""
    with _pipeline_lock:
        for key in pipeline_status:
            if key == "models":
                pipeline_status["models"] = dict(_INITIAL_PIPELINE_STATUS["models"])
            elif key in ("vram_used_gb", "vram_total_gb", "gpu_name"):
                pass  # keep GPU info
            else:
                pipeline_status[key] = _INITIAL_PIPELINE_STATUS[key]
