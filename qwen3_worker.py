import json
import os
import sys

import soundfile as sf
import torch

# Ensure qwen_tts can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Qwen3-TTS"))

from qwen_tts import Qwen3TTSModel


def generate_batch(tasks_file, model_name="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice", language="Russian", speaker="Vivian"):
    print(f"🔄 Initializing {model_name} for {language}...", file=sys.stderr)
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = Qwen3TTSModel.from_pretrained(
            model_name,
            device_map=device,
            dtype=torch.bfloat16 if device == "cuda" else torch.float32,
            attn_implementation="sdpa"
        )

        with open(tasks_file, 'r', encoding='utf-8-sig') as f:
            tasks = json.load(f)

        print(f"🎙️ Generating voice for {len(tasks)} segments...", file=sys.stderr)
        success = 0
        failed = 0
        for task in tasks:
            out_path = task["out_path"]
            text = task["gen_text"]

            # Map languages (ru -> Russian, en -> English, etc.)
            # Quick default to Russian for Qwen3 if not provided explicitly in tasks

            try:
                wavs, sr = model.generate_custom_voice(
                    text=text,
                    language=language,
                    speaker=speaker
                )
                sf.write(out_path, wavs[0], sr)
                success += 1
                print(f"✅ Generated: {out_path}", file=sys.stderr)
            except Exception as e:
                failed += 1
                import traceback
                print(f"❌ Failed for segment {out_path}: {e}\n{traceback.format_exc()}", file=sys.stderr)

        print(f"\nDone: {success} ok, {failed} failed, {len(tasks)} total", file=sys.stderr)

        del model
        if device == "cuda":
            torch.cuda.empty_cache()
        import gc; gc.collect()

        if failed > 0:
            sys.exit(1)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Qwen3-TTS Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python qwen3_worker.py <tasks.json> <model_name> [language] [speaker]")
        sys.exit(1)

    tasks_file = sys.argv[1]
    model_name = sys.argv[2]
    lang = sys.argv[3] if len(sys.argv) > 3 else "Russian"
    spk = sys.argv[4] if len(sys.argv) > 4 else "Vivian"

    generate_batch(tasks_file, model_name, lang, spk)
