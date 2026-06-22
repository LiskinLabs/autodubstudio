"""
AutoDub Studio - Automated Engine Testing (v0.0.1)
Tests ALL Translation x TTS combinations for test_20s.mp4 -> TR, RU.
Generates report with results.
"""
import json, os, sys, time, traceback
from datetime import datetime

TEST_VIDEO = os.path.join(os.path.dirname(__file__), "downloads", "test_20s.mp4")
OUT_DIR = os.path.join(os.path.dirname(__file__), "downloads", "test_reports")
os.makedirs(OUT_DIR, exist_ok=True)

# (target_lang, translation_engine, translator_model, tts_engine, demucs_model)
TEST_CONFIGS = [
    # === TURKISH (tr) ===
    ("tr", "Google Translate (Free)", "default", "xttsv2", "htdemucs_ft"),
    ("tr", "Google Translate (Free)", "default", "f5-tts", "htdemucs_ft"),
    ("tr", "Google Translate (Free)", "default", "edge-tts", "htdemucs_ft"),
    ("tr", "Google Translate (Free)", "default", "f5-onnx", "htdemucs_ft"),
    ("tr", "DeepSeek API", "deepseek-chat", "xttsv2", "htdemucs_ft"),
    ("tr", "DeepSeek API", "deepseek-chat", "f5-tts", "htdemucs_ft"),
    ("tr", "DeepSeek API", "deepseek-chat", "edge-tts", "htdemucs_ft"),
    ("tr", "DeepL API", "deepl-api", "xttsv2", "htdemucs_ft"),
    ("tr", "DeepL API", "deepl-api", "edge-tts", "htdemucs_ft"),
    ("tr", "Ollama", "gemma4:e4b", "xttsv2", "htdemucs_ft"),
    ("tr", "Ollama", "gemma4:e4b", "f5-tts", "htdemucs_ft"),
    ("tr", "Ollama", "gemma4:e4b", "edge-tts", "htdemucs_ft"),
    ("tr", "Google Gemini API", "default", "xttsv2", "htdemucs_ft"),
    ("tr", "Google Gemini API", "default", "edge-tts", "htdemucs_ft"),
    # === RUSSIAN (ru) ===
    ("ru", "Google Translate (Free)", "default", "xttsv2", "htdemucs_ft"),
    ("ru", "Google Translate (Free)", "default", "f5-tts", "htdemucs_ft"),
    ("ru", "Google Translate (Free)", "default", "edge-tts", "htdemucs_ft"),
    ("ru", "DeepSeek API", "deepseek-chat", "xttsv2", "htdemucs_ft"),
    ("ru", "DeepSeek API", "deepseek-chat", "f5-tts", "htdemucs_ft"),
    ("ru", "DeepSeek API", "deepseek-chat", "edge-tts", "htdemucs_ft"),
    ("ru", "DeepL API", "deepl-api", "xttsv2", "htdemucs_ft"),
    ("ru", "DeepL API", "deepl-api", "edge-tts", "htdemucs_ft"),
    ("ru", "Ollama", "gemma4:e4b", "xttsv2", "htdemucs_ft"),
    ("ru", "Ollama", "gemma4:e4b", "edge-tts", "htdemucs_ft"),
    ("ru", "Google Gemini API", "default", "xttsv2", "htdemucs_ft"),
    ("ru", "Google Gemini API", "default", "edge-tts", "htdemucs_ft"),
]


def load_keys():
    keys = {}
    keys["gemini"] = os.environ.get("GEMINI_KEY", "")
    keys["deepseek"] = os.environ.get("DEEPSEEK_KEY", "")
    keys["deepl"] = os.environ.get("DEEPL_KEY", "")
    keys["hf"] = os.environ.get("HF_TOKEN", "")
    cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            cfg = json.load(f)
        for k in ["gemini_key", "deepseek_key", "deepl_key", "hf_key"]:
            if cfg.get(k):
                keys[k.replace("_key", "")] = cfg[k]
    return keys


