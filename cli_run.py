#!/usr/bin/env python3
"""AutoDubStudio CLI Runner — запуск пайплайна дубляжа из командной строки."""

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


def main():
    # Project-relative paths
    project_dir = os.path.dirname(os.path.abspath(__file__))
    video_path = os.path.join(
        project_dir, "downloads", "New Samsung Dex - One UI 8.5 !.mp4"
    )
    out_dir = os.path.join(project_dir, "downloads")

    if not os.path.exists(video_path):
        print(f"[FATAL] Video not found: {video_path}")
        sys.exit(1)

    # Gemini API — fast cloud translation (no local GPU needed)
    # Set GEMINI_API_KEY in your environment or .env file
    translator_engine = "Google Gemini API [internet, $]"
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_api_key:
        print("[WARN] GEMINI_API_KEY not set — falling back to Google Translate")
        translator_engine = "Google Translate (Free)"
    # Edge-TTS works for all 14 languages, fast and free
    dub_engine = "Edge-TTS (Cloud, Free, Fast)"

    print("=" * 70)
    print("  AutoDubStudio CLI — Full Pipeline Test")
    print("=" * 70)
    print(f"  Video:       {os.path.basename(video_path)}")
    print("  Target Langs: ru (Russian), tr (Turkish)")
    print(f"  Translator:  {translator_engine}")
    print(f"  TTS Engine:  {dub_engine}")
    print("  Whisper:     small")
    print("  Device:      cuda")
    print("  Mode:        automatic (no manual review)")
    print("=" * 70)
    print()

    start_time = time.time()

    config = {
        "video_path": video_path,
        "out_dir": out_dir,
        "target_langs": ["ru", "tr"],
        "whisper_model": "small",
        "device": "cuda",
        "translation_engine": translator_engine,
        "gemini_key": gemini_api_key,
        "dub_engine": dub_engine,
        "manual_mode": False,
        "lip_sync": False,
        "tag": "RU-TR",
    }
    worker = AutoDubWorker(config)

    def on_log(msg):
        elapsed = time.time() - start_time
        try:
            print(f"  [{elapsed:7.1f}s] {msg}")
        except UnicodeEncodeError:
            safe_msg = msg.encode("ascii", "replace").decode("ascii")
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

    print("  Starting pipeline...\n")
    worker.run()

    print("\n  CLI Runner finished.")


if __name__ == "__main__":
    main()
