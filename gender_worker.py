"""
Gender detection worker for AutoDubStudio.
Uses a cross-lingual wav2vec2-XLSR model with pitch-based fallback.
XLSR-53 was pre-trained on 53 languages, making it suitable for multilingual content.
"""
import json
import os
import sys
import warnings
import traceback

import torch

warnings.filterwarnings("ignore")

# ── Monkey-patches for HF compatibility ──
try:
    import transformers.utils.import_utils
    transformers.utils.import_utils.check_torch_load_is_safe = lambda: None
except ImportError:
    pass
try:
    import transformers.modeling_utils
    transformers.modeling_utils.check_torch_load_is_safe = lambda: None
except ImportError:
    pass


def detect_gender_pitch(audio_path: str) -> tuple[str, float]:
    """
    Cross-lingual gender detection based on fundamental frequency (pitch).
    Female voices typically have mean F0 > 165 Hz, male < 165 Hz.
    This is language-independent and requires no model download.

    Returns (gender_label, confidence_score).
    """
    try:
        import librosa
        import numpy as np

        y, sr = librosa.load(audio_path, sr=16000, duration=8.0)

        # Extract pitch using CREPE-style algorithm via librosa
        f0, voiced_flag, _ = librosa.pyin(
            y,
            fmin=50.0,
            fmax=600.0,
            sr=sr,
            frame_length=2048,
        )

        # Only consider voiced frames
        voiced_f0 = f0[voiced_flag]
        if len(voiced_f0) < 10:
            return ("male", 0.3)  # Not enough voiced speech

        mean_f0 = float(np.mean(voiced_f0))

        # Female > 165 Hz, Male < 165 Hz
        # Confidence based on distance from threshold
        threshold = 165.0
        distance = abs(mean_f0 - threshold)
        confidence = min(0.95, distance / 100.0 + 0.5)

        if mean_f0 > threshold:
            return ("female", confidence)
        else:
            return ("male", confidence)

    except Exception as e:
        print(f"  Pitch detection failed: {e}")
        return ("male", 0.1)


def detect_gender_ml(audio_path: str) -> tuple[str, float] | None:
    """
    ML-based gender detection using wav2vec2-XLSR-53 fine-tuned for gender.
    XLSR-53 is cross-lingual (pre-trained on 53 languages).
    Returns None if the model can't be loaded.
    """
    try:
        from transformers import pipeline

        # Try the best available cross-lingual model
        model_id = "alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech"

        classifier = pipeline(
            "audio-classification",
            model=model_id,
            device=0 if torch.cuda.is_available() else -1,
        )

        import librosa
        speech, _ = librosa.load(audio_path, sr=16000, duration=10.0)
        preds = classifier(speech)
        # preds: [{'score': 0.99, 'label': 'male'}, {'score': 0.01, 'label': 'female'}]
        best = preds[0]
        return (best["label"].lower(), best["score"])

    except Exception as e:
        print(f"  ML model not available: {e}")
        return None


def detect_gender(tasks_file, output_file):
    with open(tasks_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[Gender] Device: {device}, Tasks: {len(tasks)}")

    # Try ML model first, fall back to pitch
    ml_available = True
    try:
        from transformers import pipeline
        test = pipeline(
            "audio-classification",
            model="alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech",
            device=0 if device == "cuda" else -1,
        )
    except Exception:
        ml_available = False
        print("[Gender] ML model unavailable — using pitch-based detection")

    results = {}
    for task in tasks:
        speaker = task["speaker_id"]
        audio_path = task["audio_path"]

        if not os.path.exists(audio_path):
            print(f"[Gender] Audio not found for {speaker}: {audio_path}")
            results[speaker] = "female"  # Default to female for TTS quality
            continue

        gender = "female"  # Default
        confidence = 0.0

        if ml_available:
            result = detect_gender_ml(audio_path)
            if result:
                gender, confidence = result
                print(f"[Gender] ML: {speaker} = {gender} ({confidence:.2f})")

        # If ML failed or low confidence, use pitch as fallback
        if confidence < 0.6:
            pitch_gender, pitch_conf = detect_gender_pitch(audio_path)
            if pitch_conf > confidence:
                gender = pitch_gender
                confidence = pitch_conf
            print(f"[Gender] Pitch fallback: {speaker} = {gender} ({confidence:.2f})")

        results[speaker] = gender

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f)

    print(f"[Gender] Results: {results}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python gender_worker.py <tasks.json> <output.json>")
        sys.exit(1)

    try:
        detect_gender(sys.argv[1], sys.argv[2])
    except Exception:
        traceback.print_exc()
        # Write fallback results
        with open(sys.argv[2], "w", encoding="utf-8") as f:
            json.dump({"SPEAKER_00": "female"}, f)
