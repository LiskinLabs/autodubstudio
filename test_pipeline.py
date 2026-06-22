import sys
import os
# HF_TOKEN загружается из переменных окружения или .env файла
# Для тестирования: установите export HF_TOKEN=your_token перед запуском

from PyQt6.QtWidgets import QApplication
from engine import AutoDubWorker

# Тестовый конфиг — значения по умолчанию, секреты через env vars
config = {
    "video_path": os.environ.get("TEST_VIDEO_PATH", ""),
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

app = QApplication(sys.argv)
worker = AutoDubWorker(config)

def on_log(msg):
    print(f"[LOG] {msg}", flush=True)
worker.log_signal.connect(on_log)

def on_finished(success, message):
    print(f"[FINISHED] Success={success}, Message={message}", flush=True)
    app.quit()
worker.finished_signal.connect(on_finished)

worker.start()
sys.exit(app.exec())
