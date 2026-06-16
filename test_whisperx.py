import os
import torch
import whisperx

print("CUDA available:", torch.cuda.is_available())
video_path = r"C:\Users\silvestr.liskin\Desktop\AutoDubStudio\downloads\New Samsung Dex - One UI 8.5 !.mp4"

print("Loading audio...")
audio = whisperx.load_audio(video_path)

print("Loading whisperx model...")
model = whisperx.load_model("small", "cuda", compute_type="int8")

print("Transcribing...")
try:
    result = model.transcribe(audio, batch_size=2)
    print("Transcription done! Language:", result.get('language'))
except Exception as e:
    print("Error during transcribe:", e)

print("Loading align model...")
try:
    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device="cuda")
    print("Aligning...")
    result = whisperx.align(result["segments"], model_a, metadata, audio, "cuda", return_char_alignments=False)
    print("Alignment done!")
except Exception as e:
    print("Error during alignment:", e)

print("SUCCESS")
