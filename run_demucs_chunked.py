import math
import os
import subprocess
import sys

video_path = r"C:\Users\silvestr.liskin\Downloads\recordings\ACP training-20251008_100238-Meeting Recording.mp4"
base_name = os.path.splitext(os.path.basename(video_path))[0]
demucs_out_dir = r"C:\Users\silvestr.liskin\Downloads\recordings\demucs_out"
model_out = os.path.join(demucs_out_dir, "mdx_extra_q", base_name)
os.makedirs(model_out, exist_ok=True)

# 1. Extract audio
audio_path = "temp_audio.wav"
subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", audio_path], check=True)

# 2. Get duration
duration_str = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]).decode().strip()
duration = float(duration_str)

CHUNK_LEN = 3 * 60  # 3 minutes per chunk! Better for RAM.
num_chunks = math.ceil(duration / CHUNK_LEN)

vocals_list = "vocals_list.txt"
no_vocals_list = "no_vocals_list.txt"
with open(vocals_list, "w", encoding="utf-8") as f_v, open(no_vocals_list, "w", encoding="utf-8") as f_nv:
    for i in range(num_chunks):
        start = i * CHUNK_LEN
        chunk_path = f"chunk_{i}.wav"
        print(f"Extracting chunk {i + 1}/{num_chunks}")
        subprocess.run(["ffmpeg", "-y", "-i", audio_path, "-ss", str(start), "-t", str(CHUNK_LEN), "-acodec", "copy", chunk_path], check=True)

        print(f"Running Demucs on chunk {i + 1}")
        cmd = [
            sys.executable, "-m", "demucs.separate",
            "-n", "mdx_extra_q",
            "-d", "cuda",
            "--two-stems=vocals",
            "--segment", "10",
            "-o", "chunk_demucs_out",
            chunk_path
        ]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            print("CUDA failed, trying CPU...")
            cmd[cmd.index("cuda")] = "cpu"
            subprocess.run(cmd, check=True)

        chunk_v = f"chunk_demucs_out/mdx_extra_q/chunk_{i}/vocals.wav"
        chunk_nv = f"chunk_demucs_out/mdx_extra_q/chunk_{i}/no_vocals.wav"

        chunk_v_abs = os.path.abspath(chunk_v).replace('\\', '/')
        chunk_nv_abs = os.path.abspath(chunk_nv).replace('\\', '/')

        f_v.write(f"file '{chunk_v_abs}'\n")
        f_nv.write(f"file '{chunk_nv_abs}'\n")

print("Concatenating...")
subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", vocals_list, "-c", "copy", os.path.join(model_out, "vocals.wav")], check=True)
subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", no_vocals_list, "-c", "copy", os.path.join(model_out, "no_vocals.wav")], check=True)

print("Done!")
