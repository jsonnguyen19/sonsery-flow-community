"""Sub-run registry + kill helpers.

Manages the sub-processes spawned by the `shell` tool: see what is running,
kill them individually, avoid orphans when watchctx exits.

See docs/features/subrun-manager.md for the full design.

Public API:
- register / mark_status / unregister
- list_all / get_one
- kill_one / kill_all / cleanup_all / prune_stale
- subrun_paths / read_registry / write_registry

Registry file: .state/watchctx.subruns.json (atomic write + file lock).

Cross-platform details (kill/pid-alive/process-group) are pushed down to
runctx.platform.* — this module only orchestrates.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from .constants import (
    CLEANUP_TIMEOUT,
    KILL_FINAL_WAIT,
    KILL_GRACE_SECONDS,
    KILL_POLL_INTERVAL,
    REGISTRY_VERSION,
    STATE_DIR,
    SUBUNS_FILE,
    SUBUNS_LOCK_FILE,
    SUBUNS_TMP_FILE,
)
from .platform import is_group_alive, kill_group
from .platform.lock import acquire_lock, release_lock
from .platform.process import SIGKILL, SIGTERM
from .platform.system import is_windows

# ============ FILE LOCK ============


class _FileLock:
    """Cross-platform advisory lock on a single file.

    POSIX: fcntl.flock. Windows: msvcrt.locking (details in
    runctx.platform.lock). Not re-entrant. Use as a context manager.
    """

    def __init__(self, path: Path, timeout: float = 2.0):
        self.path = path
        self.timeout = timeout
        self._fh = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+")
        deadline = time.time() + self.timeout
        while True:
            try:
                self._acquire()
                return self
            except OSError:
                if time.time() >= deadline:
                    # Could not acquire the lock within the timeout -> proceed anyway (best-effort).
                    # Registry writes may race, but that is rare.
                    return self
                time.sleep(0.05)

    def _acquire(self) -> None:
        assert self._fh is not None
        acquire_lock(self._fh, windows=is_windows())

    def __exit__(self, *_exc):
        fh = self._fh
        try:
            if fh is not None:
                release_lock(fh, windows=is_windows())
        finally:
            try:
                if fh is not None:
                    fh.close()
            except Exception:
                pass
            self._fh = None


# ============ REGISTRY I/O ============


def _empty_registry() -> dict[str, Any]:
    return {
        "version": REGISTRY_VERSION,
        "updated_at": int(time.time() * 1000),
        "subruns": [],
    }


def read_registry() -> dict[str, Any]:
    """Read the registry. Returns empty when the file is missing / corrupt."""
    if not SUBUNS_FILE.exists():
        return _empty_registry()
    try:
        raw = SUBUNS_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict) or "subruns" not in data:
            return _empty_registry()
        if not isinstance(data["subruns"], list):
            return _empty_registry()
        return data
    except Exception:
        return _empty_registry()


def write_registry(data: dict[str, Any]) -> None:
    """Atomic write: write tmp -> os.replace.

    The caller must hold _FileLock before calling (see the _with_lock helper).
    """
    data["version"] = REGISTRY_VERSION
    data["updated_at"] = int(time.time() * 1000)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = str(SUBUNS_TMP_FILE)
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, str(SUBUNS_FILE))


def _with_lock(fn):
    """Decorator: run fn inside _FileLock."""

    def wrapper(*args, **kwargs):
        with _FileLock(SUBUNS_LOCK_FILE):
            return fn(*args, **kwargs)

    return wrapper


# ============ PUBLIC API ============


def register(
    sub_id: str,
    *,
    payload_id: int | None,
    tool: str,
    label: str,
    command: str,
    mode: str,
    pid: int,
    pgid: int,
) -> None:
    """Add a `running` entry to the registry."""
    with _FileLock(SUBUNS_LOCK_FILE):
        data = read_registry()
        # Dedup: if sub_id already exists (race/retry), update instead of adding a new one.
        data["subruns"] = [r for r in data["subruns"] if r.get("sub_id") != sub_id]
        data["subruns"].append(
            {
                "sub_id": sub_id,
                "payload_id": payload_id,
                "tool": tool,
                "label": label,
                "command": command,
                "mode": mode,
                "pid": pid,
                "pgid": pgid,
                "started_at": int(time.time() * 1000),
                "status": "running",
                "exit_code": None,
            }
        )
        write_registry(data)


def mark_status(sub_id: str, status: str, exit_code: int | None = None) -> None:
    """Update the status (and exit_code when provided) of a sub-run.

    When the status is 'done' / 'error' / 'stuck' -> also write finished_at (epoch ms)
    so the UI shows a correct elapsed time (frozen, does not keep growing).
    """
    with _FileLock(SUBUNS_LOCK_FILE):
        data = read_registry()
        for r in data["subruns"]:
            if r.get("sub_id") == sub_id:
                r["status"] = status
                if exit_code is not None:
                    r["exit_code"] = int(exit_code)
                if status in ("done", "error", "stuck"):
                    r["finished_at"] = int(time.time() * 1000)
                break
        write_registry(data)


def unregister(sub_id: str) -> None:
    """Remove an entry from the registry."""
    with _FileLock(SUBUNS_LOCK_FILE):
        data = read_registry()
        before = len(data["subruns"])
        data["subruns"] = [r for r in data["subruns"] if r.get("sub_id") != sub_id]
        if len(data["subruns"]) != before:
            write_registry(data)


def list_all() -> list[dict[str, Any]]:
    """Return the sub-run list (no read lock — read-only).

    Stable sort by (payload_id, index within the payload) so the UI shows the
    commands in the order the user wrote them. Parsed from the sub_id format
    '<payload_id>:<index>'. Falls back to started_at when sub_id is not in that format.
    """
    data = read_registry()
    runs = list(data.get("subruns", []))

    def _sort_key(r: dict[str, Any]):
        sub_id = r.get("sub_id", "")
        if ":" in sub_id:
            pid_part, _, idx_part = sub_id.rpartition(":")
            try:
                return (0, int(pid_part) if pid_part.isdigit() else 0, int(idx_part))
            except ValueError:
                pass
        return (1, r.get("started_at", 0), 0)

    runs.sort(key=_sort_key)
    return runs


def get_one(sub_id: str) -> dict[str, Any] | None:
    for r in read_registry().get("subruns", []):
        if r.get("sub_id") == sub_id:
            return r
    return None


def kill_one(sub_id: str) -> dict[str, Any]:
    """Kill one sub-run: SIGTERM -> grace -> SIGKILL.

    Idempotent: if the entry is missing / already dead -> return ok.
    Returns {ok, sub_id, exit_code?, reason?}.
    """
    entry = get_one(sub_id)
    if entry is None:
        return {"ok": False, "sub_id": sub_id, "reason": "not found"}

    status = entry.get("status")
    pgid = int(entry.get("pgid") or 0)

    if status in ("done", "error"):
        return {"ok": True, "sub_id": sub_id, "exit_code": entry.get("exit_code")}

    mark_status(sub_id, "killing")

    # If the group is already dead -> mark done immediately.
    if not is_group_alive(pgid):
        mark_status(sub_id, "done", exit_code=0)
        return {"ok": True, "sub_id": sub_id, "exit_code": 0}

    # SIGTERM
    kill_group(pgid, SIGTERM)

    deadline = time.time() + KILL_GRACE_SECONDS
    while time.time() < deadline:
        if not is_group_alive(pgid):
            mark_status(sub_id, "done", exit_code=143)  # 128 + 15
            return {"ok": True, "sub_id": sub_id, "exit_code": 143}
        time.sleep(KILL_POLL_INTERVAL)

    # SIGKILL
    kill_group(pgid, SIGKILL)
    time.sleep(KILL_FINAL_WAIT)
    if not is_group_alive(pgid):
        mark_status(sub_id, "done", exit_code=137)  # 128 + 9
        return {"ok": True, "sub_id": sub_id, "exit_code": 137}

    # Still alive -> mark stuck.
    mark_status(sub_id, "stuck")
    return {"ok": False, "sub_id": sub_id, "reason": "stuck (group still alive after SIGKILL)"}


def kill_all() -> dict[str, Any]:
    """Kill every sub-run. Sequential kill (simple, rarely > 10 items).

    Returns {ok, killed: [sub_id], failed: [{sub_id, reason}]}.
    """
    killed: list[str] = []
    failed: list[dict[str, Any]] = []
    for entry in list_all():
        sub_id = entry.get("sub_id")
        if not sub_id:
            continue
        if entry.get("status") in ("done", "error"):
            continue
        res = kill_one(sub_id)
        if res.get("ok"):
            killed.append(sub_id)
        else:
            failed.append({"sub_id": sub_id, "reason": res.get("reason", "unknown")})
    return {"ok": True, "killed": killed, "failed": failed}


def cleanup_all(timeout: float = CLEANUP_TIMEOUT) -> None:
    """Called in the watcher's finally: kill every sub-run, wait up to `timeout`.

    Best-effort — never raises even on error. Deletes the registry file when done.
    """
    deadline = time.time() + timeout
    try:
        for entry in list_all():
            if time.time() >= deadline:
                break
            sub_id = entry.get("sub_id")
            if not sub_id or entry.get("status") in ("done", "error"):
                continue
            try:
                kill_one(sub_id)
            except Exception:
                pass
    finally:
        # Delete the registry file — avoid carry-over into another session.
        try:
            SUBUNS_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            SUBUNS_TMP_FILE.unlink(missing_ok=True)
        except Exception:
            pass


def prune_stale() -> dict[str, Any]:
    """On watcher start: kill live PGIDs from the old registry, delete the file.

    Returns {killed: [...], pruned: N}.
    """
    killed: list[str] = []
    pruned = 0
    try:
        for entry in list_all():
            sub_id = entry.get("sub_id")
            pgid = int(entry.get("pgid") or 0)
            status = entry.get("status")
            if not sub_id:
                pruned += 1
                continue
            if status in ("done", "error"):
                pruned += 1
                continue
            if is_group_alive(pgid) and kill_one(sub_id).get("ok"):
                killed.append(sub_id)
            pruned += 1
    finally:
        try:
            SUBUNS_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            SUBUNS_TMP_FILE.unlink(missing_ok=True)
        except Exception:
            pass
    return {"killed": killed, "pruned": pruned}


def make_sub_id(payload_id: int | None, index: int) -> str:
    """Standard sub_id format: '<payload_id>:<index>'. Falls back to 'x' when no id."""
    pid_part = str(payload_id) if payload_id is not None else "x"
    return f"{pid_part}:{index}"
