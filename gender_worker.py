import json
import sys
import warnings

import torch


def detect_gender(tasks_file, output_file):
    # Suppress warnings
    warnings.filterwarnings("ignore")

    with open(tasks_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading Gender Detection Model on {device}...")

    try:
        import librosa  # noqa: PLC0415
        from transformers import pipeline  # noqa: PLC0415
    except ImportError:
        print(
            "Required libraries missing. Run: pip install transformers librosa soundfile"
        )
        sys.exit(1)

    classifier = pipeline(
        "audio-classification",
        model="alefiury/wav2vec2-large-xlsr-53-gender-recognition-osman",
        device=0 if device == "cuda" else -1,
    )

    results = {}
    for task in tasks:
        speaker = task["speaker_id"]
        audio_path = task["audio_path"]

        try:
            # Load audio at 16kHz
            speech, _ = librosa.load(audio_path, sr=16000)

            # Predict
            preds = classifier(speech)
            # Preds: [{'score': 0.99, 'label': 'male'}, {'score': 0.01, 'label': 'female'}]
            best_label = preds[0]["label"].lower()
            results[speaker] = best_label
            print(f"Detected {speaker}: {best_label}")
        except Exception as e:
            print(f"Error processing {speaker}: {e}")
            results[speaker] = "unknown"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python gender_worker.py <tasks.json> <output.json>")
        sys.exit(1)
    detect_gender(sys.argv[1], sys.argv[2])
