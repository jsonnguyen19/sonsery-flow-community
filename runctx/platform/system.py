"""OS detection + process-group helpers (cross-platform).

Pattern: public function = dispatcher thuan (lookup + goi private). Private
function = `_<action>_<subject>_<platform>`. Caller is OS-agnostic.
"""

from __future__ import annotations

import os
import platform
import subprocess

# ============ OS DETECTION ============


def current_os() -> str:
    """Returns 'Windows' | 'Darwin' | 'Linux' | <other>. Single caller of platform.system()."""
    return platform.system()


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_linux() -> bool:
    return platform.system() == "Linux"


def is_macos() -> bool:
    return platform.system() == "Darwin"


# ============ SPAWN KWARGS (dispatcher) ============
#
# Windows: creationflags=CREATE_NEW_PROCESS_GROUP (no real killpg, but
# CTRL_BREAK_EVENT and taskkill /T are available).
# POSIX: start_new_session=True.
#
# Dict dispatch instead of if/else; works on Python 3.8. Unknown OS falls
# back to the POSIX branch.


def _create_new_process_group_flag_windows() -> int:
    return getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


def _create_new_process_group_flag_posix() -> int:
    return 0


_CREATE_FLAG_BY_OS = {
    "Windows": _create_new_process_group_flag_windows,
}


def create_new_process_group_flag() -> int:
    """Windows creation flag for a separate process group. Non-Windows -> 0."""
    builder = _CREATE_FLAG_BY_OS.get(current_os(), _create_new_process_group_flag_posix)
    return builder()


def _spawn_kwargs_windows() -> dict:
    return {"creationflags": _create_new_process_group_flag_windows()}


def _spawn_kwargs_posix() -> dict:
    return {"start_new_session": True}


_SPAWN_KWARGS_BY_OS = {
    "Windows": _spawn_kwargs_windows,
}


def spawn_kwargs() -> dict:
    """Common Popen kwargs to create a separate process group."""
    builder = _SPAWN_KWARGS_BY_OS.get(current_os(), _spawn_kwargs_posix)
    return builder()


# ============ PGID (dispatcher) ============


def _get_pgid_windows(pid: int) -> int:
    """Windows has no PGID -> fall back to PID."""
    return pid


def _get_pgid_posix(pid: int) -> int:
    try:
        return os.getpgid(pid)
    except Exception:
        return pid


def get_pgid(pid: int) -> int:
    """Get the process PGID. Windows -> pid, POSIX -> os.getpgid (fallback pid)."""
    if is_windows():
        return _get_pgid_windows(pid)
    return _get_pgid_posix(pid)
