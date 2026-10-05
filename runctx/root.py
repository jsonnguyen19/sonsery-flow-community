"""Project root resolution — shared between the backend modules.

Why this exists: previously the logic reading watchctx.pwd + active-root was
copied in two places. If the two drifted apart → security hole (rpc validates against
root X but the tool reads against root Y).

This module is the single source of truth for:
- Paths of the state files (pwd, active-root).
- Logic to read the active root (permissive: no boundary check).
- Root factory: get_root(kind) returns the root for a kind (project/package/base).

Callers should NOT read PWD_FILE / ACTIVE_ROOT_FILE directly and should NOT
if/else on root kind; always use get_root(kind) to keep things consistent.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .constants import (
    ACTIVE_ROOT_FILE,
    PWD_FILE,
    ROOT_PACKAGE,
    ROOT_PROJECT,
    STATE_DIR,
)

# Fallback when watchctx has not yet written the PWD file (e.g. tests, first run).
PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _read_root_file(path: Path) -> Path | None:
    """Read a single absolute-path line from a file. Returns None if missing/empty/invalid."""
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    p = Path(raw)
    if p.is_absolute() and p.is_dir():
        return p
    return None


def _resolve_project() -> Path:
    """Current project root for all file/git/tree/search operations.

    Internal resolver for ROOT_PROJECT. Callers outside this module ALWAYS use
    get_root(ROOT_PROJECT) — do not import this function directly.

    Priority:
    1. active-root (chosen by the user) — honored as-is, no boundary check.
    2. base root (the PWD of watchctx).

    Permissive by design: an active root is returned even when it lies outside
    the base root. Tighten via constants.PATH_BLOCKLIST if needed later.
    """
    base = _read_root_file(PWD_FILE) or PACKAGE_ROOT
    active = _read_root_file(ACTIVE_ROOT_FILE)
    if active is None:
        return base
    return active


def set_active_root(target: Path | None) -> None:
    """Write the active-root file. `None` = reset to base root (delete the file).

    This function does not validate — it only writes/deletes.
    """
    if target is None:
        ACTIVE_ROOT_FILE.unlink(missing_ok=True)
        return
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_ROOT_FILE.write_text(str(target), encoding="utf-8")


def clear_active_root() -> None:
    """Delete the active-root file (used when watchctx exits). Best-effort."""
    try:
        ACTIVE_ROOT_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _resolve_package() -> Path:
    """Root of the tool package itself (where runctx/, prompts/, ... live).

    Internal resolver for ROOT_PACKAGE. Callers outside this module ALWAYS use
    get_root(ROOT_PACKAGE) — do not import this function directly.

    Differs from project root: does NOT depend on watchctx.pwd or active-root.
    Used for resources that belong to the tool itself (e.g. prompts/ templates),
    which must always come from the tool root regardless of where watchctx runs.
    """
    return PACKAGE_ROOT


# ============ ROOT FACTORY ============
# 3 root kinds, one resolver each. Adding a new kind = adding one line here; the
# consumers (rpc, ...) do not need to change any if/else.
#
# - project: watchctx pwd/active-root (default for any read/write/git tool).
# - package: tool root (prompts/ mention @@) — does NOT depend on pwd.
_ROOT_RESOLVERS: dict[str, Callable[[], Path]] = {
    ROOT_PROJECT: _resolve_project,
    ROOT_PACKAGE: _resolve_package,
}
ROOT_KINDS = tuple(_ROOT_RESOLVERS)


def _path_blocklisted(resolved_str: str, pattern: str) -> bool:
    """True if `pattern` matches the resolved path.

    Match rule: substring of the full resolved path string. This is
    deliberately lenient — the blocklist is a coarse safety valve, empty by
    default. Callers documenting a PATH_BLOCKLIST entry should use a
    path-segment-ish substring (e.g. '/etc/' or '.ssh/') to avoid matching an
    unrelated directory whose name merely contains the pattern.
    """
    return pattern in resolved_str


def normalize_root_kind(value: object) -> str:
    """Normalize the client 'root' param → 'package' or 'project'.

    Only 'package' is selectable from the client. Any other value (including
    'base') → 'project' (backward-compat). 'base' is internal-only; the client
    cannot select it.
    """
    return ROOT_PACKAGE if value == ROOT_PACKAGE else ROOT_PROJECT


def get_root(kind: str = ROOT_PROJECT) -> Path:
    """Factory: return the root for a kind. Raises ValueError for an unknown kind."""
    resolver = _ROOT_RESOLVERS.get(kind)
    if resolver is None:
        raise ValueError(f"unknown root kind: {kind!r}")
    return resolver()


def resolve_tool_path(value: str, root_kind: str = ROOT_PROJECT) -> Path:
    """Resolve a user-supplied path permissively (nothing blocked by default).

    Supported formats:
    - Relative: 'src/index.js'    → joined with the root
    - Home:     '~/notes/todo.md' → '~' expanded to the user's home
    - Absolute: '/any/where/x'    → used as-is
    - Parent:   '../sibling/x'    → used as-is (resolved against the root only
                                    when relative)

    root_kind:
    - "project" (default): resolve relative paths against the project root
      (pwd/active-root).
    - "package": resolve relative paths against PACKAGE_ROOT (the tool root),
      NOT tied to pwd. Used for tool resources (e.g. prompts/).
    Any other value → treated as "project".

    By default NOTHING is blocked. To tighten later, add substrings to
    constants.PATH_BLOCKLIST; any resolved path containing one of those
    substrings is rejected. The list is EMPTY today, so the blocking layer is
    a no-op but ready to scale.

    Note on error handling: this function CAN raise OSError from resolve() when
    the path is invalid or permission is denied. Callers already catch
    OSError/Exception and return {success: False, error: ...} to the client →
    no wrapping needed here.
    """
    import os

    from .constants import PATH_BLOCKLIST

    root = get_root(normalize_root_kind(root_kind))

    # Expand '~' so the path points at the real location; other forms pass
    # through untouched.
    expanded = os.path.expanduser(value)
    candidate = Path(expanded)

    # Absolute paths are used as-is; relative paths are joined to the root.
    resolved = candidate if candidate.is_absolute() else root / candidate

    # Opt-in blocklist (empty by default -> no blocking).
    if PATH_BLOCKLIST:
        try:
            resolved_str = str(resolved.resolve())
        except OSError:
            resolved_str = str(resolved)
        for pattern in PATH_BLOCKLIST:
            if pattern and _path_blocklisted(resolved_str, pattern):
                raise ValueError(f"Path '{value}' is blocked by PATH_BLOCKLIST ({pattern})")

    return resolved
