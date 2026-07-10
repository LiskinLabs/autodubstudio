import json
import os
import sys
import traceback
import warnings

warnings.filterwarnings("ignore")


def detect_language(audio_path, output_json, device="cpu"):
    try:
        from speechbrain.inference.classifiers import EncoderClassifier

        print(f"[SpeechBrain] Loading lang-id model on {device}...")
        # voxlingua107-ecapa is ~80MB and detects 107 languages
        classifier = EncoderClassifier.from_hparams(
            source="speechbrain/lang-id-voxlingua107-ecapa",
            savedir=os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AutoDub Studio", "models", "speechbrain_models"),
            run_opts={"device": device}
        )

        print(f"[SpeechBrain] Analyzing {audio_path}...")
        signal = classifier.load_audio(audio_path)
        prediction = classifier.classify_batch(signal)

        # e.g., prediction[3][0] is the string label like "en: English"
        lang_label = prediction[3][0]
        # Extract just the 2-letter or 3-letter code if possible, or keep full
        lang_code = lang_label.split(":")[0].strip() if ":" in lang_label else lang_label

        out = {
            "status": "success",
            "language": lang_code,
            "full_label": lang_label
        }

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)

        print(f"[SpeechBrain] Detected language: {lang_label}")

    except Exception as e:
        print(f"[SpeechBrain] Error: {e}")
        traceback.print_exc()
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump({"status": "error", "error": str(e)}, f)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python lang_worker.py <params_json_string>")
        sys.exit(1)

    params = json.loads(sys.argv[1])
    audio_path = params.get("audio_path")
    output_json = params.get("output_json")
    device = params.get("device", "cpu")

    detect_language(audio_path, output_json, device)
