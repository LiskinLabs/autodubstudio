import os

# HF_TOKEN загружается из переменных окружения или .env файла
# Для тестирования: установите export HF_TOKEN=your_token перед запуском
from engine import AutoDubWorker

# Тестовый конфиг — значения по умолчанию, секреты через env vars
video_path = os.environ.get("TEST_VIDEO_PATH", "")
if not video_path:
    print("[SKIP] TEST_VIDEO_PATH not set, skipping pipeline test.")
    os._exit(0)

config = {
    "video_path": video_path,
    "out_dir": os.environ.get("TEST_OUT_DIR", "."),
    "target_langs": ["tr"],
    "whisper_model": "small",
    "device": "cuda",
    "translation_engine": "DeepSeek API",
    "gemini_key": os.environ.get("GEMINI_KEY", ""),
    "dub_engine": "XTTS v2 (Local/CUDA)",
    "manual_mode": False,
    "lip_sync": False,
    "tag": "TEST",
}

worker = AutoDubWorker(config)


def on_log(msg):
    print(f"[LOG] {msg}", flush=True)


worker.log_signal.connect(on_log)


def on_finished(success, message):
    print(f"[FINISHED] Success={success}, Message={message}", flush=True)
    import os  # noqa: PLC0415

    os._exit(0) if success else os._exit(1)


worker.finished_signal.connect(on_finished)

worker.start()
worker.join()
