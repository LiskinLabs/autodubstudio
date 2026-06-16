import os
import sys
import time

# Ensure UTF-8
os.environ["PYTHONIOENCODING"] = "utf-8"

from engine import AutoDubWorker

video_path = r"C:\Users\silvestr.liskin\Desktop\AutoDubStudio\downloads\test_20s.mp4"
out_dir = r"C:\Users\silvestr.liskin\Desktop\AutoDubStudio\downloads"

def run_pipeline(lang, translation_engine, dub_engine, tag):
    print(f"\n{'='*70}")
    print(f"  STARTING COMBINATION: {tag}")
    print(f"  Lang: {lang} | Translator: {translation_engine} | TTS: {dub_engine}")
    print(f"{'='*70}\n")
    
    config = {
        "video_path": video_path,
        "out_dir": out_dir,
        "target_langs": [lang],
        "whisper_model": "small",
        "device": "cuda",
        "translation_engine": translation_engine,
        "gemini_key": os.environ.get("GEMINI_API_KEY", ""),
        "dub_engine": dub_engine,
        "manual_mode": False,
        "lip_sync": False,
        "tag": tag
    }
    worker = AutoDubWorker(config)
    start_time = time.time()
    
    def on_log(msg):
        elapsed = time.time() - start_time
        try:
            print(f"  [{elapsed:7.1f}s] [{tag}] {msg}")
        except:
            pass

    def on_finished(success, message):
        print(f"\n  [RESULT - {tag}] Success: {success} | Message: {message}\n")

    worker.log_signal.connect(on_log)
    worker.finished_signal.connect(on_finished)
    
    worker.run()
    
if __name__ == "__main__":
    combinations = [
        # Russian (Gemini API)
        ("ru", "Gemini", "Qwen3-TTS Local", "RU-Gemini-Qwen3"),
        ("ru", "Gemini", "XTTSv2 Local", "RU-Gemini-XTTS"),
        ("ru", "Gemini", "F5-TTS Local", "RU-Gemini-F5"),
        # Turkish (Gemini API)
        ("tr", "Gemini", "Qwen3-TTS Local", "TR-Gemini-Qwen3"),
        ("tr", "Gemini", "XTTSv2 Local", "TR-Gemini-XTTS"),
        ("tr", "Gemini", "F5-TTS Local", "TR-Gemini-F5"),
    ]
    
    for lang, trans, tts, tag in combinations:
        run_pipeline(lang, trans, tts, tag)
        time.sleep(5)
