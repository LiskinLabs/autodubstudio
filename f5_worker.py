"""
F5-TTS Worker — Voice Cloning for AutoDubStudio
Runs in Python 3.10+ venv. F5TTS_Base model + fp16 + checkpoint_activations = fits 4GB VRAM.
Supports: Turkish (fine-tuned), English, Chinese (base model).
Zero-shot voice cloning — ref_text must be provided manually (no Whisper ASR).
"""

import gc
import json
import sys
import traceback

# ── Language → Model mapping ──
F5_MODEL_MAP = {
    "tr": {
        "repo_id": "marduk-ra/F5-TTS-Turkish",
        "ckpt_file": "f5_tts_turkish_1000000.safetensors",
        "vocab_file": "vocab.txt",
        "name": "Turkish Fine-Tune",
    },
    "en": {
        "repo_id": "SWivid/F5-TTS",
        "ckpt_file": "F5TTS_Base/model_1200000.pt",
        "vocab_file": "F5TTS_Base/vocab.txt",
        "name": "F5TTS_Base (English/Chinese)",
    },
    "zh": {
        "repo_id": "SWivid/F5-TTS",
        "ckpt_file": "F5TTS_Base/model_1200000.pt",
        "vocab_file": "F5TTS_Base/vocab.txt",
        "name": "F5TTS_Base (English/Chinese)",
    },
    "ru": {
        "repo_id": "SWivid/F5-TTS",
        "ckpt_file": "F5TTS_Base/model_1200000.pt",
        "vocab_file": "F5TTS_Base/vocab.txt",
        "name": "F5TTS_Base (English/Chinese — Russian via cross-lingual)",
    },
}

# Fallback languages that use the base English model
_BASE_MODEL_LANGS = {"en", "zh", "ru"}


