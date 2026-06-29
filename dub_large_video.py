import os
import sys
import time
import subprocess
import glob

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from engine import AutoDubWorker

def get_video_duration(video_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", video_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0

def split_video(video_path, chunk_dir, chunk_duration=600):
    os.makedirs(chunk_dir, exist_ok=True)
    existing_chunks = sorted(glob.glob(os.path.join(chunk_dir, "chunk_*.mp4")))
    if existing_chunks:
        print(f"Found {len(existing_chunks)} existing chunks. Skipping split.")
        return existing_chunks

    print(f"Splitting video into {chunk_duration}s chunks...")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-c", "copy", "-f", "segment",
        "-segment_time", str(chunk_duration),
        "-reset_timestamps", "1",
        os.path.join(chunk_dir, "chunk_%03d.mp4")
    ]
    subprocess.run(cmd, check=True)
    chunks = sorted(glob.glob(os.path.join(chunk_dir, "chunk_*.mp4")))
    print(f"Created {len(chunks)} chunks.")
    return chunks

def merge_videos(video_paths, output_path):
    print("Merging dubbed chunks...")
    list_path = os.path.join(os.path.dirname(output_path), "concat_list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for vp in video_paths:
            # Escape path properly for ffmpeg
            safe_vp = vp.replace("\\", "/")
            f.write(f"file '{safe_vp}'\n")
    
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", list_path, "-map", "0", "-c", "copy", output_path
    ]
    subprocess.run(cmd, check=True)
    print(f"Successfully merged into {output_path}")
    os.remove(list_path)

def dub_chunk(chunk_path, out_dir, index, total):
    print(f"--- Processing chunk {index}/{total}: {os.path.basename(chunk_path)} ---")
    
    # We use Edge-TTS by default for speed, or XTTSv2 Local
    config = {
        "video_path": chunk_path,
        "out_dir": out_dir,
        "target_langs": ["tr"],
        "whisper_model": "large-v3-turbo",
        "device": "cuda",
        "translation_engine": "Google Translate (Free)",
        "dub_engine": "Edge-TTS (Cloud, Free, Fast)",
        "manual_mode": False,
        "lip_sync": False,
        "tag": "TR-DUB",
        "user_glossary": "ACP = Agile Certified Practitioner\nScrum = Scrum",
    }
    
    worker = AutoDubWorker(config)
    
    def on_log(msg):
        # We can silence normal logs or print them
        try:
            print(f"  [Chunk {index}] {msg}", flush=True)
        except Exception:
            pass

    # Flag to track success
    result = {"success": False, "file": None}

    def on_finished(success, message):
        result["success"] = success
        if success:
            # engine.py usually puts the file in out_dir/chunk_001_tr.mp4
            # We need to find the output file
            pass

    worker.log_signal.connect(on_log)
    worker.finished_signal.connect(on_finished)
    
    worker.run()
    
    # After run, the output file might be .mkv or .mp4 depending on engine subtitles
    base_name = os.path.splitext(os.path.basename(chunk_path))[0]
    import glob
    possible_outputs = glob.glob(os.path.join(out_dir, f"{base_name}*TR*mkv")) + \
                       glob.glob(os.path.join(out_dir, f"{base_name}*tr*mp4"))
    
    if possible_outputs:
        return possible_outputs[0]
    else:
        # Check if the engine appended the language suffix
        alt_out = os.path.join(out_dir, f"{base_name}.mp4")
        if os.path.exists(alt_out):
            return alt_out
        
        print(f"Error: Output file not found for {chunk_path}")
        return None

def main():
    video_path = r"C:\Users\silvestr.liskin\Desktop\видео\ACP training-20251008_130639-Meeting Recording 1.mp4"
    base_dir = r"C:\Users\silvestr.liskin\Desktop\видео\autodub_out"
    chunks_dir = os.path.join(base_dir, "chunks")
    dubbed_chunks_dir = os.path.join(base_dir, "dubbed_chunks")
    
    os.makedirs(base_dir, exist_ok=True)
    os.makedirs(dubbed_chunks_dir, exist_ok=True)
    
    if not os.path.exists(video_path):
        print(f"[FATAL] Video not found: {video_path}")
        sys.exit(1)
        
    duration = get_video_duration(video_path)
    print(f"Video duration: {duration}s")
    
    # 10 minutes = 600s
    chunks = split_video(video_path, chunks_dir, chunk_duration=600)
    
    dubbed_files = []
    
    start_time = time.time()
    
    for i, chunk in enumerate(chunks, 1):
        base_name = os.path.splitext(os.path.basename(chunk))[0]
        import glob
        existing = glob.glob(os.path.join(dubbed_chunks_dir, f"{base_name}*TR*mkv")) + \
                   glob.glob(os.path.join(dubbed_chunks_dir, f"{base_name}*tr*mp4"))
        
        if existing:
            print(f"Skipping chunk {i}, already dubbed: {existing[0]}")
            dubbed_files.append(existing[0])
            continue

        # Dub each chunk
        dubbed_file = dub_chunk(chunk, dubbed_chunks_dir, i, len(chunks))
        if not dubbed_file:
            print(f"Failed to dub chunk {i}. Aborting.")
            sys.exit(1)
        dubbed_files.append(dubbed_file)
        
    final_output = os.path.join(base_dir, "FINAL_DUBBED_ACP_training_TR.mkv")
    merge_videos(dubbed_files, final_output)
    
    total_time = time.time() - start_time
    print(f"All done! Total time: {total_time:.1f}s")
    print(f"Final video: {final_output}")

if __name__ == "__main__":
    main()