def test_config(lang, trans_engine, trans_model, tts_engine, demucs_model, keys):
    from PyQt6.QtWidgets import QApplication
    from engine import AutoDubWorker

    app = QApplication.instance() or QApplication(sys.argv)

    config = {
        "video_path": TEST_VIDEO,
        "out_dir": OUT_DIR,
        "target_langs": [lang],
        "whisper_model": "large-v3",
        "device": "cuda",
        "translation_engine": trans_engine,
        "dub_engine": tts_engine,
        "gemini_key": keys.get("gemini", ""),
        "deepseek_key": keys.get("deepseek", ""),
        "deepl_key": keys.get("deepl", ""),
        "hf_key": keys.get("hf", ""),
        "manual_mode": False,
        "ui_language": "ru",
        "demucs_model": demucs_model,
        "auto_mux": True,
        "export_srt": False,
        "keep_intermediate": False,
    }

    result = {"success": False, "message": ""}

    def on_log(msg):
        pass

    def on_finished(success, msg):
        result["success"] = success
        result["message"] = msg

    worker = AutoDubWorker(config)
    worker.log_signal.connect(on_log)
    worker.finished_signal.connect(on_finished)

    start_time = time.time()
    worker.start()
    worker.join(timeout=600)

    if worker.is_alive():
        worker.requestInterruption()
        worker.join(timeout=10)
        return False, "TIMEOUT (10 min)", time.time() - start_time

    return result["success"], result["message"], time.time() - start_time


def main():
    print("=" * 60)
    print("AutoDub Studio - Engine Test Suite")
    print(f"Video: test_20s.mp4 | Configs: {len(TEST_CONFIGS)}")
    print("=" * 60)

    keys = load_keys()
    print(f"Keys: DeepSeek={'OK' if keys['deepseek'] else 'NO'}, "
          f"Gemini={'OK' if keys['gemini'] else 'NO'}, "
          f"DeepL={'OK' if keys['deepl'] else 'NO'}, "
          f"HF={'OK' if keys['hf'] else 'NO'}")

    results = []
    for i, (lang, trans_engine, trans_model, tts_engine, demucs) in enumerate(TEST_CONFIGS):
        name = f"[{lang.upper()}] {trans_engine} + {tts_engine}"
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(TEST_CONFIGS)}] {name}")

        skip_reason = None
        if "DeepL" in trans_engine and not keys["deepl"]:
            skip_reason = "No DeepL key"
        if "Gemini" in trans_engine and not keys["gemini"]:
            skip_reason = "No Gemini key"

        if skip_reason:
            print(f"  SKIP: {skip_reason}")
            results.append({"lang": lang, "translation": trans_engine, "tts": tts_engine,
                           "success": None, "message": skip_reason, "duration": 0})
            continue

        try:
            success, msg, duration = test_config(
                lang, trans_engine, trans_model, tts_engine, demucs, keys
            )
            status = "PASS" if success else "FAIL"
            print(f"  {status} ({duration:.1f}s): {msg[:150]}")
            results.append({
                "lang": lang, "translation": trans_engine, "tts": tts_engine,
                "success": success, "message": msg, "duration": round(duration, 1)
            })
        except Exception as e:
            print(f"  CRASH: {e}")
            traceback.print_exc()
            results.append({
                "lang": lang, "translation": trans_engine, "tts": tts_engine,
                "success": False, "message": f"CRASH: {str(e)[:200]}", "duration": 0
            })

    # Report
    report_path = os.path.join(OUT_DIR, f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({"test_time": datetime.now().isoformat(), "results": results}, f, ensure_ascii=False, indent=2)

    passed = [r for r in results if r["success"] is True]
    failed = [r for r in results if r["success"] is False]
    skipped = [r for r in results if r["success"] is None]

    print("\n" + "=" * 60)
    print(f"RESULTS: {len(passed)} PASS | {len(failed)} FAIL | {len(skipped)} SKIP")
    print("=" * 60)

    if failed:
        print("\nFAILED:")
        for r in failed:
            print(f"  [{r['lang'].upper()}] {r['translation']} + {r['tts']}: {r['message'][:120]}")
    if passed:
        print("\nPASSED:")
        for r in passed:
            print(f"  [{r['lang'].upper()}] {r['translation']} + {r['tts']} ({r['duration']}s)")

    print(f"\nReport: {report_path}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
