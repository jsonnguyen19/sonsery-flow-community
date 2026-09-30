"""Process helpers: check pid running, shutdown previous watcher.

Cross-platform logic is pushed down to runctx.platform.*; this module only
calls functions (facade); it no longer checks the platform itself.
"""

from __future__ import annotations

from pathlib import Path

from ..platform import is_pid_alive
from ..platform.process import shutdown_pid

# Keep the old API for backward compat (tests + watcher import).
is_process_running = is_pid_alive


def shutdown_old_watchctx(pid_file: Path) -> None:
    """Shut down the previous watchctx process if present. Cross-platform.

    OS logic (Windows: OpenProcess/TerminateProcess + taskkill fallback,
    POSIX: SIGTERM -> wait -> SIGKILL) lives in platform.process.shutdown_pid.
    """
    if not pid_file.exists():
        return

    try:
        old_pid = int(pid_file.read_text(encoding="utf-8").strip())
        if is_pid_alive(old_pid):
            print(f"Shutting down old watchctx process (PID: {old_pid})...")
            shutdown_pid(old_pid)
    except (ValueError, FileNotFoundError) as e:
        print(f"WARN: Failed to read PID file: {e}")

    # Remove stale PID file
    try:
        pid_file.unlink(missing_ok=True)
    except Exception:
        pass
