"""Cross-platform primitives.

Centralizes ALL OS-specific logic (platform.system(), Windows ctypes, Linux
/proc, POSIX signals vs taskkill). Callers just call functions; they never
check the platform themselves.

Modules:
- system.py   : OS detection, process group flags, spawn kwargs.
- process.py  : is_pid_alive, is_group_alive, terminate/kill pid/group.
- zombie.py   : Linux /proc zombie detection (used by process.py).

Public API (re-exported here so `from runctx.platform import X` works):
- current_os / is_windows / is_linux / is_macos
- spawn_kwargs / create_new_process_group_flag / get_pgid
- is_pid_alive / is_group_alive
- kill_pid / kill_group / terminate_pid
- SIGTERM / SIGKILL
"""

from __future__ import annotations

from .process import (
    SIGKILL,
    SIGTERM,
    is_group_alive,
    is_pid_alive,
    kill_group,
    kill_pid,
    terminate_pid,
)
from .system import (
    create_new_process_group_flag,
    current_os,
    get_pgid,
    is_linux,
    is_macos,
    is_windows,
    spawn_kwargs,
)

__all__ = [
    "SIGKILL",
    "SIGTERM",
    "create_new_process_group_flag",
    "current_os",
    "get_pgid",
    "is_group_alive",
    "is_linux",
    "is_macos",
    "is_pid_alive",
    "is_windows",
    "kill_group",
    "kill_pid",
    "spawn_kwargs",
    "terminate_pid",
]
