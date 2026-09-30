"""PID/PGID alive check + kill/terminate (cross-platform).

Pattern: public function = pure dispatcher (lookup + call private). Private
function = `_<action>_<subject>_<platform>`. Caller is OS-agnostic.

Windows: taskkill /F /PID (single) and /F /T /PID (tree).
POSIX  : os.kill (single) and os.killpg (group).
"""

from __future__ import annotations

import os
import subprocess
import time

from .system import is_linux, is_windows
from .zombie import group_has_live_process, is_zombie

# Windows kernel32 constants
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_PROCESS_TERMINATE = 0x0001

# POSIX signal numbers as ints to avoid importing signal.
SIGTERM = 15
SIGKILL = 9

# taskkill subprocess timeout.
_TASKKILL_TIMEOUT = 5


# ============ WINDOWS CTYPES HELPERS (private) ============


def _open_handle_windows(pid: int, access: int):
    """Open a Windows handle for pid. Returns the handle or None."""
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        return kernel32.OpenProcess(access, False, pid)
    except Exception:
        return None


def _close_handle_windows(handle) -> None:
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle(handle)
    except Exception:
        pass


# ============ IS PID ALIVE (dispatcher) ============


def _is_pid_alive_windows(pid: int) -> bool:
    handle = _open_handle_windows(pid, _PROCESS_QUERY_LIMITED_INFORMATION)
    if handle:
        _close_handle_windows(handle)
        return True
    return False


def _is_pid_alive_posix(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except Exception:
        return False
    # On Linux: exclude zombies.
    return not is_zombie(pid)


def is_pid_alive(pid: int) -> bool:
    """Check whether a process is TRULY alive (excluding zombies). Cross-platform."""
    if pid <= 0:
        return False
    if is_windows():
        return _is_pid_alive_windows(pid)
    return _is_pid_alive_posix(pid)


# ============ IS GROUP ALIVE (dispatcher) ============


def _is_group_alive_windows(pgid: int) -> bool:
    """Windows has no process groups -> check the original pid."""
    return is_pid_alive(pgid)


def _is_group_alive_linux(pgid: int) -> bool:
    """Linux: check group exists + scan /proc excluding zombies."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Group exists but permission denied -> treat as alive.
        return True
    except Exception:
        return False
    # Group exists -> scan its PIDs, excluding zombies.
    result = group_has_live_process(pgid)
    if result is None:
        # /proc unreadable -> treat as alive (safe fallback).
        return True
    return result


def _is_group_alive_posix(pgid: int) -> bool:
    """macOS / BSD: no /proc, fallback to killpg 0."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False
    return True


def is_group_alive(pgid: int) -> bool:
    """Check whether any process in the group is TRULY alive.

    Windows: fall back to checking the original pid.
    Linux  : killpg(0) + scan /proc excluding zombies.
    macOS/BSD: killpg(0) (no /proc).
    """
    if pgid <= 0:
        return False
    if is_windows():
        return _is_group_alive_windows(pgid)
    if is_linux():
        return _is_group_alive_linux(pgid)
    return _is_group_alive_posix(pgid)


# ============ KILL PID (dispatcher) ============


def _kill_pid_windows(pid: int, sig: int) -> bool:
    """Windows: taskkill /F /PID (sig ignored — Windows has no signals)."""
    try:
        subprocess.run(
            ["taskkill", "/F", "/PID", str(pid)],
            capture_output=True,
            timeout=_TASKKILL_TIMEOUT,
        )
        return True
    except Exception:
        return False


def _kill_pid_posix(pid: int, sig: int) -> bool:
    try:
        os.kill(pid, sig)
        return True
    except ProcessLookupError:
        return True  # Already dead -> treat as success.
    except Exception:
        return False


def kill_pid(pid: int, sig: int = SIGTERM) -> bool:
    """Send a signal to a PID. Windows: taskkill /F /PID. True on success."""
    if pid <= 0:
        return False
    if is_windows():
        return _kill_pid_windows(pid, sig)
    return _kill_pid_posix(pid, sig)


# ============ KILL GROUP (dispatcher) ============


def _kill_group_windows(pgid: int, sig: int) -> bool:
    """Windows: taskkill /F /T /PID kills the whole tree (sig ignored)."""
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pgid)],
            capture_output=True,
            timeout=_TASKKILL_TIMEOUT,
        )
        return True
    except Exception:
        return False


def _kill_group_posix(pgid: int, sig: int) -> bool:
    try:
        os.killpg(pgid, sig)
        return True
    except ProcessLookupError:
        return True  # Already dead -> treat as success.
    except Exception:
        return False


def kill_group(pgid: int, sig: int = SIGTERM) -> bool:
    """Send a signal to the whole process group. Windows: taskkill /F /T /PID.

    True on success (or if already dead).
    """
    if pgid <= 0:
        return False
    if is_windows():
        return _kill_group_windows(pgid, sig)
    return _kill_group_posix(pgid, sig)


# ============ TERMINATE PID (dispatcher) ============


def _terminate_pid_windows(pid: int) -> None:
    """Terminate a process on Windows (best-effort, taskkill fallback).

    1. OpenProcess(PROCESS_TERMINATE) -> TerminateProcess -> CloseHandle
    2. sleep(0.5)
    3. Still alive -> taskkill /F /PID
    4. Print success message
    OpenProcess failure falls back to taskkill /F /PID.
    """
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(_PROCESS_TERMINATE, False, pid)
        if handle:
            kernel32.TerminateProcess(handle, 0)
            kernel32.CloseHandle(handle)
            time.sleep(0.5)
            if is_pid_alive(pid):
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True,
                    timeout=_TASKKILL_TIMEOUT,
                )
            print(f"Successfully shut down old process (PID: {pid})")
        else:
            # Fallback to taskkill
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                timeout=_TASKKILL_TIMEOUT,
            )
    except Exception as e:
        print(f"WARN: Failed to terminate process: {e}")
        # Last resort
        try:
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                timeout=_TASKKILL_TIMEOUT,
            )
        except Exception:
            pass


def terminate_pid(pid: int) -> None:
    """Terminate a process (best-effort). Windows only; non-Windows is a no-op."""
    if is_windows():
        _terminate_pid_windows(pid)


# ============ SHUTDOWN PID (dispatcher) ============
#
# Shut down a stale process (e.g. previous watcher session). Windows uses
# OpenProcess/TerminateProcess + taskkill fallback. POSIX uses
# SIGTERM -> wait 0.5s -> SIGKILL if still alive.


_SIGTERM_GRACE_SECONDS = 0.5


def _shutdown_pid_windows(pid: int) -> None:
    _terminate_pid_windows(pid)


def _shutdown_pid_posix(pid: int) -> None:
    kill_pid(pid, SIGTERM)
    time.sleep(_SIGTERM_GRACE_SECONDS)
    if is_pid_alive(pid):
        kill_pid(pid, SIGKILL)
        print(f"Force killed old process (PID: {pid})")
    else:
        print(f"Successfully shut down old process (PID: {pid})")


def shutdown_pid(pid: int) -> None:
    """Shut down a stale process (best-effort). OS-agnostic for callers."""
    if is_windows():
        _shutdown_pid_windows(pid)
    else:
        _shutdown_pid_posix(pid)
