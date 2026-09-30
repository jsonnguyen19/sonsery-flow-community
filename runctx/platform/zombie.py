"""Linux zombie detection.

A zombie is a process that has died but has not been reaped by its parent.
It still holds a PID slot, so os.kill(pid, 0) succeeds -> it must be excluded
to avoid detecting a dead process as alive.

Pattern: public function = pure dispatcher, private = `_<action>_<platform>`.
On non-Linux, `_read_stat_*` and `group_has_live_process_*` return None/False
immediately (no /proc reads).
"""

from __future__ import annotations

import os

from .system import is_linux

# ============ /proc READ (private, Linux-only) ============


def _read_stat_linux(pid: int) -> tuple[str, int] | None:
    """Read /proc/<pid>/stat, returns (state, pgrp) or None on failure.

    Format: `pid (comm) state ppid pgrp ...` -> state is the char after the last
    ')' and pgrp is the 3rd field of the remainder (0-indexed: 0=state, 1=ppid, 2=pgrp).
    """
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
            content = f.read()
    except (FileNotFoundError, PermissionError, OSError):
        return None
    rparen = content.rfind(")")
    if rparen == -1:
        return None
    rest = content[rparen + 2 :]
    fields = rest.split()
    if len(fields) < 3:
        return None
    state = fields[0]
    try:
        pgrp = int(fields[2])
    except ValueError:
        return None
    return state, pgrp


def _read_stat_non_linux(pid: int) -> tuple[str, int] | None:
    """Non-Linux: no /proc -> always None."""
    return None


def _read_stat(pid: int) -> tuple[str, int] | None:
    if is_linux():
        return _read_stat_linux(pid)
    return _read_stat_non_linux(pid)


# ============ PUBLIC API (dispatcher) ============


def is_zombie(pid: int) -> bool:
    """Linux: True if process is a zombie. Non-Linux: False."""
    if not is_linux():
        return False
    info = _read_stat_linux(pid)
    return info is not None and info[0] == "Z"


def group_has_live_process(pgid: int) -> bool | None:
    """Scan /proc for a live (non-zombie) process in the group.

    Returns:
    - True  : at least one process with state != 'Z' in the group
    - False : group only has zombies (or no processes)
    - None  : /proc unreadable (caller should treat as alive for safety)

    Linux-only. Non-Linux -> None.
    """
    if not is_linux():
        return None
    try:
        entries = os.listdir("/proc")
    except OSError:
        return None
    for entry in entries:
        if not entry.isdigit():
            continue
        info = _read_stat_linux(int(entry))
        if info is None:
            continue
        state, pgrp = info
        if pgrp != pgid:
            continue
        if state == "Z":
            continue
        return True
    return False
