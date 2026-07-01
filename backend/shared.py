"""Shared state between main.py and engine.py — avoids circular imports."""

import copy
import threading

_pipeline_lock = threading.Lock()

# Исходное состояние — все модели idle (серые индикаторы)
_INITIAL_PIPELINE_STATUS = {
    "active": False,
    "step": "",
    "step_index": 0,
    "total_steps": 6,
    "models": {
        "demucs": "idle",  # idle | running | done | error
        "whisper": "idle",
        "pyannote": "idle",
        "translate": "idle",
        "tts": "idle",
        "mux": "idle",
    },
    "translate_engine": "",  # google / deepl / gemma4 / deepseek / gemini
    "tts_engine": "",  # f5-tts / f5-onnx / xttsv2 / qwen3-tts / edge-tts / azure
    "vram_used_gb": 0.0,
    "vram_total_gb": 0.0,
    "gpu_name": "",
}

pipeline_status = copy.deepcopy(_INITIAL_PIPELINE_STATUS)


def reset_pipeline_status():
    """Сброс статуса пайплайна в исходное состояние (все индикаторы серые).
    Вызывается при 'New Project' и после завершения/ошибки пайплайна."""
    with _pipeline_lock:
        # Сохраняем GPU-инфу (она не зависит от пайплайна)
        gpu_info = {
            "vram_used_gb": pipeline_status.get("vram_used_gb", 0.0),
            "vram_total_gb": pipeline_status.get("vram_total_gb", 0.0),
            "gpu_name": pipeline_status.get("gpu_name", ""),
        }
        # Полный сброс к исходному состоянию
        pipeline_status.clear()
        pipeline_status.update(copy.deepcopy(_INITIAL_PIPELINE_STATUS))
        # Возвращаем GPU-инфу и все динамические ключи со значениями по умолчанию
        pipeline_status.update(gpu_info)
        pipeline_status.setdefault("pytorch_allocated_gb", 0.0)
        pipeline_status.setdefault("pytorch_reserved_gb", 0.0)
