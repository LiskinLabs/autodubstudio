"""
XTTS v2 Worker — Voice Cloning for AutoDubStudio
Runs on Python 3.11 (separate venv), called as subprocess from main app.
"""

import json
import os
import sys
import traceback

# Automatically accept Coqui TTS license to prevent hanging on input
os.environ["COQUI_TOS_AGREED"] = "1"


def main():
    if len(sys.argv) < 2:
        print("Usage: python xtts_worker.py <tasks.json>")
        sys.exit(1)

    tasks_file = sys.argv[1]
    with open(tasks_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    print(f"XTTS Worker: {len(tasks)} segments")

    import torch  # noqa: PLC0415

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"GPU: {torch.cuda.get_device_properties(0).name} ({gb:.1f} GB)")

    from TTS.api import TTS  # noqa: PLC0415
    from TTS.utils.manage import ModelManager  # noqa: PLC0415

    print("Loading XTTS v2 model...")
    model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
    model_path, _, _ = ModelManager().download_model(model_name)
    tts = TTS(
        model_path=model_path,
        config_path=f"{model_path}/config.json",
        progress_bar=False,
    ).to(device)

    success = 0
    failed = 0

    for i, task in enumerate(tasks):
        ref_audio = task["ref_audio"]
        gen_text = task["gen_text"]
        out_path = task["out_path"]
        language = task.get("language", "tr")

        if (i + 1) % 5 == 0 or i == 0:
            print(f"[{i + 1}/{len(tasks)}] {gen_text[:60]}...")

        try:
            tts.tts_to_file(
                text=gen_text,
                speaker_wav=ref_audio,
                language=language,
                file_path=out_path,
            )
            success += 1
        except Exception as e:
            print(f"! [{i + 1}]: {e}")
            failed += 1
            
        # GC to prevent VRAM leak
        if i % 3 == 0:
            import gc
            import gc; gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    print(f"\nDone: {success} ok, {failed} failed, {len(tasks)} total")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())
        sys.exit(3)
