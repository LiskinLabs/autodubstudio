import os
import subprocess
import glob

# Paths
video_path = r"C:\Users\silvestr.liskin\Downloads\recordings\ACP training-20251008_100238-Meeting Recording.mp4"
base_name = os.path.splitext(os.path.basename(video_path))[0]
demucs_out = r"C:\Users\silvestr.liskin\Downloads\recordings\demucs_out\mdx_extra_q"
target_dir = os.path.join(demucs_out, base_name)
temp_dir = os.path.join(demucs_out, "temp_chunks")

os.makedirs(target_dir, exist_ok=True)
os.makedirs(temp_dir, exist_ok=True)

print("1. Extracting full audio...")
full_audio = os.path.join(temp_dir, "full_audio.wav")
if not os.path.exists(full_audio):
    subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vn", "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2", full_audio], check=True)

print("2. Slicing into 15-minute chunks...")
# Use ffmpeg segment muxer
chunk_pattern = os.path.join(temp_dir, "chunk_%03d.wav")
subprocess.run(["ffmpeg", "-y", "-i", full_audio, "-f", "segment", "-segment_time", "900", "-c", "copy", chunk_pattern], check=True)

chunks = sorted(glob.glob(os.path.join(temp_dir, "chunk_*.wav")))
print(f"Created {len(chunks)} chunks.")

print("3. Processing chunks with Demucs...")
for chunk in chunks:
    chunk_name = os.path.splitext(os.path.basename(chunk))[0]
    out_dir = os.path.join(temp_dir, chunk_name)
    if not os.path.exists(os.path.join(out_dir, "mdx_extra_q", chunk_name, "vocals.wav")):
        print(f"Processing {chunk_name}...")
        subprocess.run([
            "uv", "run", "python", "-m", "demucs.separate",
            "-n", "mdx_extra_q", "-d", "cpu", "--two-stems=vocals",
            "-o", out_dir, chunk
        ], check=True)

print("4. Concatenating vocals and no_vocals...")
vocals_txt = os.path.join(temp_dir, "vocals_list.txt")
no_vocals_txt = os.path.join(temp_dir, "no_vocals_list.txt")

with open(vocals_txt, "w", encoding="utf-8") as f_v, open(no_vocals_txt, "w", encoding="utf-8") as f_n:
    for chunk in chunks:
        chunk_name = os.path.splitext(os.path.basename(chunk))[0]
        v_path = os.path.join(temp_dir, chunk_name, "mdx_extra_q", chunk_name, "vocals.wav")
        n_path = os.path.join(temp_dir, chunk_name, "mdx_extra_q", chunk_name, "no_vocals.wav")
        f_v.write(f"file '{v_path}'\n".replace("\\", "/"))
        f_n.write(f"file '{n_path}'\n".replace("\\", "/"))

final_vocals = os.path.join(target_dir, "vocals.wav")
final_no_vocals = os.path.join(target_dir, "no_vocals.wav")

subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", vocals_txt, "-c", "copy", final_vocals], check=True)
subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", no_vocals_txt, "-c", "copy", final_no_vocals], check=True)

print("DONE! Vocals and no_vocals saved to target_dir. You can now run run_remaining.py.")
