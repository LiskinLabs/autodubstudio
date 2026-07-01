"""Windows native memory optimization — same APIs used by WinMemoryCleaner (2k ⭐).

All techniques are documented Windows API calls. No snake oil.
Verifiable via Windows Resource Monitor (resmon.exe).

References:
- WinMemoryCleaner: https://github.com/IgorMundstein/WinMemoryCleaner
- MSDN: SetProcessWorkingSetSize, EmptyWorkingSet, NtSetSystemInformation
"""

import ctypes
import ctypes.wintypes
import gc
import subprocess
import sys
from dataclasses import dataclass

# ═══════════════════════════════════════════════════════════════════════════════
#  Windows API bindings
# ═══════════════════════════════════════════════════════════════════════════════

_PSAPI = ctypes.windll.psapi
_KERNEL32 = ctypes.windll.kernel32
_NTDLL = ctypes.windll.ntdll

# ── Process enumeration ──

_PROCESS_QUERY_INFORMATION = 0x0400
_PROCESS_VM_READ = 0x0010
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001


def _enum_processes():
    """Yield (pid, handle) for all running processes."""
    count = 256
    while True:
        pids = (ctypes.wintypes.DWORD * count)()
        needed = ctypes.wintypes.DWORD()
        if not _PSAPI.EnumProcesses(ctypes.byref(pids), ctypes.sizeof(pids), ctypes.byref(needed)):
            return
        actual = needed.value // ctypes.sizeof(ctypes.wintypes.DWORD)
        for i in range(min(actual, count)):
            pid = pids[i]
            if pid == 0:
                continue
            h = _KERNEL32.OpenProcess(
                _PROCESS_QUERY_INFORMATION | _PROCESS_SET_QUOTA | _PROCESS_VM_READ,
                False,
                pid,
            )
            if h:
                yield pid, h
        if actual < count:
            break
        count *= 2


# ── Working Set ──


def empty_all_working_sets() -> int:
    """Call EmptyWorkingSet on every user-mode process. Returns count of processes trimmed.

    Equivalent to WinMemoryCleaner's 'Working Set' optimization.
    Forces processes to release non-essential RAM — can free significant memory
    from browsers, Electron apps, etc. without killing them.
    """
    trimmed = 0
    for pid, handle in _enum_processes():
        try:
            if _PSAPI.EmptyWorkingSet(handle):
                trimmed += 1
        except Exception:
            pass
        finally:
            _KERNEL32.CloseHandle(handle)
    return trimmed


def trim_process_working_set(pid: int) -> bool:
    """Trim single process working set. Returns True on success."""
    h = _KERNEL32.OpenProcess(_PROCESS_SET_QUOTA, False, pid)
    if not h:
        return False
    try:
        return bool(_PSAPI.EmptyWorkingSet(h))
    finally:
        _KERNEL32.CloseHandle(h)


# ── Standby List ──

# SystemInformationClass 0x40 = SystemMemoryListInformation
_SYSTEM_MEMORY_LIST_INFORMATION = 0x40


class _MEMORY_LIST_COMMAND(ctypes.c_uint):
    MemoryPurgeStandbyList = 4
    MemoryPurgeCombinedPageList = 5
    MemoryPurgeLowPriorityStandbyList = 6


class _SYSTEM_MEMORY_LIST_INFO(ctypes.Structure):
    _fields_ = [
        ("command", ctypes.c_uint),
        ("data", ctypes.c_void_p),
    ]


def clear_standby_list(aggressive: bool = True) -> bool:
    """Clear Windows Standby List — cached memory from closed applications.

    This is the single most impactful optimization for low-RAM systems.
    The Standby List holds pages from closed apps that Windows keeps "just in case".
    Clearing it instantly converts cached RAM → free RAM.

    WinMemoryCleaner docs:
      "Clears the entire Standby List. This aggressive method frees the maximum
       amount of cached RAM for demanding tasks."

    Verifiable: open resmon.exe → Memory tab → watch blue 'Standby' drop to zero.
    """
    try:
        command = (
            _MEMORY_LIST_COMMAND.MemoryPurgeStandbyList
            if aggressive
            else _MEMORY_LIST_COMMAND.MemoryPurgeLowPriorityStandbyList
        )
        info = _SYSTEM_MEMORY_LIST_INFO(command=command, data=None)
        status = _NTDLL.NtSetSystemInformation(
            _SYSTEM_MEMORY_LIST_INFORMATION,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        return status == 0  # STATUS_SUCCESS
    except Exception:
        return False


def clear_combined_page_list() -> bool:
    """Flush Combined Page List — merged identical pages (Windows 8+/2012+).

    Windows combines identical memory pages across processes to save RAM.
    This flushes those combinations, releasing the shared pages.
    """
    try:
        info = _SYSTEM_MEMORY_LIST_INFO(
            command=_MEMORY_LIST_COMMAND.MemoryPurgeCombinedPageList, data=None
        )
        status = _NTDLL.NtSetSystemInformation(
            _SYSTEM_MEMORY_LIST_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)
        )
        return status == 0
    except Exception:
        return False


# ── File Cache ──


def flush_file_caches() -> int:
    """Flush filesystem cache to disk for all fixed drives.

    Forces pending writes to disk and releases cached data from RAM.
    Useful before launching memory-intensive pipeline stages.
    """
    # Use Windows built-in: sync.exe if available, or call FlushFileBuffers on volumes
    flushed = 0
    for drive in range(ord("A"), ord("Z") + 1):
        drive_letter = f"{chr(drive)}:\\"
        try:
            # FlushFileBuffers on root volume
            handle = _KERNEL32.CreateFileW(
                f"\\\\.\\{chr(drive)}:",
                0x80000000,  # GENERIC_READ
                0x00000001 | 0x00000002,  # FILE_SHARE_READ | FILE_SHARE_WRITE
                None,
                3,  # OPEN_EXISTING
                0,
                None,
            )
            if handle and handle != -1:
                try:
                    _KERNEL32.FlushFileBuffers(handle)
                    flushed += 1
                except Exception:
                    pass
                finally:
                    _KERNEL32.CloseHandle(handle)
        except Exception:
            continue
    return flushed


