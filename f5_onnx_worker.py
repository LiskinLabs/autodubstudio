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

# Fallback: HuggingFace cache (for installed app where models/ is not bundled)
_HF_CACHE = os.path.expanduser("~/.cache/huggingface/hub/models--patientxtr--F5_TTS_ONNX_Turkish/snapshots")
def _find_hf_snapshot():
    """Find the latest snapshot directory in HF cache. Returns path or None."""
    if not os.path.isdir(_HF_CACHE):
        return None
    for entry in sorted(os.listdir(_HF_CACHE), reverse=True):
        snap = os.path.join(_HF_CACHE, entry)
        if os.path.isdir(snap) and len(entry) == 40:  # SHA hash
            return snap
    return None

def _resolve_model_path(local_path, filename):
    """Return the actual model path, checking local first, then HF cache."""
    if os.path.exists(local_path):
        return local_path
    snap = _find_hf_snapshot()
    if snap:
        hf_path = os.path.join(snap, filename)
        if os.path.exists(hf_path):
            return hf_path
    return local_path  # Return original (will fail with clear error)

VOCAB_PATH = _resolve_model_path(VOCAB_PATH, "vocab.txt")
PREPROCESS_ONNX = _resolve_model_path(PREPROCESS_ONNX, "F5_Preprocess-4096-tr.onnx")
TRANSFORMER_ONNX = _resolve_model_path(TRANSFORMER_ONNX, "F5_Transformer-4096-tr.onnx")
DECODE_ONNX = _resolve_model_path(DECODE_ONNX, "F5_Decode-4096-tr.onnx")


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

            # Estimate max_duration: ~15 chars per second of speech, min 3s
            max_dur = max(3, int(len(gen_text) / 15.0) + 2)

            # Step 1: Preprocess — extracts features from ref audio + text
            pre_inputs = {
                "audio": ref_wav[np.newaxis, np.newaxis, :],  # [1, 1, audio_len]
                "text_ids": text_ids,                           # [1, text_len]
                "max_duration": np.array(max_dur, dtype=np.int32),  # scalar
            }
            pre_outputs = pre_sess.run(None, pre_inputs)
            # Outputs: noise, rope_cos, rope_sin, cat_mel_text,
            #          cat_mel_text_drop, qk_rotated_empty, ref_signal_len

            # Step 2: Transformer — iterative denoising (diffusion)
            denoised = pre_outputs[0]  # noise (initial)
            nfe_step = 32  # number of function evaluation steps
            for step in range(nfe_step):
                tr_inputs = {
                    "noise": denoised,
                    "rope_cos": pre_outputs[1],
                    "rope_sin": pre_outputs[2],
                    "cat_mel_text": pre_outputs[3],
                    "cat_mel_text_drop": pre_outputs[4],
                    "qk_rotated_empty": pre_outputs[5],
                    "time_step": np.array(step, dtype=np.int32),
                }
                tr_outputs = tr_sess.run(None, tr_inputs)
                denoised = tr_outputs[0]  # updated denoised

            # Step 3: Decode — mel to waveform
            dec_inputs = {
                "denoised": denoised,
                "ref_signal_len": pre_outputs[6],
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
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())
        sys.exit(3)
