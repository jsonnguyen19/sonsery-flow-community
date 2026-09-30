"""Cross-platform advisory file lock.

POSIX: fcntl.flock. Windows: msvcrt.locking. Caller chi goi `acquire_lock` /
`release_lock` — callers never import fcntl/msvcrt directly.

Pattern: public = dispatcher, private = `_<action>_<subject>_<platform>`.
"""

from __future__ import annotations

# ============ ACQUIRE (dispatcher) ============


def _acquire_lock_windows(fh) -> None:
    import msvcrt

    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)


def _acquire_lock_posix(fh) -> None:
    import fcntl

    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def acquire_lock(fh, *, windows: bool) -> None:
    """Acquire a non-blocking exclusive lock on fh.

    Caller passes windows=True on Windows. Raises OSError if unavailable.
    """
    if windows:
        _acquire_lock_windows(fh)
    else:
        _acquire_lock_posix(fh)


# ============ RELEASE (dispatcher) ============


def _release_lock_windows(fh) -> None:
    import msvcrt

    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)


def _release_lock_posix(fh) -> None:
    import fcntl

    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def release_lock(fh, *, windows: bool) -> None:
    """Release lock tren fh. Best-effort: OSError duoc bo qua."""
    try:
        if windows:
            _release_lock_windows(fh)
        else:
            _release_lock_posix(fh)
    except OSError:
        pass
