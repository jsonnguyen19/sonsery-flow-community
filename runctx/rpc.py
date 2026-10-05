"""Bridge RPC handler: validate request -> flatten params -> dispatch.

Does not use the clipboard. Does not use state.py. Returns the result immediately.

Separated from bridge.py to allow independent testing and to keep bridge.py thin.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .constants import RPC_TOOLS
from .dispatcher import process_payload
from .root import ROOT_PACKAGE, ROOT_PROJECT, normalize_root_kind
from .root import get_root as _get_root


class RpcError(Exception):
    """RPC error with a clear HTTP status."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


# ============ PATH VALIDATION ============


def _resolve_within_root(value: str, base_root: Optional[Path] = None) -> Path:
    # (base_root is passed by the caller per root_kind: package -> PACKAGE_ROOT)
    """Resolve a path permissively (nothing blocked by default).

    base_root: the root to resolve relative paths against (default =
    the active project root).

    Accepted formats: relative (joined to base_root), '~' (expanded), and
    absolute (used as-is). By default NOTHING is blocked. To tighten later,
    add substrings to constants.PATH_BLOCKLIST; any resolved path containing
    one of those substrings is rejected.

    Returns the resolved ABSOLUTE path so callers use it consistently.

    Differs from safe_path() in utils/fs.py (that one calls sys.exit; not for the server).
    Raises RpcError(400) only on invalid input (empty) or a PATH_BLOCKLIST hit.
    """
    from .constants import PATH_BLOCKLIST

    if not isinstance(value, str) or not value:
        raise RpcError(400, "'path' must be a non-empty string")

    root = base_root if base_root is not None else _get_root(ROOT_PROJECT)
    try:
        root_resolved = root.resolve()
    except OSError as exc:
        raise RpcError(400, f"cannot resolve root: {exc}") from exc

    expanded = os.path.expanduser(value)
    candidate = Path(expanded)
    try:
        resolved = (candidate if candidate.is_absolute() else root_resolved / candidate).resolve()
    except OSError as exc:
        raise RpcError(400, f"cannot resolve path: {exc}") from exc

    # Opt-in blocklist (empty by default -> no blocking). Matching is a plain
    # substring test against the resolved path — see root._path_blocklisted.
    from .root import _path_blocklisted

    for pattern in PATH_BLOCKLIST:
        if pattern and _path_blocklisted(str(resolved), pattern):
            raise RpcError(400, f"path is blocked by PATH_BLOCKLIST ({pattern}): {value}")

    return resolved


def _validate_params_paths(tool: str, params: Dict[str, Any]) -> None:
    """Validate every 'path' field in params, per tool.

    root="package": validate the boundary against PACKAGE_ROOT (the tool root),
    used for tool resources like prompts/. All read tools (read/list/tree/stat/search)
    support this param; git does not (always project).
    """
    # Other tools use the 'path' field — resolved against the active root (default),
    # unless params['root'] == 'package' then resolve against PACKAGE_ROOT.
    if "path" in params:
        kind = normalize_root_kind(params.get("root"))
        if kind == ROOT_PACKAGE:
            _resolve_within_root(params["path"], base_root=_get_root(kind))
        else:
            _resolve_within_root(params["path"])
    # write/replace take a 'files' array: [{path, content|search/replace}].
    # Validate each path in the array against the active root.
    if tool in ("write", "replace"):
        files = params.get("files")
        if not isinstance(files, list):
            raise RpcError(400, "'files' must be an array")
        for idx, item in enumerate(files):
            if not isinstance(item, dict):
                raise RpcError(400, f"files[{idx}] must be an object")
            if "path" not in item:
                raise RpcError(400, f"files[{idx}] missing 'path'")
            _resolve_within_root(item["path"])


# ============ REQUEST VALIDATION ============


def _flatten_request(request: Any) -> Dict[str, Any]:
    """Validate the request, flatten params -> payload for process_payload.

    Payload shape: {id, tool, **params}. params cannot override id/tool.
    Raises RpcError(400) when invalid.
    """
    if not isinstance(request, dict):
        raise RpcError(400, "request must be a JSON object")

    req_id = request.get("id")
    if not isinstance(req_id, int) or isinstance(req_id, bool):
        raise RpcError(400, "'id' must be an integer")

    tool = request.get("tool")
    if not isinstance(tool, str) or not tool:
        raise RpcError(400, "'tool' must be a non-empty string")

    params = request.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise RpcError(400, "'params' must be an object")

    # params cannot override id/tool
    if "id" in params:
        raise RpcError(400, "'params' must not contain 'id'")
    if "tool" in params:
        raise RpcError(400, "'params' must not contain 'tool'")

    # Whitelist check
    if tool not in RPC_TOOLS:
        # Distinguish unknown vs disallowed (write tool) when possible
        raise RpcError(403, f"tool not allowed over RPC: {tool}")

    # Path validation per tool
    try:
        _validate_params_paths(tool, params)
    except RpcError:
        raise
    except Exception as exc:
        raise RpcError(400, f"invalid params: {exc}") from exc

    payload: Dict[str, Any] = {"id": req_id, "tool": tool}
    payload.update(params)
    return payload


# ============ MAIN ENTRY ============


def handle_rpc_request(request: Any) -> Tuple[int, Dict[str, Any]]:
    """Entry for bridge.py.

    Returns (http_status, body_dict).
    - 400: malformed / override / invalid path
    - 403: tool not in the whitelist
    - 200: success or the tool failed (success=false)
    """
    try:
        payload = _flatten_request(request)
    except RpcError as exc:
        return exc.status, {"error": exc.message}
    except Exception as exc:
        return 400, {"error": f"invalid request: {exc}"}

    req_id = payload.get("id")

    try:
        success, data, error = process_payload(payload)
    except Exception as exc:
        return 200, {
            "id": req_id,
            "success": False,
            "data": [],
            "error": str(exc),
        }

    return 200, {
        "id": req_id,
        "success": success,
        "data": data,
        "error": error,
    }


def validate_request_only(request: Any) -> Optional[str]:
    """Test helper: return an error message or None when the request is valid."""
    try:
        _flatten_request(request)
        return None
    except RpcError as exc:
        return exc.message
    except Exception as exc:
        return str(exc)
