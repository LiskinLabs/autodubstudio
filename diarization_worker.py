import json
import os
import sys
import traceback
import warnings

warnings.filterwarnings("ignore")

import huggingface_hub
import torch

# --- MONKEYPATCH FOR PYANNOTE 3.1 & HUGGINGFACE_HUB >= 0.23 ---
original_hf_hub_download = huggingface_hub.hf_hub_download


def patched_hf_hub_download(*args, **kwargs):
    if "use_auth_token" in kwargs:
        kwargs["token"] = kwargs.pop("use_auth_token")
    return original_hf_hub_download(*args, **kwargs)


huggingface_hub.hf_hub_download = patched_hf_hub_download
import pyannote.audio.core.pipeline

pyannote.audio.core.pipeline.hf_hub_download = patched_hf_hub_download
import pyannote.audio.pipelines.utils.getter

pyannote.audio.pipelines.utils.getter.hf_hub_download = patched_hf_hub_download
# -------------------------------------------------------------


def main():
    if len(sys.argv) < 3:
        print("Usage: python diarization_worker.py <input_audio.wav> <output.json>")
        print("  HF_TOKEN is read from environment variable (more secure than argv).")
        sys.exit(1)

    audio_path = sys.argv[1]
    output_json = sys.argv[2]
    hf_token = os.environ.get("HF_TOKEN", "")

    if not os.path.exists(audio_path):
        print(f"File not found: {audio_path}")
        sys.exit(1)

    print("Starting Pyannote Diarization 3.1...")
    print("Audio: [path omitted to avoid encoding crash]")

    try:
        from pyannote.audio import Pipeline  # noqa: PLC0415
    except ImportError:
        print("Error: pyannote.audio is not installed in the current environment!")
        print("Run: pip install pyannote.audio")
        sys.exit(2)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    try:
        hf_token = hf_token.strip()
        if not hf_token:
            print("Error: HF_TOKEN is empty! Pyannote 3.1 requires a valid Hugging Face token. Set it in the settings.")
            sys.exit(3)
        # Use use_auth_token= (compatible with pyannote 3.1 depending on hf_hub version)
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token,
        )
        if torch.cuda.is_available():
            pipeline.to(device)
    except Exception as e:
        print(f"Error loading Pyannote model (check HF Token and access): {e}")
        sys.exit(3)

    print("Analyzing audio (this might take a while)...")
    try:
        diarization = pipeline(audio_path)
    except Exception as e:
        print(f"Error processing audio: {e}")
        sys.exit(4)

    results = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        results.append(
            {
                "start": round(turn.start, 2),
                "end": round(turn.end, 2),
                "speaker": speaker,
            }
        )

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    unique_speakers = set(r["speaker"] for r in results)  # noqa: C401
    print(f"✅ Diarization complete. Found unique speakers: {len(unique_speakers)}")
    print("Result saved successfully.")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())
        sys.exit(5)
