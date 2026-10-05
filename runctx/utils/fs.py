"""Filesystem helpers: safe_path, read/write text, read_file_range."""

import os
import sys
from pathlib import Path
from typing import Optional


def safe_path(value: str) -> Path:
    """Resolve a user-supplied path permissively (nothing blocked by default).

    Supported formats:
    - Relative:  'src/index.js'      -> returned as-is (resolved against CWD
                                        by the downstream reader/writer).
    - Home:      '~/notes/todo.md'   -> '~' expanded to the user's home.
    - Absolute:  '/any/where/file'   -> accepted as-is.
    - Parent:    '../sibling/x'      -> accepted (resolved against CWD).

    By default NOTHING is blocked — every path is allowed. To tighten later,
    add substrings to constants.PATH_BLOCKLIST; any resolved path containing
    one of those substrings is then rejected. The list is EMPTY today, so the
    blocking layer is a no-op but ready to scale.

    Raises SystemExit(1) only on invalid input (empty) or a PATH_BLOCKLIST hit
    (CLI contract: callers rely on exit-on-error).
    """
    from ..constants import PATH_BLOCKLIST

    if not isinstance(value, str) or not value:
        print("ERROR: path must be a non-empty string")
        sys.exit(1)

    # Expand '~' so the path points at the real location; other forms pass
    # through untouched. Relative paths stay relative (legacy CWD behavior).
    is_home_ref = value == "~" or value.startswith("~/") or value.startswith("~\\")
    if is_home_ref:
        result = Path(os.path.expanduser(value))
    else:
        result = Path(value)

    # Opt-in blocklist (empty by default -> no blocking). Matching is a plain
    # substring test against the resolved path — see root._path_blocklisted.
    if PATH_BLOCKLIST:
        from ..root import _path_blocklisted

        try:
            resolved_str = str(result.resolve())
        except OSError:
            resolved_str = str(result)
        for pattern in PATH_BLOCKLIST:
            if pattern and _path_blocklisted(resolved_str, pattern):
                print(f"ERROR: path is blocked by PATH_BLOCKLIST ({pattern}): {value}")
                sys.exit(1)

    return result


def read_text(path: Path) -> str:
    """Read file with error handling."""
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    """Write file with directory creation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def read_file_range(path: Path, start: Optional[int], end: Optional[int]) -> str:
    """Read specific line range from file."""
    lines = read_text(path).splitlines()
    start_line = max(1, int(start or 1))
    end_line = min(len(lines), int(end or len(lines)))
    if start_line > end_line:
        return ""
    selected = lines[start_line - 1 : end_line]
    return "\n".join(f"{idx}: {line}" for idx, line in enumerate(selected, start=start_line))
