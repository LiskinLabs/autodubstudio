import subprocess

import torch

# VRAM-hungry processes to offer to close
VRAM_HOGS = [
    ("chrome.exe", "Chrome"),
    ("msedge.exe", "Edge"),
    ("firefox.exe", "Firefox"),
    ("brave.exe", "Brave"),
    ("opera.exe", "Opera"),
    ("Spotify.exe", "Spotify"),
    ("Discord.exe", "Discord"),
    ("Teams.exe", "MS Teams"),
]

def get_free_vram_mb():
    """Get free VRAM in MB. Returns 0 if CUDA unavailable."""
    try:
        if torch.cuda.is_available():
            free, total = torch.cuda.mem_get_info(0)
            return free // (1024 * 1024)
    except (RuntimeError, ImportError):
        pass
    return 0

def free_up_vram(log_callback=None):
    """Kill known VRAM-hungry background processes. Returns count of killed processes."""
    killed = 0
    for proc, name in VRAM_HOGS:
        try:
            r = subprocess.run(
                ["taskkill", "/f", "/im", proc],
                capture_output=True, text=True, encoding="utf-8"
            )
            if r.returncode == 0:
                if log_callback: log_callback(f"🧹 Закрыт: {name}")
                killed += 1
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            pass

    if killed == 0:
        if log_callback: log_callback("🧹 Нет запущенных фоновых программ для закрытия.")
    else:
        if log_callback: log_callback(f"🧹 Закрыто программ: {killed}. Освобождена VRAM.")
    return killed
