"""Payload history ring buffer: stores up to N executed payloads + results.

Pattern: in-memory list + JSON file persist, atomic write (tmp + os.replace),
thread-safe via threading.Lock. Rotate FIFO when over cap.

File: .state/payload_history.json (JSON array, newest first).
Cap: configurable via Settings (default 100, min 20, max 1000).
Cap stored in .state/watchctx.history-cap (int as text).

Row schema (stored to file):
{
  "id": int (payload id),
  "ts": int (unix ms when written),
  "tool": str,
  "payload": str (FULL payload, capped at HISTORY_FULL_CHARS),
  "result": str (FULL output, capped at HISTORY_FULL_CHARS),
  "status": "success"|"error",
  "duration_ms": int,
}

- list_rows() returns a 300-char preview (fields 'summary' + 'result_preview')
  to avoid an RPC response > 100KB when there are many rows.
- get_row() returns the full content (payload + result) for the detail view.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

from .constants import (
    DEFAULT_CAP,
    HISTORY_CAP_FILE,
    HISTORY_FILE,
    HISTORY_FULL_CHARS,
    HISTORY_PREVIEW_CHARS,
    MAX_CAP,
    MIN_CAP,
    STATE_DIR,
)

_lock = threading.Lock()
_cache: list[dict[str, Any]] | None = None


# ============ CAP CONFIG ============


def _read_cap() -> int:
    """Read the cap from file. Fallback DEFAULT_CAP when missing/invalid."""
    try:
        raw = HISTORY_CAP_FILE.read_text(encoding="utf-8").strip()
        val = int(raw)
    except (OSError, ValueError):
        return DEFAULT_CAP
    return max(MIN_CAP, min(MAX_CAP, val))


def set_cap(value: int) -> int:
    """Set a new cap (clamped MIN..MAX). Persist to file. Return the clamped value.

    If the cap decreases below the current row count, trim immediately.
    """
    clamped = max(MIN_CAP, min(MAX_CAP, int(value)))
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_CAP_FILE.write_text(str(clamped), encoding="utf-8")
    with _lock:
        global _cache
        if _cache is not None and len(_cache) > clamped:
            _cache = _cache[:clamped]
            _write_locked(_cache)
    return clamped


def get_cap() -> int:
    return _read_cap()


# ============ IO ============


def _atomic_write(data: list[dict[str, Any]]) -> None:
    """Write the file safely: tmp + fsync + os.replace."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = HISTORY_FILE.with_suffix(".json.tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=None, separators=(",", ":"))
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, HISTORY_FILE)


def _write_locked(data: list[dict[str, Any]]) -> None:
    """Caller already holds _lock. Writes the file + updates the cache."""
    global _cache
    try:
        _atomic_write(data)
    except OSError:
        # Best-effort: history must never crash the watcher.
        pass
    _cache = data


def _load_locked() -> list[dict[str, Any]]:
    """Read the file the first time (lazy). Caller already holds _lock."""
    global _cache
    if _cache is not None:
        return _cache
    try:
        raw = HISTORY_FILE.read_text(encoding="utf-8")
        parsed = json.loads(raw) if raw.strip() else []
        if not isinstance(parsed, list):
            parsed = []
    except (OSError, json.JSONDecodeError):
        parsed = []
    _cache = parsed
    return _cache


# ============ PUBLIC API ============


def append(
    *,
    payload_id: Any | None,
    tool: str,
    payload_preview: str,
    result_preview: str,
    status: str,
    duration_ms: int,
) -> None:
    """Add one row at the head of history (newest first). Rotate when over cap.

    Stores the FULL payload/result (each field capped at HISTORY_FULL_CHARS) to file.
    Previews for the list view are truncated separately in list_rows().

    Best-effort: any IO error is swallowed, never raised outward.
    """
    ts = int(time.time() * 1000)
    row: dict[str, Any] = {
        "id": payload_id if isinstance(payload_id, int) else ts,
        "ts": ts,
        "tool": str(tool or "unknown")[:64],
        "payload": (payload_preview or "")[:HISTORY_FULL_CHARS],
        "result": (result_preview or "")[:HISTORY_FULL_CHARS],
        "status": "success" if status == "success" else "error",
        "duration_ms": max(0, int(duration_ms)),
    }

    cap = _read_cap()
    with _lock:
        rows = _load_locked()
        # Prepend newest (id can repeat if the caller sends two payloads with the same id —
        # acceptable, the UI will show both rows).
        new_rows = [row, *rows]
        if len(new_rows) > cap:
            new_rows = new_rows[:cap]
        _write_locked(new_rows)


def _to_preview_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a full row -> preview row (for the list view). Truncates the two big fields."""
    return {
        "id": row.get("id"),
        "ts": row.get("ts"),
        "tool": row.get("tool"),
        "summary": (row.get("payload") or "")[:HISTORY_PREVIEW_CHARS],
        "status": row.get("status"),
        "result": (row.get("result") or "")[:HISTORY_PREVIEW_CHARS],
        "duration_ms": row.get("duration_ms", 0),
    }


def list_rows(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """Return a list of preview rows (summary + result truncated to 300 chars).

    Does not return full payload/result, avoiding an RPC response > 100KB.
    limit clamped 1..200. offset >= 0.
    """
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    with _lock:
        rows = list(_load_locked())
    total = len(rows)
    sliced = [_to_preview_row(r) for r in rows[offset : offset + limit]]
    return {
        "ok": True,
        "total": total,
        "offset": offset,
        "limit": limit,
        "cap": _read_cap(),
        "rows": sliced,
    }


def get_row(payload_id: int, ts: int | None = None) -> dict[str, Any] | None:
    """Find a row by (id, ts when provided). Returns the FULL row (untruncated).

    When ts is provided, both fields must match (avoid confusion on id collision).
    """
    with _lock:
        rows = list(_load_locked())
    for row in rows:
        if row.get("id") != payload_id:
            continue
        if ts is not None and row.get("ts") != ts:
            continue
        # Return the full row (full payload + result). No truncation.
        return dict(row)
    return None


def clear() -> int:
    """Clear all history. Returns the number of rows removed."""
    with _lock:
        rows = _load_locked()
        n = len(rows)
        _write_locked([])
    return n
