#!/usr/bin/env python3
"""
AutoDubStudio — CLI Test Runner v2
Запускает пайплайн дубляжа с разными комбинациями движков перевода и TTS.
Использует engine.py напрямую (не через WebSocket).
"""
import os, sys, time, json, traceback

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import AutoDubWorker

VIDEO = os.path.join(os.path.dirname(__file__), "downloads", "test_20s.mp4")
OUT_DIR = os.path.join(os.path.dirname(__file__), "downloads", "test_output")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Language-TTS compatibility matrix ──
TTS_COMPAT = {
    "Edge-TTS (Cloud, Free, Fast)": ["ru", "en", "tr"],
    "Qwen3-TTS Local": ["ru", "en"],           # NO Turkish!
    "XTTSv2 Local": ["ru", "en", "tr"],
    "F5-TTS Local": ["ru", "en", "tr"],
}

def is_tts_compatible(tts_engine, lang):
    allowed = TTS_COMPAT.get(tts_engine, [])
    return lang in allowed

def run_test(name, config):
    """Run one pipeline test and return (success, message, duration)."""
    print(f"\n{'='*70}")
    print(f"  TEST: {name}")
    print(f"  Config: {json.dumps(config, indent=2)}")
    print(f"{'='*70}")

    # Validate TTS-language compatibility
    lang = list(config.get("target_langs", ["en"]))[0]
    tts = config.get("dub_engine", "")
    if not is_tts_compatible(tts, lang):
        msg = f"SKIP: {tts} does not support language '{lang}'. Compatible: {TTS_COMPAT.get(tts, [])}"
        print(f"  ⚠ {msg}")
        return (False, msg, 0)

    start = time.time()
    worker = AutoDubWorker(config)

    last_log = [""]
    def on_log(msg):
        elapsed = time.time() - start
        try:
            clean = str(msg).strip()
            if clean and clean != last_log[0]:
                print(f"  [{elapsed:6.1f}s] {clean}")
                last_log[0] = clean
        except Exception:
            pass

    def on_progress(val):
        print(f"  [PROGRESS] {val}%")

    result = {"success": False, "message": ""}
    def on_finished(success, msg):
        result["success"] = success
        result["message"] = str(msg)

    worker.log_signal.connect(on_log)
    worker.progress_signal.connect(on_progress)
    worker.finished_signal.connect(on_finished)

    worker.run()

    duration = time.time() - start
    status = "PASS" if result["success"] else "FAIL"
    print(f"  [{status}] {result['message']} ({duration:.1f}s)")
    return (result["success"], result["message"], duration)


def main():
    if not os.path.exists(VIDEO):
        print(f"FATAL: Video not found: {VIDEO}")
        sys.exit(1)

    all_tests = [
        # ── RU Tests ──
        ("RU | Ollama + Edge-TTS", {
            "video_path": VIDEO, "out_dir": OUT_DIR, "target_langs": ["ru"],
            "whisper_model": "small", "device": "cuda",
            "translation_engine": "Ollama (Local, Free)",
            "dub_engine": "Edge-TTS (Cloud, Free, Fast)",
            "manual_mode": False, "lip_sync": False, "tag": "ru_ollama_edge"
        }),
        ("RU | Google + Edge-TTS", {
            "video_path": VIDEO, "out_dir": OUT_DIR, "target_langs": ["ru"],
            "whisper_model": "small", "device": "cuda",
            "translation_engine": "Google Translate (Free)",
            "dub_engine": "Edge-TTS (Cloud, Free, Fast)",
            "manual_mode": False, "lip_sync": False, "tag": "ru_google_edge"
        }),
        ("RU | Ollama + XTTSv2", {
            "video_path": VIDEO, "out_dir": OUT_DIR, "target_langs": ["ru"],
            "whisper_model": "small", "device": "cuda",
            "translation_engine": "Ollama (Local, Free)",
            "dub_engine": "XTTSv2 Local",
            "manual_mode": False, "lip_sync": False, "tag": "ru_ollama_xtts"
        }),
        # ── TR Tests ──
        ("TR | Ollama + Edge-TTS", {
            "video_path": VIDEO, "out_dir": OUT_DIR, "target_langs": ["tr"],
            "whisper_model": "small", "device": "cuda",
            "translation_engine": "Ollama (Local, Free)",
            "dub_engine": "Edge-TTS (Cloud, Free, Fast)",
            "manual_mode": False, "lip_sync": False, "tag": "tr_ollama_edge"
        }),
        ("TR | Google + Edge-TTS", {
            "video_path": VIDEO, "out_dir": OUT_DIR, "target_langs": ["tr"],
            "whisper_model": "small", "device": "cuda",
            "translation_engine": "Google Translate (Free)",
            "dub_engine": "Edge-TTS (Cloud, Free, Fast)",
            "manual_mode": False, "lip_sync": False, "tag": "tr_google_edge"
        }),
        ("TR | Ollama + XTTSv2", {
            "video_path": VIDEO, "out_dir": OUT_DIR, "target_langs": ["tr"],
            "whisper_model": "small", "device": "cuda",
            "translation_engine": "Ollama (Local, Free)",
            "dub_engine": "XTTSv2 Local",
            "manual_mode": False, "lip_sync": False, "tag": "tr_ollama_xtts"
        }),
        # ── Validation tests: Qwen3-TTS for TR should be BLOCKED ──
        ("TR | Ollama + Qwen3-TTS [SHOULD SKIP]", {
            "video_path": VIDEO, "out_dir": OUT_DIR, "target_langs": ["tr"],
            "whisper_model": "small", "device": "cuda",
            "translation_engine": "Ollama (Local, Free)",
            "dub_engine": "Qwen3-TTS Local",
            "manual_mode": False, "lip_sync": False, "tag": "tr_ollama_qwen3_blocked"
        }),
    ]

    results = []
    for name, cfg in all_tests:
        try:
            ok, msg, dur = run_test(name, cfg)
            results.append((name, ok, msg, dur))
        except Exception as e:
            print(f"  [CRASH] {e}")
            traceback.print_exc()
            results.append((name, False, str(e), 0))

    # ── Summary ──
    print(f"\n{'='*70}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*70}")
    passed = sum(1 for r in results if r[1])
    skipped = sum(1 for r in results if "SKIP" in str(r[2]))
    failed = sum(1 for r in results if not r[1] and "SKIP" not in str(r[2]))
    for name, ok, msg, dur in results:
        icon = "PASS" if ok else ("SKIP" if "SKIP" in msg else "FAIL")
        print(f"  [{icon}] {name} ({dur:.0f}s) — {msg[:80]}")
    print(f"\n  Total: {len(results)} | Pass: {passed} | Fail: {failed} | Skip: {skipped}")


if __name__ == "__main__":
    main()
