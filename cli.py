import argparse
import sys
import os
import shutil
import json

# Fix for Windows PyTorch Audio / FFmpeg TorchCodec DLL issue
if os.name == 'nt':
    shared_ffmpeg_path = r"C:\Projects\AutoDubStudio\downloads\ffmpeg7\ffmpeg-7.1-full_build-shared\bin"
    if os.path.exists(shared_ffmpeg_path):
        os.environ["PATH"] = shared_ffmpeg_path + os.pathsep + os.environ.get("PATH", "")
        os.add_dll_directory(shared_ffmpeg_path)
    else:
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ.get("PATH", "")
            os.add_dll_directory(os.path.dirname(ffmpeg_path))

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
    parser.add_argument("--translator_model", type=str, default="gemma4:e4b", help="Model for Ollama translator: gemma4:12b (High-end), gemma4:e4b (Medium), gemma4:e2b (Weak)")
    
    # API Keys
    parser.add_argument("--gemini_key", type=str, default="", help="Google Gemini API Key")
    parser.add_argument("--deepseek_key", type=str, default="", help="DeepSeek API Key")
    parser.add_argument("--deepl_key", type=str, default="", help="DeepL API Key")
    parser.add_argument("--hf_key", type=str, default="", help="Hugging Face API Key")
    
    # Advanced Options
    parser.add_argument("--lip_sync", action="store_true", help="Enable Lip-Sync processing")
    parser.add_argument("--manual_mode", action="store_true", help="Pause pipeline for manual subtitle editing")
    parser.add_argument("--tag", type=str, default="", help="Custom tag for output filenames")
    parser.add_argument("--max_duration", type=int, default=0, help="Maximum video duration in seconds (trims the beginning of the video)")
    
    args = parser.parse_args()

    config = {
        "video_path": args.video_path,
        "out_dir": args.out_dir,
        "langs": [l.strip() for l in args.langs.split(",") if l.strip()],
        "model_size": args.model_size,
        "device": args.device,
        "translation_engine": args.translator_engine,
        "dub_engine": args.dub_engine,
        "translator_model": args.translator_model,
        "gemini_key": args.gemini_key,
        "deepseek_key": args.deepseek_key,
        "deepl_key": args.deepl_key,
        "hf_key": args.hf_key,
        "lip_sync": args.lip_sync,
        "manual_mode": args.manual_mode,
        "tag": args.tag,
        "max_duration": args.max_duration
    }

    print(f"==================================================")
    print(f"AutoDub Studio CLI v1.1 - Industrial Edition")
    print(f"==================================================")
    for k, v in config.items():
        if 'key' in k and v:
            print(f"{k.ljust(20)}: {'*' * 8}")
        else:
            print(f"{k.ljust(20)}: {v}")
    print(f"==================================================")

    worker = AutoDubWorker(config)
    
    def on_log(msg):
        print(f"[LOG] {msg}")

    def on_progress(p):
        pass # To avoid console spam

    def on_finished(success, msg):
        print(f"\n[FINISHED] Success: {success}")
        print(f"[RESULT] {msg}")
        
    def on_manual_edit(manual_subs):
        print("\n" + "="*50)
        print("MANUAL MODE PAUSED")
        print("="*50)
        edit_file = os.path.join(os.getcwd(), "manual_edit.json")
        with open(edit_file, "w", encoding="utf-8") as f:
            json.dump(manual_subs, f, ensure_ascii=False, indent=4)
        
        print(f"Subtitles dumped to: {edit_file}")
        print("1. Open this file in your favorite text editor.")
        print("2. Modify the 'trans' (translation) fields or 'speaker' assignments as needed.")
        print("3. Save the file.")
        
        input("\nPress ENTER when you have finished editing to resume the pipeline...")
        
        try:
            with open(edit_file, "r", encoding="utf-8") as f:
                edited_subs = json.load(f)
            
            # Map back to the format engine expects (it expects 'text' instead of 'trans' sometimes,
            # but in engine.py:1605 it assigns self.edited_segments directly to translated_segments,
            # so we ensure 'text' is properly set)
            for s in edited_subs:
                s['text'] = s.get('trans', s.get('text', ''))
                
            worker.edited_segments = edited_subs
            print("Changes loaded successfully. Resuming pipeline...")
        except Exception as e:
            print(f"Error loading edits ({e}). Resuming with original translations...")
            
        worker.pause_event.set()

    worker.log_signal.connect(on_log)
    worker.progress_signal.connect(on_progress)
    worker.finished_signal.connect(on_finished)
    worker.manual_edit_signal.connect(on_manual_edit)

    worker.start()
    
    try:
        while worker.is_alive():
            worker.join(timeout=1.0)
    except KeyboardInterrupt:
        print("\n[!] KeyboardInterrupt received. Stopping worker...")
        worker.stop()
        worker.join()
        sys.exit(0)

if __name__ == "__main__":
    main()
