import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")


def run_whisper_multi(params_file):
    with open(params_file, "r", encoding="utf-8") as f:
        p = json.load(f)

    model_size = p["model_size"]
    device = p["device"]
    audio_path = p["audio_path"]
    output_path = p["output_path"]
    engine_type = p.get("engine_type", "whisperX")
    use_multi_lang = p.get("use_multi_lang", True)
    hf_token = p.get("hf_token", "") or os.environ.get("HF_TOKEN", "")
    source_lang = p.get("source_lang", None)

    # Set HF_TOKEN for gated model downloads (SpeechBrain, etc.)
    if hf_token:
        os.environ["HF_TOKEN"] = hf_token
        print(f"[MultiLang] HF token configured (len={len(hf_token)})")

    # 1. Run basic VAD to get chunks. We can use faster_whisper's VAD.
    from faster_whisper import WhisperModel

    # Actually, we can just run faster_whisper or whisperx to get segments first
    print(f"[MultiLang] Loading {engine_type} model {model_size} on {device}...")
    if engine_type == "whisperX":
        import whisperx
        try:
            import transformers.utils.import_utils
            transformers.utils.import_utils.check_torch_load_is_safe = lambda: None
        except:
            pass
        m = whisperx.load_model(model_size, device, compute_type="int8", vad_method="silero")
        audio = whisperx.load_audio(audio_path)
        print(f"[MultiLang] Running base transcription (forced lang: {source_lang})...")
        # For whisperX (pyannote), we can't easily set min_silence_duration in transcribe. We will just pass nothing and rely on faster_whisper for precise VAD later if needed.
        res = m.transcribe(audio, batch_size=4, language=source_lang)
        base_segments = res["segments"]
        base_lang = res.get("language", source_lang or "en")
        print(f"[MultiLang] Base language detected: {base_lang}")

    else:
        m = WhisperModel(model_size, device=device, compute_type="int8")
        print(f"[MultiLang] Running base transcription (forced lang: {source_lang})...")
        # Force VAD to split on 300ms pauses (default is 2000ms)
        vad_params = {"min_silence_duration_ms": 300, "speech_pad_ms": 100}
        segs, info = m.transcribe(audio_path, beam_size=5, vad_filter=True, vad_parameters=vad_params, language=source_lang)
        base_lang = info.language
        base_segments = [{"start": s.start, "end": s.end, "text": s.text} for s in segs]
        print(f"[MultiLang] Base language detected: {base_lang}")

    # 2. If multi-lang is enabled, use SpeechBrain for initial language detection only
    # (not per-segment re-transcription — too slow for 60+ segments).
    # The engine.py applies text-based language detection post-Whisper for accuracy.
    out_segments = []
    if use_multi_lang and len(base_segments) > 0:
        try:
            import huggingface_hub
            import torchaudio
            from speechbrain.pretrained import EncoderClassifier

            # Monkey-patch hf_hub_download to ignore use_auth_token
            _original_hf_hub_download = huggingface_hub.hf_hub_download

            def _patched_hf_hub_download(*args, **kwargs):
                kwargs.pop("use_auth_token", None)
                try:
                    return _original_hf_hub_download(*args, **kwargs)
                except Exception as e:
                    if "custom.py" in str(e) or "404" in str(e):
                        import urllib.error
                        raise urllib.error.HTTPError(url="", code=404, msg="404 Client Error", hdrs=None, fp=None)
                    raise e
            huggingface_hub.hf_hub_download = _patched_hf_hub_download

            classifier = EncoderClassifier.from_hparams(
                source="speechbrain/lang-id-voxlingua107-ecapa",
                savedir=os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AutoDub Studio", "models", "speechbrain_models"),
                run_opts={"device": "cuda"} if device == "cuda" else None
            )

            signal, fs = torchaudio.load(audio_path)

            for i, seg in enumerate(base_segments):
                start_s = seg["start"]
                end_s = seg["end"]

                # Only detect language for longer segments (>1.5s) where audio-based detection is reliable
                if (end_s - start_s) > 1.5:
                    start_frame = int(start_s * fs)
                    end_frame = int(end_s * fs)
                    chunk = signal[:, start_frame:end_frame]

                    try:
                        prediction = classifier.classify_batch(chunk)
                        lang_label = prediction[3][0]
                        lang_code = lang_label.split(":")[0].strip() if ":" in lang_label else lang_label
                        lang_code = lang_code[:2].lower()
                        VALID_LANGS = {"en", "es", "ru", "tr", "ar", "fr", "de", "zh", "ja", "ko", "it", "pt", "pl", "hi", "nl", "sv", "fi", "no", "da", "el", "he", "th", "vi", "id", "ms", "uk", "ro", "hu", "cs", "sk", "bg", "hr", "sr", "sl", "lt", "lv", "et"}
                        if lang_code in VALID_LANGS and lang_code != base_lang:
                            seg["language"] = lang_code
                            # We MUST re-transcribe to get the correct words in the detected language!
                            print(f"[MultiLang] Re-transcribing segment {i} ({start_s:.2f}-{end_s:.2f}) as {lang_code}...")
                            try:
                                if engine_type == "whisperX":
                                    import numpy as np
                                    chunk_audio = audio[int(start_s * 16000):int(end_s * 16000)]
                                    # whisperx.transcribe needs a dict or array.
                                    res_chunk = m.transcribe(chunk_audio, language=lang_code)
                                    if res_chunk["segments"]:
                                        seg["text"] = " ".join([s["text"] for s in res_chunk["segments"]])
                                else:
                                    import numpy as np
                                    # For faster_whisper, we need to extract the audio chunk.
                                    # Since faster_whisper takes a path or numpy array:
                                    # torchaudio loads as [channels, frames]. We need 1D numpy array for faster_whisper.
                                    chunk_np = chunk.squeeze(0).numpy()
                                    segs_chunk, _ = m.transcribe(chunk_np, beam_size=5, language=lang_code)
                                    texts = [s.text for s in segs_chunk]
                                    if texts:
                                        seg["text"] = " ".join(texts)
                            except Exception as e:
                                print(f"[MultiLang] Error re-transcribing segment {i}: {e}")
                    except Exception:
                        pass  # Keep base language for this segment

                if not seg.get("language"):
                    seg["language"] = base_lang
                out_segments.append(seg)

        except Exception as e:
            print(f"[MultiLang] SpeechBrain not available: {e}. Using base language for all segments.")
            for seg in base_segments:
                if not seg.get("language"):
                    seg["language"] = base_lang
            out_segments = base_segments
    else:
        for seg in base_segments:
            if not seg.get("language"):
                seg["language"] = base_lang
        out_segments = base_segments

    # Align if whisperX
    if engine_type == "whisperX" and len(out_segments) > 0:
        try:
            import whisperx
            model_a, metadata = whisperx.load_align_model(language_code=base_lang, device=device)
            res_align = whisperx.align(out_segments, model_a, metadata, audio, device, return_char_alignments=False)
            out_segments = res_align["segments"]
        except Exception as e:
            print(f"[MultiLang] Alignment error: {e}")

    # Format output
    final_out = {
        "segments": [
            {
                "start": s["start"],
                "end": s["end"],
                "text": s["text"],
                "speaker": "SPEAKER_00",
                "language": s.get("language", base_lang)
            }
            for s in out_segments
        ],
        "language": base_lang
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_out, f, ensure_ascii=False)

    print(f"DONE:{len(out_segments)}")


if __name__ == "__main__":
    run_whisper_multi(sys.argv[1])
