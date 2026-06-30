"""Continuous VRAM + RAM monitor with automatic cleanup for low-resource scenarios.

Runs a daemon background thread that polls GPU/CPU memory every few seconds.
When thresholds are crossed it auto-kills VRAM-hungry processes, empties CUDA
cache, and runs Python GC — before the pipeline ever hits an OOM crash.
"""

import gc
import subprocess
import threading
import time

import torch

# ── VRAM-hungry processes to offer to close ──
VRAM_HOGS = [
    ("chrome.exe", "Chrome"),
    ("msedge.exe", "Edge"),
    ("firefox.exe", "Firefox"),
    ("brave.exe", "Brave"),
    ("opera.exe", "Opera"),
    ("Spotify.exe", "Spotify"),
    ("Discord.exe", "Discord"),
    ("Teams.exe", "MS Teams"),
    ("WhatsApp.exe", "WhatsApp"),
    ("slack.exe", "Slack"),
]


def get_free_vram_mb():
    """Get free VRAM in MB. Returns 0 if CUDA unavailable."""
    try:
        if torch.cuda.is_available():
            free, _total = torch.cuda.mem_get_info(0)
            return free // (1024 * 1024)
    except (RuntimeError, ImportError):
        pass
    return 0


def get_free_ram_mb():
    """Get free system RAM in MB (Windows)."""
    try:
        import ctypes
        import ctypes.wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.wintypes.DWORD),
                ("dwMemoryLoad", ctypes.wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        mem = MEMORYSTATUSEX()
        mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
        return mem.ullAvailPhys // (1024 * 1024)
    except Exception:
        # Cross-platform fallback
        try:
            import psutil
            return psutil.virtual_memory().available // (1024 * 1024)
        except ImportError:
            return 4096  # assume plenty if we can't detect


def free_up_vram(log_callback=None):
    """Kill known VRAM-hungry background processes. Returns count of killed processes."""
    killed = 0
    for proc, name in VRAM_HOGS:
        try:
            r = subprocess.run(
                ["taskkill", "/f", "/im", proc],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if r.returncode == 0:
                if log_callback:
                    log_callback(f"🧹 Closed: {name}")
                killed += 1
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            pass

    if killed == 0:
        if log_callback:
            log_callback("ℹ️ No background processes found to close.")
    else:
        if log_callback:
            log_callback(f"✅ Closed {killed} processes. VRAM freed.")
    return killed


# ═══════════════════════════════════════════════════════════════════════════════
#  Continuous Resource Monitor
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_INTERVAL_SEC = 3  # polling interval

# Thresholds in MB — auto-cleanup fires when free memory drops below these
DEFAULT_VRAM_CRITICAL_MB = 2000  # kill hogs + empty cache + gc
DEFAULT_VRAM_WARNING_MB = 3500  # empty cache + gc only
DEFAULT_RAM_CRITICAL_MB = 2000  # gc collect
DEFAULT_RAM_WARNING_MB = 4000  # gc collect


class ResourceMonitor(threading.Thread):
    """Background daemon that watches VRAM + RAM and auto-cleans."""

    def __init__(
        self,
        interval_sec: float = DEFAULT_INTERVAL_SEC,
        vram_critical_mb: int = DEFAULT_VRAM_CRITICAL_MB,
        vram_warning_mb: int = DEFAULT_VRAM_WARNING_MB,
        ram_critical_mb: int = DEFAULT_RAM_CRITICAL_MB,
        ram_warning_mb: int = DEFAULT_RAM_WARNING_MB,
        on_cleanup=None,
        on_warning=None,
    ):
        super().__init__(daemon=True)
        self.interval = interval_sec
        self.vram_critical_mb = vram_critical_mb
        self.vram_warning_mb = vram_warning_mb
        self.ram_critical_mb = ram_critical_mb
        self.ram_warning_mb = ram_warning_mb
        self.on_cleanup = on_cleanup  # callable(level, vram_free, ram_free, actions)
        self.on_warning = on_warning  # callable(level, vram_free, ram_free)

        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Live snapshot
        self.vram_free_mb = 0
        self.ram_free_mb = 0
        self.vram_total_mb = 0
        self.ram_total_mb = 0
        self.last_cleanup_time = 0.0
        self.cleanup_count = 0
        self.last_level = "normal"  # normal | warning | critical

    # ── public API ──

    def stop(self):
        self._stop_event.set()

    @property
    def vram_free_gb(self) -> float:
        return self.vram_free_mb / 1024.0

    @property
    def ram_free_gb(self) -> float:
        return self.ram_free_mb / 1024.0

    def snapshot(self) -> dict:
        """Return the latest resource snapshot (non-blocking)."""
        with self._lock:
            return {
                "vram_free_mb": self.vram_free_mb,
                "vram_free_gb": round(self.vram_free_mb / 1024.0, 2),
                "ram_free_mb": self.ram_free_mb,
                "ram_free_gb": round(self.ram_free_mb / 1024.0, 2),
                "cleanup_count": self.cleanup_count,
                "level": self.last_level,
                "monitor_running": self.is_alive(),
            }

    def force_cleanup(self) -> dict:
        """Manual trigger — returns what was done."""
        return self._do_cleanup("critical", reason="manual")

    def wait_for_vram(self, need_mb: int, timeout_sec: float = 10.0) -> bool:
        """Block until at least `need_mb` VRAM is free, or timeout."""
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if self.vram_free_mb >= need_mb:
                return True
            time.sleep(0.5)
        return self.vram_free_mb >= need_mb

    # ── thread loop ──

    def run(self):
        while not self._stop_event.is_set():
            self._tick()
            self._stop_event.wait(self.interval)

    # ── internals ──

    def _tick(self):
        vram = get_free_vram_mb()
        ram = get_free_ram_mb()

        with self._lock:
            self.vram_free_mb = vram
            self.ram_free_mb = ram
            if torch.cuda.is_available():
                _free, total = torch.cuda.mem_get_info(0)
                self.vram_total_mb = total // (1024 * 1024)

        # Determine level
        if vram < self.vram_critical_mb or ram < self.ram_critical_mb:
            self._do_cleanup("critical", vram, ram)
        elif vram < self.vram_warning_mb or ram < self.ram_warning_mb:
            self._do_cleanup("warning", vram, ram)
        else:
            self.last_level = "normal"

    def _do_cleanup(self, level: str, vram: int = 0, ram: int = 0, reason: str = "") -> dict:
        """Execute cleanup actions appropriate for the level."""
        now = time.time()
        # Don't spam cleanup more than once every 30 s
        if now - self.last_cleanup_time < 30 and reason != "manual":
            return {"level": level, "actions": [], "skipped": "cooldown"}

        self.last_cleanup_time = now
        self.cleanup_count += 1
        self.last_level = level
        actions = []

        if level == "critical":
            # Aggressive: kill background hogs
            killed = free_up_vram(self._emit if self.on_cleanup else None)
            if killed:
                actions.append(f"killed_{killed}_hogs")
            # Empty CUDA cache
            try:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    actions.append("cuda_empty_cache")
            except Exception:
                pass

        # Always run gc on warning/critical
        gc.collect()
        actions.append("gc_collect")

        result = {
            "level": level,
            "vram_free_mb": self.vram_free_mb,
            "ram_free_mb": self.ram_free_mb,
            "actions": actions,
            "reason": reason,
        }

        if self.on_cleanup:
            self.on_cleanup(level, self.vram_free_mb, self.ram_free_mb, actions)

        # Re-read after cleanup
        self.vram_free_mb = get_free_vram_mb()
        self.ram_free_mb = get_free_ram_mb()

        return result

    def _emit(self, msg: str):
        if self.on_cleanup:
            self.on_cleanup(self.last_level, self.vram_free_mb, self.ram_free_mb, [msg])


# ═══════════════════════════════════════════════════════════════════════════════
#  Singleton access (one monitor per process)
# ═══════════════════════════════════════════════════════════════════════════════

_monitor: ResourceMonitor | None = None
_monitor_lock = threading.Lock()


def get_monitor(**kw) -> ResourceMonitor:
    """Return the process-wide ResourceMonitor, creating it if needed.

    Pass threshold overrides on first call only.
    """
    global _monitor
    with _monitor_lock:
        if _monitor is None or not _monitor.is_alive():
            _monitor = ResourceMonitor(**kw)
            _monitor.start()
        return _monitor


def stop_monitor():
    global _monitor
    with _monitor_lock:
        if _monitor is not None:
            _monitor.stop()
            _monitor = None
