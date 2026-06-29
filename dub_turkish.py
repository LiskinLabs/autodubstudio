import os
import sys
import time

# Ensure UTF-8 output on Windows
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from engine import AutoDubWorker

def process_video(video_path, out_dir):
    print("=" * 70)
    print(f"  AutoDubStudio - Turkish Dubbing: {os.path.basename(video_path)}")
    print("=" * 70)

    start_time = time.time()

    # Configure the worker for Turkish with F5-TTS
    config = {
        "video_path": video_path,
        "out_dir": out_dir,
        "target_langs": ["tr"],
        "whisper_model": "large-v3-turbo",  # Using a good robust model
        "device": "cuda",
        "translation_engine": "Google Translate (Free)",
        "dub_engine": "Edge-TTS (Cloud, Free, Fast)",
        "manual_mode": False,
        "lip_sync": False,
        "tag": "TR-DUB",
        "user_glossary": "ACP = Agile Certified Practitioner\nScrum = Scrum",
    }
    worker = AutoDubWorker(config)

    def on_log(msg):
        elapsed = time.time() - start_time
        try:
            print(f"  [{elapsed:7.1f}s] {msg}", flush=True)
        except Exception:
            safe_msg = msg.encode("ascii", "replace").decode("ascii")
            print(f"  [{elapsed:7.1f}s] {safe_msg}", flush=True)

    def on_progress(val):
        pass # To avoid spamming, progress can be ignored in log text

    def on_finished(success, message):
        elapsed = time.time() - start_time
        print("\n" + "=" * 70)
        if success:
            print(f"  [OK] Pipeline finished in {elapsed:.1f}s")
            print(f"  Result: {message}")
        else:
            print(f"  [FAIL] Pipeline failed after {elapsed:.1f}s")
            print(f"  Error: {message}")
        print("=" * 70)

    worker.log_signal.connect(on_log)
    worker.progress_signal.connect(on_progress)
    worker.finished_signal.connect(on_finished)

    worker.run()

def main():
    video_dir = r"C:\Users\silvestr.liskin\Desktop\video"
    out_dir = r"C:\Users\silvestr.liskin\Desktop\video\autodub_out"
    os.makedirs(out_dir, exist_ok=True)

    videos = [
        "Atlas_Siva_Kamera_Vida_Kontrol_2.mp4",
        "Atlas_Siva_Kamera_Vida_Kontrol_3.mp4"
    ]

    for video_name in videos:
        video_path = os.path.join(video_dir, video_name)
        if not os.path.exists(video_path):
            print(f"[FATAL] Video not found: {video_path}")
            continue

        process_video(video_path, out_dir)

if __name__ == "__main__":
    main()