# ── Process Priority ──

# Priority classes
PROCESS_PRIORITY_CLASSES = {
    "idle": 0x00000040,        # IDLE_PRIORITY_CLASS
    "below_normal": 0x00004000,  # BELOW_NORMAL_PRIORITY_CLASS
    "normal": 0x00000020,       # NORMAL_PRIORITY_CLASS
    "above_normal": 0x00008000,  # ABOVE_NORMAL_PRIORITY_CLASS
    "high": 0x00000080,         # HIGH_PRIORITY_CLASS
    "realtime": 0x00000100,     # REALTIME_PRIORITY_CLASS
}

# Processes to demote to idle priority (bloatware that shouldn't compete)
BLOCKABLE_BLOAT = [
    "OneDrive.exe",
    "Skype.exe",
    "Cortana.exe",
    "Widgets.exe",
    "GameBar.exe",
    "YourPhone.exe",
    "OfficeClickToRun.exe",
]


def set_self_priority(level: str = "above_normal") -> bool:
    """Boost our own process priority."""
    cls = PROCESS_PRIORITY_CLASSES.get(level)
    if cls:
        return bool(_KERNEL32.SetPriorityClass(_KERNEL32.GetCurrentProcess(), cls))
    return False


def demote_bloatware_priority() -> int:
    """Set known bloatware processes to idle priority. Returns count of demoted."""
    demoted = 0
    for proc_name in BLOCKABLE_BLOAT:
        try:
            r = subprocess.run(
                ["wmic", "process", "where", f"name='{proc_name}'", "get", "processid"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            for line in r.stdout.splitlines():
                line = line.strip()
                if line.isdigit():
                    pid = int(line)
                    h = _KERNEL32.OpenProcess(0x0200, False, pid)  # PROCESS_SET_INFORMATION
                    if h:
                        try:
                            _KERNEL32.SetPriorityClass(h, PROCESS_PRIORITY_CLASSES["idle"])
                            demoted += 1
                        except Exception:
                            pass
                        finally:
                            _KERNEL32.CloseHandle(h)
        except Exception:
            pass
    return demoted


# ═══════════════════════════════════════════════════════════════════════════════
#  Combined system optimization
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class OptimizeResult:
    """What happened during an optimization cycle."""

    working_sets_trimmed: int = 0
    standby_cleared: bool = False
    combined_pages_cleared: bool = False
    file_caches_flushed: int = 0
    bloat_demoted: int = 0
    gc_collected: int = 0
    hogs_killed: int = 0
    freed_mb_estimate: int = 0

    def summary(self) -> str:
        parts = []
        if self.working_sets_trimmed:
            parts.append(f"WS×{self.working_sets_trimmed}")
        if self.standby_cleared:
            parts.append("Standby")
        if self.combined_pages_cleared:
            parts.append("Combined")
        if self.file_caches_flushed:
            parts.append(f"Cache×{self.file_caches_flushed}")
        if self.bloat_demoted:
            parts.append(f"Bloat×{self.bloat_demoted}")
        if self.hogs_killed:
            parts.append(f"Killed×{self.hogs_killed}")
        if self.gc_collected:
            parts.append(f"GC×{self.gc_collected}")
        return ", ".join(parts) if parts else "nothing to clean"


def system_optimize(hogs_to_kill: list | None = None) -> OptimizeResult:
    """Run a full system optimization cycle.

    Call this:
    - Before heavy pipeline stages (Demucs, Whisper, TTS)
    - On low-resource warnings
    - Periodically during long-running tasks

    Returns an OptimizeResult with counts of what was done.
    """
    result = OptimizeResult()

    # 1. Trim all process working sets (releases non-essential RAM)
    result.working_sets_trimmed = empty_all_working_sets()

    # 2. Clear Standby List (cached RAM → free RAM) — biggest impact
    result.standby_cleared = clear_standby_list(aggressive=True)

    # 3. Combined page list (Windows 8+)
    if sys.getwindowsversion().major >= 8:
        result.combined_pages_cleared = clear_combined_page_list()

    # 4. Flush file caches
    result.file_caches_flushed = flush_file_caches()

    # 5. Demote bloatware priority
    result.bloat_demoted = demote_bloatware_priority()

    # 6. Python GC
    gc.collect()
    result.gc_collected = 1

    # 7. Kill VRAM hogs (passed from ResourceMonitor)
    if hogs_to_kill:
        result.hogs_killed = _kill_hogs(hogs_to_kill)

    return result


def _kill_hogs(process_list: list) -> int:
    killed = 0
    for proc_name in process_list:
        try:
            r = subprocess.run(
                ["taskkill", "/f", "/im", proc_name],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if r.returncode == 0:
                killed += 1
        except Exception:
            pass
    return killed


# ═══════════════════════════════════════════════════════════════════════════════
#  Quick self-diagnostics
# ═══════════════════════════════════════════════════════════════════════════════


def test_standby_clear():
    """Quick self-test: clear standby list and print result."""
    import time
    t0 = time.time()
    ok = clear_standby_list(aggressive=True)
    ms = (time.time() - t0) * 1000
    print(f"StandbyList clear: {'OK' if ok else 'FAIL'} ({ms:.0f}ms)")
    return ok


if __name__ == "__main__":
    test_standby_clear()
    r = system_optimize()
    print(f"System optimize: {r.summary()}")
