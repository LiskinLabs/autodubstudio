import sys
import subprocess
import os

def main():
    if len(sys.argv) < 2:
        print("Usage: signtool.py <args...>")
        sys.exit(1)
        
    args = sys.argv[1:]
    
    # We want to extract the file path, which is usually the last argument or passed as "%1"
    # The PowerShell script needs the file path.
    # Actually, we can just pass ALL arguments to our PowerShell script if needed,
    # OR we know tauri invokes it as python .github/scripts/signtool.py sign /debug ... "path/to/file"
    # Let's just find the file path (last argument)
    file_path = args[-1]
    
    # Call the powershell script
    ps_script = os.path.join(os.path.dirname(__file__), "sign.ps1")
    cmd = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", ps_script, file_path]
    
    print(f"Executing: {cmd}")
    sys.stdout.flush()
    
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == '__main__':
    main()
