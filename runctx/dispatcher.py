"""Payload dispatcher: process_payload.

Keeps the previous behavior intact, including the `_internal` flag for old format convert.

Uses dict-dispatch (not an if-else chain) for readability and extensibility.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

from . import history as _history
from .handlers import handle_read, handle_replace, handle_shell, handle_write

__all__ = ["process_payload"]


# ============ TOOL DISPATCHERS ============
# Each tool has its own dispatch function, returning (success, data, error).

Result = Tuple[bool, List[Any], Optional[str]]


def _dispatch_shell(payload: Dict[str, Any]) -> Result:
    commands = payload.get("commands", [])
    if not commands:
        return False, [], "Shell tool requires 'commands' array"
    mode = payload.get("mode", "sequential")
    payload_id = payload.get("id")
    results = handle_shell(commands, payload_id=payload_id, mode=mode)
    return True, results, None


def _dispatch_read(payload: Dict[str, Any]) -> Result:
    files = payload.get("files", [])
    if not files:
        return False, [], "Read tool requires 'files' array or 'path' string"
    results = handle_read(files)
    all_success = all(r.get("success", False) for r in results)
    return all_success, results, None if all_success else "Some files failed to read"


def _dispatch_replace(payload: Dict[str, Any]) -> Result:
    files = payload.get("files", [])
    if not files:
        return False, [], "Replace tool requires 'files' array"
    results = handle_replace(files)
    all_success = all(r.get("success", False) for r in results)
    return all_success, results, None if all_success else "Some replacements failed"


def _dispatch_write(payload: Dict[str, Any]) -> Result:
    files = payload.get("files", [])
    if not files:
        return False, [], "Write tool requires 'files' array"
    results = handle_write(files)
    return True, results, None


# ============ HISTORY (RPC-only, does not go through the clipboard) ============


def _dispatch_get_history(payload: Dict[str, Any]) -> Result:
    limit = payload.get("limit", 50)
    offset = payload.get("offset", 0)
    try:
        limit = int(limit)
        offset = int(offset)
    except (TypeError, ValueError):
        return False, [], "get_history: 'limit'/'offset' must be integers"
    result = _history.list_rows(limit=limit, offset=offset)
    return True, [result], None


def _dispatch_get_history_detail(payload: Dict[str, Any]) -> Result:
    # Uses 'payload_id' instead of 'id' because of the RPC reservation: params.id
    # is forbidden (avoid overriding the correlation id in _flatten_request).
    raw_id = payload.get("payload_id")
    if not isinstance(raw_id, int):
        return False, [], "get_history_detail: 'payload_id' must be an integer"
    ts = payload.get("ts")
    if ts is not None and not isinstance(ts, int):
        return False, [], "get_history_detail: 'ts' must be an integer when provided"
    row = _history.get_row(raw_id, ts=ts)
    if row is None:
        return False, [{"ok": False, "error": "history row not found"}], "history row not found"
    return True, [{"ok": True, "row": row}], None


def _dispatch_clear_history(payload: Dict[str, Any]) -> Result:
    removed = _history.clear()
    return True, [{"ok": True, "removed": removed}], None


def _dispatch_set_history_cap(payload: Dict[str, Any]) -> Result:
    raw = payload.get("cap")
    if raw is None or isinstance(raw, bool):
        return False, [], "set_history_cap: 'cap' must be an integer"
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return False, [], "set_history_cap: 'cap' must be an integer"
    clamped = _history.set_cap(value)
    return True, [{"ok": True, "cap": clamped}], None


_TOOL_HANDLERS: Dict[str, Callable[[Dict[str, Any]], Result]] = {
    "shell": _dispatch_shell,
    "read": _dispatch_read,
    "replace": _dispatch_replace,
    "write": _dispatch_write,
    # Read-only tools (RPC)
    # History (RPC-only, does not go through the clipboard)
    "get_history": _dispatch_get_history,
    "get_history_detail": _dispatch_get_history_detail,
    "clear_history": _dispatch_clear_history,
    "set_history_cap": _dispatch_set_history_cap,
}


# ============ MAIN DISPATCHER ============


def process_payload(payload: Dict[str, Any], *, _internal: bool = False) -> Result:
    """
    Process a runctx payload and return a structured result.
    Returns: (success, data_items, error_message)

    _internal=True when called from the old format convert -> skips the id check.
    """
    try:
        tool = payload.get("tool")

        # New format: tool-based
        if tool in _TOOL_HANDLERS:
            # Validate 'id' (skip during internal convert)
            if not _internal:
                if "id" not in payload:
                    return False, [], "Payload must include an 'id' field"
                if not isinstance(payload["id"], int):
                    return False, [], "Payload 'id' must be an integer"
            return _TOOL_HANDLERS[tool](payload)

        return False, [], "Unknown payload format. Missing 'tool' field."

    except Exception as e:
        return False, [], str(e)
