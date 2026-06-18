"""
F5-TTS-ONNX Worker — ONNX Runtime Turkish TTS for AutoDubStudio
Uses: patientxtr/F5_TTS_ONNX_Turkish + DakeQQ/F5-TTS-ONNX inference
Faster inference, lower VRAM than PyTorch version.
"""
import json
import os
import sys
import traceback

import numpy as np
import onnxruntime as ort
import soundfile as sf

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "f5-onnx", "models")
VOCAB_PATH = os.path.join(MODEL_DIR, "vocab.txt")
PREPROCESS_ONNX = os.path.join(MODEL_DIR, "F5_Preprocess-4096-tr.onnx")
TRANSFORMER_ONNX = os.path.join(MODEL_DIR, "F5_Transformer-4096-tr.onnx")
DECODE_ONNX = os.path.join(MODEL_DIR, "F5_Decode-4096-tr.onnx")


def load_vocab(path):
    """Load character-level vocab for Turkish F5-TTS."""
    with open(path, "r", encoding="utf-8") as f:
        chars = [line.rstrip("\n").rstrip("\r") for line in f if line.strip()]
    # vocab.txt format: char per line, 4096 entries
    c2i = {c: i for i, c in enumerate(chars)}
    return c2i, chars


def text_to_ids(text, c2i):
    """Convert text to token IDs using char-level vocab."""
    ids = []
    for ch in text:
        if ch in c2i:
            ids.append(c2i[ch])
        else:
            ids.append(0)  # UNK token
    return np.array([ids], dtype=np.int64)


def main():
    if len(sys.argv) < 2:
        print("Usage: python f5_onnx_worker.py <tasks.json>")
        sys.exit(1)

    tasks_file = sys.argv[1]
    with open(tasks_file, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    print(f"F5-TTS-ONNX Worker: {len(tasks)} segments")

    # Load vocab
    print(f"Loading vocab: {VOCAB_PATH}")
    c2i, chars = load_vocab(VOCAB_PATH)
    print(f"Vocab size: {len(c2i)} chars")

    # Load ONNX models
    sess_opts = ort.SessionOptions()
    sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sess_opts.intra_op_num_threads = 4

    providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if ort.get_device() == 'GPU' else ['CPUExecutionProvider']

    print("Loading Preprocess model...")
    pre_sess = ort.InferenceSession(PREPROCESS_ONNX, sess_opts, providers=providers)

    print("Loading Transformer model...")
    tr_sess = ort.InferenceSession(TRANSFORMER_ONNX, sess_opts, providers=providers)

    print("Loading Decode model...")
    dec_sess = ort.InferenceSession(DECODE_ONNX, sess_opts, providers=providers)

    print(f"All models loaded! Providers: {pre_sess.get_providers()}")

    success = 0
    failed = 0

    for i, task in enumerate(tasks):
        ref_audio = task["ref_audio"]
        gen_text = task["gen_text"]
        out_path = task["out_path"]

        if not gen_text.strip():
            gen_text = "Merhaba."

        if (i + 1) % 10 == 0 or i == 0:
            print(f"[{i+1}/{len(tasks)}] {gen_text[:60]}...")

        try:
            # Load reference audio
            ref_wav, ref_sr = sf.read(ref_audio)
            if ref_sr != 24000:
                import librosa
                ref_wav = librosa.resample(ref_wav, orig_sr=ref_sr, target_sr=24000)
                ref_sr = 24000
            ref_wav = ref_wav.astype(np.float32)
            if len(ref_wav.shape) > 1:
                ref_wav = ref_wav.mean(axis=1)

            # Text to IDs
            text_ids = text_to_ids(gen_text, c2i)

            # Step 1: Preprocess
            pre_inputs = {
                "ref_audio": ref_wav[np.newaxis, :],
                "text_ids": text_ids,
            }
            pre_outputs = pre_sess.run(None, pre_inputs)
            # Output: hidden_states, ref_features, mask

            # Step 2: Transformer
            tr_inputs = {
                "hidden_states": pre_outputs[0],
                "ref_features": pre_outputs[1],
                "mask": pre_outputs[2] if len(pre_outputs) > 2 else np.ones((1, pre_outputs[0].shape[1]), dtype=np.bool_),
            }
            tr_outputs = tr_sess.run(None, tr_inputs)

            # Step 3: Decode
            dec_inputs = {
                "mel": tr_outputs[0],
            }
            dec_outputs = dec_sess.run(None, dec_inputs)
            audio = dec_outputs[0].flatten()

            # Save
            sf.write(out_path, audio.astype(np.float32), 24000)
            success += 1

        except Exception as e:
            print(f"ERROR [{i+1}]: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
            # Write silence as fallback
            silence = np.zeros(24000, dtype=np.float32)
            sf.write(out_path, silence, 24000)

    print(f"\nDone: {success} ok, {failed} failed, {len(tasks)} total [F5-TTS-ONNX Turkish]")
    os._exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())
        os._exit(3)
