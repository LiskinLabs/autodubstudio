import argparse
import sys
import threading
from engine import AutoDubWorker

def main():
    parser = argparse.ArgumentParser(description="AutoDub Studio CLI - Command Line Interface")
    parser.add_argument("video_path", type=str, help="Path to input video or YouTube URL")
    parser.add_argument("--out_dir", type=str, default="", help="Output directory")
    parser.add_argument("--langs", type=str, default="ru", help="Target languages separated by comma (e.g. ru,tr,en)")
    parser.add_argument("--model_size", type=str, default="large-v3", help="Whisper model size")
    parser.add_argument("--device", type=str, default="cuda", help="Device to use (cuda/cpu)")
    parser.add_argument("--translator_engine", type=str, default="google", help="Translator engine (google, deepl, ollama, deepseek)")
    parser.add_argument("--dub_engine", type=str, default="xttsv2", help="TTS Dub Engine (xttsv2, gtts, edge)")
    parser.add_argument("--translator_model", type=str, default="gemma4:e4b", help="Model for Ollama translator")
    
    args = parser.parse_args()

    config = {
        "video_path": args.video_path,
        "out_dir": args.out_dir,
        "langs": args.langs.split(',') if ',' in args.langs else [args.langs],
        "model_size": args.model_size,
        "device": args.device,
        "translator_engine": args.translator_engine,
        "dub_engine": args.dub_engine,
        "translator_model": args.translator_model,
        "manual_mode": False
    }

    # AutoDubWorker expect strings for langs in the dict currently (it parses inside engine), 
    # wait, let's just pass what user provided directly.
    config["langs"] = args.langs 

    print(f"==================================================")
    print(f"🎬 AutoDub Studio CLI v1.0")
    print(f"==================================================")
    print(f"Target Video: {config['video_path']}")
    print(f"Languages:    {config['langs']}")
    print(f"Device:       {config['device']}")
    print(f"--------------------------------------------------")

    worker = AutoDubWorker(config)
    
    def on_log(msg):
        print(f"[LOG] {msg}")

    def on_progress(p):
        pass # print(f"[PROGRESS] {p}%") # Progress is often spammy, kept silent unless debugging

    def on_finished(success, msg):
        print(f"\n[FINISHED] Success: {success}")
        print(f"[RESULT] {msg}")
        
    worker.log_signal.connect(on_log)
    worker.progress_signal.connect(on_progress)
    worker.finished_signal.connect(on_finished)

    worker.start()
    
    try:
        # Wait for the thread to finish
        while worker.is_alive():
            worker.join(timeout=1.0)
    except KeyboardInterrupt:
        print("\n[!] KeyboardInterrupt received. Stopping worker...")
        worker.stop()
        worker.join()
        sys.exit(0)

if __name__ == "__main__":
    main()
