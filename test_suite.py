import subprocess
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run_test(name, cmd):
    print(f"=== Starting {name} ===")
    print(f"Command: {cmd}")
    try:
        # We need to set PYTHONIOENCODING=utf-8 to avoid Windows console errors
        import os
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', env=env
        )
        for line in process.stdout:
            print(line, end='', flush=True)
            
        process.wait()
        print(f"=== {name} finished with code {process.returncode} ===\n")
        return process.returncode == 0
    except Exception as e:
        print(f"Test failed to run: {e}")
        return False

def main():
    video_url = "https://www.youtube.com/watch?v=wTK6TS3pXgc"
    
    # Test 1: RU, Ollama (Gemma), XTTSv2
    # --lip_sync will be tested as well
    # --tag will mark the file
    cmd1 = f'uv run cli.py "{video_url}" --langs ru --translator_engine ollama --translator_model gemma4:e4b --dub_engine xttsv2 --lip_sync --tag TEST_RU_XTTS'
    if not run_test("Test 1 (RU, Ollama, XTTS, LipSync)", cmd1):
        print("Test 1 FAILED. Stopping.")
        sys.exit(1)
        
    # Test 2: TR, Google, Edge TTS
    cmd2 = f'uv run cli.py "{video_url}" --langs tr --translator_engine google --dub_engine edge --tag TEST_TR_EDGE'
    if not run_test("Test 2 (TR, Google, Edge)", cmd2):
        print("Test 2 FAILED. Stopping.")
        sys.exit(1)
        
    print("ALL TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
