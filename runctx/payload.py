"""Payload parsing helpers.

Two groups of functions with intentionally different behavior:
- `parse_runctx_payload` (watchctx): strict, returns (data, err).
- `load_payload` (runctx_core): sys.exit on error, returns dict.
- `invalid_result`: build an error JSON.

Uses dict dispatch for per-tool validators (instead of if-else chains).
"""

import json
import sys
from typing import Any, Callable, Dict, Optional, Tuple

import yaml

from .constants import RUNCTX_TOOLS
from .max_lines import validate_max_lines
from .utils.fence import extract_code_fence, strip_code_fence


# ============ ERROR RESULT ============
def invalid_result(reason: str, *, hint: str = "", payload_id=None) -> str:
    error_data = {"success": False, "data": [], "error": reason}

    # Add id if provided
    if payload_id is not None:
        error_data["id"] = payload_id

    # Add hint if provided
    if hint:
        error_data["hint"] = hint

    return json.dumps(error_data, ensure_ascii=False)


# ============ PER-TOOL VALIDATORS ============
# Each validator takes `data` (dict) and returns None (OK) or an error message (str).

Validator = Callable[[Dict[str, Any]], Optional[str]]


def _validate_shell(data: Dict[str, Any]) -> Optional[str]:
    commands = data.get("commands")
    if not isinstance(commands, list) or not commands:
        return "Shell tool must include a non-empty commands array"
    # `mode` is optional. Only 'sequential' (default) or 'parallel' are accepted.
    mode = data.get("mode")
    if mode is not None and mode not in ("sequential", "parallel"):
        return f"Shell 'mode' must be 'sequential' or 'parallel' (got {mode!r})"
    for index, cmd in enumerate(commands):
        if not isinstance(cmd, str) or not cmd.strip():
            return f"Shell command #{index + 1} must be a non-empty string"
        if "\n" in cmd or "\r" in cmd:
            return f"Shell command #{index + 1} must be a single-line command"
    return None


def _validate_read(data: Dict[str, Any]) -> Optional[str]:
    files = data.get("files")
    if not isinstance(files, list) or not files:
        return "Read tool must include a non-empty files array"
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            return f"Read item #{index + 1} must be an object"
        if "path" not in item:
            return f"Read item #{index + 1} must include 'path'"
        if not isinstance(item["path"], str) or not item["path"].strip():
            return f"Read item #{index + 1} 'path' must be a non-empty string"
        if "start" in item and not isinstance(item["start"], int):
            return f"Read item #{index + 1} 'start' must be an integer"
        if "end" in item and not isinstance(item["end"], int):
            return f"Read item #{index + 1} 'end' must be an integer"
        if "start" in item and "end" in item and item["start"] > item["end"]:
            return f"Read item #{index + 1} 'start' must be <= 'end'"
    return None


def _validate_replace(data: Dict[str, Any]) -> Optional[str]:
    files = data.get("files")
    if not isinstance(files, list) or not files:
        return "Replace tool must include a non-empty files array"
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            return f"Replace item #{index + 1} must be an object"
        if set(item.keys()) != {"path", "search", "replace"}:
            return f"Replace item #{index + 1} must contain only path, search, replace"
        if not isinstance(item["path"], str) or not item["path"].strip():
            return f"Replace item #{index + 1} 'path' must be a non-empty string"
        if not isinstance(item["search"], str):
            return f"Replace item #{index + 1} 'search' must be a string"
        if not isinstance(item["replace"], str):
            return f"Replace item #{index + 1} 'replace' must be a string"
    return None


def _validate_write(data: Dict[str, Any]) -> Optional[str]:
    files = data.get("files")
    if not isinstance(files, list) or not files:
        return "Write tool must include a non-empty files array"
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            return f"Write item #{index + 1} must be an object"
        if set(item.keys()) != {"path", "content"}:
            return f"Write item #{index + 1} must contain only path and content"
        if not isinstance(item["path"], str) or not item["path"].strip():
            return f"Write item #{index + 1} 'path' must be a non-empty string"
        if not isinstance(item["content"], str):
            return f"Write item #{index + 1} 'content' must be a string"
    return None


_TOOL_VALIDATORS: Dict[str, Validator] = {
    "shell": _validate_shell,
    "read": _validate_read,
    "replace": _validate_replace,
    "write": _validate_write,
}


# ============ WATCHCTX VARIANT ============
def parse_runctx_payload(text: str) -> Tuple[Optional[Dict], str]:
    payload = extract_code_fence(text)
    if not payload:
        return None, "Clipboard is empty after extracting code fence"

    if payload.startswith("RUNCTX_RESULT"):
        return None, "Clipboard contains a previous RUNCTX_RESULT"

    try:
        data = yaml.safe_load(payload)
    except Exception as exc:
        return None, f"YAML/JSON parse failed: {exc}"

    if not isinstance(data, dict):
        return None, "Payload root must be an object"

    # Check for required id field
    if "id" not in data:
        return None, "Payload must include an 'id' field"
    if not isinstance(data["id"], int):
        return None, "Payload 'id' must be an integer"

    tool = data.get("tool")
    if tool not in RUNCTX_TOOLS:
        return None, f"Unsupported or missing tool: {tool!r}"

    error = _TOOL_VALIDATORS[tool](data) or validate_max_lines(data)
    if error:
        return None, error

    return data, ""


# ============ RUNCTX_CORE VARIANT ============
def load_payload(raw: str) -> Dict[str, Any]:
    """Parse YAML/JSON payload from clipboard."""
    text = strip_code_fence(raw)
    try:
        return yaml.safe_load(text) or {}
    except Exception as yaml_exc:
        try:
            return json.loads(text)
        except Exception:
            print(f"ERROR: Invalid runctx payload: {yaml_exc}")
            sys.exit(1)