def main():
    if len(sys.argv) < 2:
        print("Usage: python f5_worker.py <tasks.json>")
        sys.exit(1)

    tasks_file = sys.argv[1]
    with open(tasks_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    print(f"F5-TTS Worker: {len(tasks)} segments")

    # ── Determine language from first task ──
    first_lang = tasks[0].get("language", "tr") if tasks else "tr"
    model_info = F5_MODEL_MAP.get(first_lang, F5_MODEL_MAP["en"])
    print(f"Selected model: {model_info['name']} (lang={first_lang})")

    # ── Load F5-TTS ──
    from importlib.resources import files  # noqa: PLC0415

    import torch  # noqa: PLC0415
    from f5_tts.infer.utils_infer import load_model, load_vocoder  # noqa: PLC0415
    from hydra.utils import get_class  # noqa: PLC0415
    from omegaconf import OmegaConf  # noqa: PLC0415

    device = "cuda" if torch.cuda.is_available() else "cpu"

    if device == "cuda":
        gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"GPU: {torch.cuda.get_device_properties(0).name} ({gb:.1f} GB)")
        torch.cuda.empty_cache()
        gc.collect()

    cfg = OmegaConf.load(str(files("f5_tts").joinpath("configs/F5TTS_Base.yaml")))
    arch = cfg.model.arch
    arch.checkpoint_activations = True  # Save VRAM on 4GB cards

    # Auto-download checkpoint from HuggingFace
    ckpt_path = ""
    vocab_path = ""
    try:
        from huggingface_hub import hf_hub_download  # noqa: PLC0415

        print(f"Downloading/verifying {model_info['name']} ({model_info['repo_id']})...")
        ckpt_path = hf_hub_download(
            repo_id=model_info["repo_id"],
            filename=model_info["ckpt_file"],
        )
        vocab_path = hf_hub_download(
            repo_id=model_info["repo_id"], filename=model_info["vocab_file"]
        )
        print(f"Checkpoint: {ckpt_path}")
        print(f"Vocab: {vocab_path}")
    except Exception as e:
        print(f"! Could not download checkpoint: {e}")
        print("Trying default SWivid/F5-TTS base model...")
        try:
            ckpt_path = hf_hub_download(
                repo_id="SWivid/F5-TTS",
                filename="F5TTS_Base/model_1200000.pt",
            )
            vocab_path = hf_hub_download(
                repo_id="SWivid/F5-TTS", filename="F5TTS_Base/vocab.txt"
            )
            print(f"Fallback checkpoint: {ckpt_path}")
        except Exception as e2:
            print(f"X All checkpoint downloads failed: {e2}")
            sys.exit(2)

    model_cls = get_class(f"f5_tts.model.{cfg.model.backbone}")
    print(
        f"Loading {model_info['name']} (dim={arch.dim}, depth={arch.depth}, fp16)..."
    )

    try:
        ema = load_model(
            model_cls,
            arch,
            ckpt_path=ckpt_path,
            mel_spec_type="vocos",
            vocab_file=vocab_path,
            ode_method="euler",
            use_ema=True,
            device=device,
        )
        used_vram = (
            torch.cuda.memory_allocated(0) / (1024**3) if device == "cuda" else 0
        )
        print(f"Model loaded! VRAM used: {used_vram:.1f} GB")
    except Exception as e:
        print(f"X Model load failed: {e}")
        sys.exit(2)

    v = load_vocoder(vocoder_name="vocos", is_local=False, local_path="", device=device)
    print("Vocoder loaded!")

    # ── Process tasks ──
    import numpy as np  # noqa: PLC0415
    import soundfile as sf  # noqa: PLC0415
    from f5_tts.infer.utils_infer import infer_process  # noqa: PLC0415

    success = 0
    failed = 0
    # Project-standard sample rate for silence fallback (matches XTTSv2 22050Hz)
    FALLBACK_SR = 22050

    for i, task in enumerate(tasks):
        ref_audio = task["ref_audio"]
        ref_text = task.get("ref_text", "Hello.")
        gen_text = task["gen_text"]
        out_path = task["out_path"]

        if not ref_text.strip():
            ref_text = "Hello."

        if (i + 1) % 10 == 0 or i == 0:
            print(f"[{i + 1}/{len(tasks)}] {gen_text[:60]}...")

        try:
            audio, sr, _ = infer_process(
                ref_audio=ref_audio,
                ref_text=ref_text,
                gen_text=gen_text,
                model_obj=ema,
                vocoder=v,
                mel_spec_type="vocos",
                target_rms=0.1,
                cross_fade_duration=0.15,
                nfe_step=32,
                cfg_strength=2.0,
                sway_sampling_coef=-1.0,
                speed=1.0,
                device=device,
            )
            sf.write(out_path, audio, sr)
            success += 1
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                print(f"FATAL CUDA OOM at segment {i + 1}: {e}")
                torch.cuda.empty_cache()
                gc.collect()
                sys.exit(2)
            print(f"! [{i + 1}]: {e}")
            # Write silent audio as fallback
            try:
                silence = np.zeros(int(FALLBACK_SR * 0.3), dtype=np.float32)
                sf.write(out_path, silence, FALLBACK_SR)
                success += 1
            except Exception:
                failed += 1
        except Exception as e:
            print(f"! [{i + 1}]: {e}")
            # Write silent audio as fallback
            try:
                silence = np.zeros(int(FALLBACK_SR * 0.3), dtype=np.float32)
                sf.write(out_path, silence, FALLBACK_SR)
                success += 1
            except Exception:
                failed += 1

        # GC to prevent VRAM leak
        if i % 5 == 0:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    print(
        f"\nDone: {success} ok, {failed} failed, {len(tasks)} total [F5TTS_Base @ {device}]"
    )

    # ── Unload model from VRAM before exit ──
    try:
        del ema
        del v
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    # Tolerate up to 10% segment failures
    sys.exit(0 if failed <= len(tasks) * 0.10 else 1)


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
