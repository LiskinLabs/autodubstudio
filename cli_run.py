#!/usr/bin/env python3
"""AutoDubStudio CLI Runner — запуск пайплайна дубляжа из командной строки."""
import os
import sys
import time

# Ensure UTF-8 output on Windows
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from engine import AutoDubWorker

def main():
    video_path = r"C:\Users\silvestr.liskin\Desktop\AutoDubStudio\downloads\New Samsung Dex - One UI 8.5 !.mp4"
    out_dir = r"C:\Users\silvestr.liskin\Desktop\AutoDubStudio\downloads"

    if not os.path.exists(video_path):
        print(f"[FATAL] Video not found: {video_path}")
        sys.exit(1)

    print("=" * 70)
    print("  AutoDubStudio CLI — Full Pipeline Test")
    print("=" * 70)
    print(f"  Video:       {os.path.basename(video_path)}")
    print(f"  Target Lang: ru (Russian)")
    print(f"  Translator:  Ollama qwen2.5:14b")
    print(f"  TTS Engine:  Qwen3-TTS Local")
    print(f"  Whisper:     small (WhisperX)")
    print(f"  Device:      cuda")
    print(f"  Mode:        automatic (no manual review)")
    print("=" * 70)
    print()

    start_time = time.time()

    # Create worker using the dict config
    config = {
        "video_path": video_path,
        "out_dir": out_dir,
        "target_langs": ["ru"],
        "whisper_model": "small",
        "device": "cuda",
        "translation_engine": "Ollama (Local, Free)",
        "dub_engine": "Qwen3-TTS Local",
        "manual_mode": False,
        "lip_sync": True
    }
    worker = AutoDubWorker(config)

    # Connect signals to console output
    def on_log(msg):
        elapsed = time.time() - start_time
        try:
            print(f"  [{elapsed:7.1f}s] {msg}")
        except UnicodeEncodeError:
            safe_msg = msg.encode('ascii', 'replace').decode('ascii')
            print(f"  [{elapsed:7.1f}s] {safe_msg}")

    def on_progress(val):
        try:
            print(f"  [PROGRESS] {val}%")
        except Exception:
            pass

    def on_finished(success, message):
        elapsed = time.time() - start_time
        print()
        print("=" * 70)
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

    # Run synchronously (not as a thread) so we see output in real-time
    print("  Starting pipeline...\n")
    worker.run()

    print("\n  CLI Runner finished.")


if __name__ == "__main__":
    main()
