"""
Qwen3-TTS Worker — Voice Cloning for AutoDubStudio
Supports: ru, en, zh, ja, ko, es, de, fr, pt, it
Zero-shot voice cloning from 3-15 sec reference audio.
Runs on 4+ GB VRAM with 0.6B model (fp16).

Model: Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice (Apache 2.0)
"""

import gc
import json
import os
import sys
import traceback


def main():
    if len(sys.argv) < 2:
        print("Usage: python qwen_worker.py <tasks.json>")
        sys.exit(1)

    tasks_file = sys.argv[1]
    with open(tasks_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    print(f"Qwen3-TTS Worker: {len(tasks)} segments")

    import torch  # noqa: PLC0415

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"GPU: {torch.cuda.get_device_properties(0).name} ({gb:.1f} GB)")
        torch.cuda.empty_cache()
        gc.collect()

    # Qwen3-TTS supported languages
    QWEN_LANGS = {"ru", "en", "zh", "ja", "ko", "es", "de", "fr", "pt", "it"}

    # Map task language to Qwen3-TTS language code
    LANG_MAP = {
        "ru": "ru", "en": "en", "zh": "zh", "ja": "ja", "ko": "ko",
        "es": "es", "de": "de", "fr": "fr", "pt": "pt", "it": "it",
    }

    print("Loading Qwen3-TTS 0.6B CustomVoice model...")
    try:
        from transformers import AutoProcessor, Qwen3TTSForConditionalGeneration  # noqa: PLC0415

        model_id = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
        processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        model = Qwen3TTSForConditionalGeneration.from_pretrained(
            model_id,
            trust_remote_code=True,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        ).to(device)
        model.eval()

        used_vram = torch.cuda.memory_allocated(0) / (1024**3) if device == "cuda" else 0
        print(f"Model loaded! VRAM used: {used_vram:.1f} GB")
    except ImportError as e:
        print(f"! Qwen3-TTS not installed: {e}")
        print("  Install: pip install transformers>=4.51.0 accelerate")
        sys.exit(4)
    except Exception as e:
        print(f"X Model load failed: {e}")
        sys.exit(2)

    import soundfile as sf  # noqa: PLC0415

    success = 0
    failed = 0

    for i, task in enumerate(tasks):
        ref_audio = task["ref_audio"]
        gen_text = task["gen_text"]
        out_path = task["out_path"]
        language = task.get("language", "ru")

        # Map to Qwen language code
        qwen_lang = LANG_MAP.get(language, "en")
        if qwen_lang not in QWEN_LANGS:
            print(f"! [{i + 1}]: language '{language}' not supported by Qwen3-TTS, using 'en'")
            qwen_lang = "en"

        if (i + 1) % 5 == 0 or i == 0:
            print(f"[{i + 1}/{len(tasks)}] [{qwen_lang}] {gen_text[:60]}...")

        try:
            # Qwen3-TTS zero-shot voice cloning
            inputs = processor(
                text=gen_text,
                return_tensors="pt",
            ).to(device)

            # Load and process reference audio for voice cloning
            ref_audio_tensor, ref_sr = sf.read(ref_audio)
            if len(ref_audio_tensor.shape) > 1:
                ref_audio_tensor = ref_audio_tensor.mean(axis=1)  # mono
            ref_audio_tensor = torch.from_numpy(ref_audio_tensor).float().to(device)

            # Resample to 16kHz if needed
            if ref_sr != 16000:
                import torchaudio.functional as F  # noqa: PLC0415
                if ref_sr != 16000:
                    ref_audio_tensor = F.resample(
                        ref_audio_tensor.unsqueeze(0),
                        orig_freq=ref_sr,
                        new_freq=16000,
                    ).squeeze(0)

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    speaker_audio=ref_audio_tensor,
                    language=qwen_lang,
                    max_new_tokens=2048,
                )

            audio = outputs.audio[0].cpu().numpy()
            sample_rate = outputs.sample_rate

            sf.write(out_path, audio, sample_rate)
            success += 1

        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                print(f"FATAL CUDA OOM at segment {i + 1}: {e}")
                torch.cuda.empty_cache()
                gc.collect()
                sys.exit(2)
            print(f"! [{i + 1}]: {e}")
            failed += 1
        except Exception as e:
            print(f"! [{i + 1}]: {e}")
            failed += 1

        # GC to prevent VRAM leak
        if i % 3 == 0:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    print(f"\nDone: {success} ok, {failed} failed, {len(tasks)} total [Qwen3-TTS @ {device}]")

    # Unload model from VRAM before exit
    try:
        del model
        del processor
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        if "out of memory" in str(e).lower():
            print(f"FATAL CUDA OOM: {e}")
            try:
                gc.collect()
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            sys.exit(2)
        print(traceback.format_exc())
        sys.exit(3)
    except Exception:
        print(traceback.format_exc())
        sys.exit(3)
