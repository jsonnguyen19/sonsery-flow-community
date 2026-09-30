"""In-memory latest result + terminal log ring buffer (thread-safe).

Keeps module-level mutable globals to match the old watchctx behavior.
"""

from __future__ import annotations

import re
import threading

from .utils.hash import sha

latest_result = ""
latest_result_hash = ""
latest_result_lock = threading.Lock()


# ============ TERMINAL LOG RING BUFFER ============

_log_buffer: list[str] = []
_log_lock = threading.Lock()
_log_seq: int = 0

_LOG_CAP_LINES = 2000
_LOG_CAP_CHARS = 500_000
_MAX_LINE_CHARS = 500  # MAX length of a line AFTER truncation (including the trailing '…')

_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[A-Za-z]"  # CSI (SGR, cursor, ?25l/h...)
    r"|\x1b\][^\x07]*\x07"  # OSC (set title, ...)
    r"|\x1b[()][A-Z0-9]"  # charset select
)


def strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)


def _trim_locked() -> None:
    """Drop the oldest lines when the line cap or total char count is exceeded."""
    while len(_log_buffer) > _LOG_CAP_LINES:
        _log_buffer.pop(0)
        # first_seq is not incremented here - derived from _log_seq - len(_log_buffer) + 1
    total = sum(len(line) + 1 for line in _log_buffer)
    while total > _LOG_CAP_CHARS and _log_buffer:
        removed = _log_buffer.pop(0)
        total -= len(removed) + 1


def append_log(line: str) -> None:
    """Append one ANSI-stripped line to the ring buffer.

    - Truncate lines longer than _MAX_LINE_CHARS + add a trailing '…'.
    - Skip empty lines after stripping.
    - Cap both line count and total char count.
    """
    global _log_seq
    clean = strip_ansi(str(line)).rstrip("\n").rstrip("\r")
    if not clean.strip():
        return
    if len(clean) > _MAX_LINE_CHARS:
        # Keep total length <= _MAX_LINE_CHARS (including the trailing '…').
        clean = clean[: _MAX_LINE_CHARS - 1] + "…"
    with _log_lock:
        _log_seq += 1
        _log_buffer.append(clean)
        _trim_locked()


def get_log_since(since: int, limit: int = 200) -> dict:
    """Return logs with seq > since.

    Returns { lines, next, first_seq, dropped }.
    """
    # Server-side clamp: limit <= 100 so the response is at most ~50KB, guaranteed
    # under MAX_RPC_RESPONSE_CHARS = 100_000 (see docs/ui-terminal-logs.md §1.2.5).
    limit = max(1, min(int(limit), 100))
    since = int(since) if since else 0
    with _log_lock:
        if _log_buffer:
            first_seq = _log_seq - len(_log_buffer) + 1
        else:
            first_seq = _log_seq + 1
        dropped = since < (first_seq - 1) and since < _log_seq
        # Determine the start index in the buffer (0-based)
        start_idx = max(0, since - first_seq + 1)
        lines = list(_log_buffer[start_idx : start_idx + limit])
        # next = seq of the last line returned (or since when there are no lines)
        if lines:
            next_seq = first_seq + start_idx + len(lines) - 1
        else:
            next_seq = _log_seq if since >= _log_seq else since
        return {
            "ok": True,
            "lines": lines,
            "next": next_seq,
            "first_seq": first_seq,
            "dropped": bool(dropped),
        }


def set_latest_result(text: str) -> None:
    global latest_result, latest_result_hash
    with latest_result_lock:
        latest_result = text
        latest_result_hash = sha(text)


def get_latest_result_payload() -> dict:
    with latest_result_lock:
        return {
            "ok": True,
            "hash": latest_result_hash,
            "result": latest_result,
        }


def consume_latest_result() -> None:
    global latest_result, latest_result_hash
    with latest_result_lock:
        latest_result = ""
        latest_result_hash = ""
