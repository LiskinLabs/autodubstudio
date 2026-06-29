#!/usr/bin/env python3
"""
Lip-Sync Worker for AutoDubStudio
Replaces the original audio track in a video with the dubbed audio.
For true lip-sync (Wav2Lip), 8-12 GB VRAM is needed — rejected per ARCHITECTURE_V2.
This worker does an ffmpeg audio swap: video from original + audio from dub.
"""

import os
import shutil
import subprocess
import sys
import traceback


def main():
    if len(sys.argv) < 4:
        print(
            "Usage: python lip_sync_worker.py <input_video> <input_audio> <output_video>"
        )
        sys.exit(1)

    # Normalize to absolute paths (defense against flag smuggling)
    input_video = os.path.abspath(sys.argv[1])
    input_audio = os.path.abspath(sys.argv[2])
    output_video = os.path.abspath(sys.argv[3])

    # Validate inputs
    for fpath, label in [(input_video, "Input video"), (input_audio, "Input audio")]:
        if not os.path.exists(fpath):
            print(f"❌ {label} not found: {fpath}")
            sys.exit(1)

    print("🎬 Lip-Sync (audio swap mode)")
    print(f"   Video: {os.path.basename(input_video)}")
    print(f"   Audio: {os.path.basename(input_audio)}")

    try:
        # Use ffmpeg to copy video stream + replace audio with dubbed audio
        # -- terminates option parsing; absolute paths prevent flag smuggling
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            input_video,
            "-i",
            input_audio,
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
            "--",
            output_video,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            print(f"❌ ffmpeg failed:\n{result.stderr[-500:]}")
            # Fallback: just copy the video as-is
            shutil.copy(input_video, output_video)
            print("⚠ Fallback: copied original video (audio swap failed)")
        else:
            print(f"✅ Lip-sync complete: {os.path.basename(output_video)}")

    except subprocess.TimeoutExpired:
        print("⚠ ffmpeg timed out. Copying original video...")
        shutil.copy(input_video, output_video)
    except Exception as e:
        print(f"❌ Lip-sync error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
