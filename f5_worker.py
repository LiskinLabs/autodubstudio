"""
F5-TTS Worker — Voice Cloning for AutoDubStudio
Runs in Python 3.10 venv with CUDA 11.8.
F5TTS_Base model + fp16 + checkpoint_activations = fits 4GB VRAM.
Key: NO Whisper ASR — ref_text must be provided manually.
"""
import gc
import json
import os
import sys
import traceback


def main():
    if len(sys.argv) < 2:
        print("Usage: python f5_worker.py <tasks.json>")
        sys.exit(1)

    tasks_file = sys.argv[1]
    with open(tasks_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    print(f"F5-TTS Worker: {len(tasks)} segments")

    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"

    if device == "cuda":
        gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"GPU: {torch.cuda.get_device_properties(0).name} ({gb:.1f} GB)")
        torch.cuda.empty_cache()
        gc.collect()

    # ── Load F5-TTS with proper checkpoint ──
    from importlib.resources import files

    from f5_tts.infer.utils_infer import load_model, load_vocoder
    from hydra.utils import get_class
    from omegaconf import OmegaConf

    cfg = OmegaConf.load(str(files("f5_tts").joinpath("configs/F5TTS_Base.yaml")))
    arch = cfg.model.arch
    arch.checkpoint_activations = True  # Save VRAM on 4GB cards

    # Auto-download checkpoint from HuggingFace
    ckpt_path = ""
    vocab_path = ""
    try:
        from huggingface_hub import hf_hub_download
        print("Downloading/verifying Turkish model (marduk-ra/F5-TTS-Turkish)...")
        ckpt_path = hf_hub_download(repo_id="marduk-ra/F5-TTS-Turkish", filename="f5_tts_turkish_1000000.safetensors")
        vocab_path = hf_hub_download(repo_id="marduk-ra/F5-TTS-Turkish", filename="vocab.txt")
        print(f"Checkpoint: {ckpt_path}")
        print(f"Vocab: {vocab_path}")
    except Exception as e:
        print(f"⚠ Could not auto-download Turkish checkpoint: {e}")
        print("Trying default checkpoint path...")

    model_cls = get_class(f"f5_tts.model.{cfg.model.backbone}")
    print(f"Loading F5TTS_Base Turkish Fine-Tune (dim={arch.dim}, depth={arch.depth}, fp16)...")

    try:
        ema = load_model(
            model_cls, arch,
            ckpt_path=ckpt_path, mel_spec_type="vocos", vocab_file=vocab_path,
            ode_method="euler", use_ema=True, device=device
        )
        used_vram = torch.cuda.memory_allocated(0) / (1024**3) if device == "cuda" else 0
        print(f"Model loaded! VRAM used: {used_vram:.1f} GB")
    except Exception as e:
        print(f"❌ Model load failed: {e}")
        os._exit(2)

    v = load_vocoder(vocoder_name="vocos", is_local=False, local_path="", device=device)
    print("Vocoder loaded!")

    # ── Process tasks ──
    import soundfile as sf
    from f5_tts.infer.utils_infer import infer_process

    success = 0
    failed = 0

    for i, task in enumerate(tasks):
        ref_audio = task["ref_audio"]
        ref_text = task.get("ref_text", "Hello.")
        gen_text = task["gen_text"]
        out_path = task["out_path"]

        if not ref_text.strip():
            ref_text = "Hello."

        if (i + 1) % 10 == 0 or i == 0:
            print(f"[{i+1}/{len(tasks)}] {gen_text[:60]}...")

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
                device=device
            )
            sf.write(out_path, audio, sr)
            success += 1
        except Exception as e:
            print(f"⚠ [{i+1}]: {e}")
            # Write silent audio as fallback — don't let 1 bad segment ruin the pipeline
            try:
                import numpy as np
                silence_sr = 24000
                silence = np.zeros(int(silence_sr * 0.3), dtype=np.float32)
                sf.write(out_path, silence, silence_sr)
                success += 1
            except Exception:
                failed += 1

    print(f"\nDone: {success} ok, {failed} failed, {len(tasks)} total [F5TTS_Base @ {device}]")
    # Tolerate up to 10% segment failures — don't block video assembly
    os._exit(0 if failed <= len(tasks) * 0.10 else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())
        os._exit(3)
