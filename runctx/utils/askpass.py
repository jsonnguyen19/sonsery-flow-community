"""SSH askpass helper: supplies a passphrase to ssh when there is no TTY.

Problem: the shell tool runs subprocesses with stdin=DEVNULL + start_new_session
(no TTY), so ssh cannot prompt for a passphrase directly. OpenSSH supports the
SSH_ASKPASS mechanism: without a TTY, ssh invokes an external program to fetch
the passphrase. This module provides:

1. Path to the helper script (generated on demand).
2. Helper script: prints the passphrase to stdout when ssh invokes it.
3. Passphrase sources in priority order (per-machine):
   - SONSSH_PASSPHRASE env var
   - ~/.ssh/passphrase file (chmod 600)
   - System keyring (Linux: secret-tool / macOS: security / Windows: None)

OS-specific logic (keyring lookup, helper content, chmod, permission warning)
has been moved down to `runctx.platform.askpass`. This module keeps only the
orchestration + public API (backward-compat).

Public API:
- ensure_helper() -> Path | None    : create the helper if missing, return its path
- get_passphrase() -> str | None    : fetch the passphrase from the available sources
- setup_env(env) -> None            : set SSH_ASKPASS + SSH_ASKPASS_REQUIRE
- is_auth_command(cmd) -> bool      : detect commands that need auth (git push, ssh, ...)
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from ..platform import askpass as _platform_askpass

# ============ CONSTANTS ============

SSH_DIR = Path.home() / ".ssh"
PASSPHRASE_FILE = SSH_DIR / "passphrase"
HELPER_PATH = SSH_DIR / "askpass-helper"

# Regex detecting commands that need interactive auth.
# Only matches real ssh/git-remote commands (not 'git status').
_AUTH_CMD_RE = re.compile(
    r"(?:^|[;&|\n]\s*)"
    r"(?:"
    r"git\s+(?:push|fetch|pull|clone|ls-remote|remote\s+(?:add|set-url|update|show))"
    r"|git\s+submodule\s+(?:update|add)"
    r"|ssh\b"
    r"|scp\b"
    r"|sftp\b"
    r"|rsync\b.*::"
    r")",
    re.IGNORECASE,
)


# ============ DETECT AUTH COMMAND ============


def is_auth_command(cmd: str) -> bool:
    """True if the command may need an SSH passphrase.

    Conservative: only matches 'git push/fetch/pull/clone' or 'ssh/scp/sftp'
    at the start of a segment. 'git status', 'git log', 'git diff' -> False.
    """
    if not cmd or not isinstance(cmd, str):
        return False
    return bool(_AUTH_CMD_RE.search(cmd))


# ============ PASSPHRASE SOURCES ============


def _from_env() -> str | None:
    val = os.environ.get("SONSSH_PASSPHRASE")
    return val if val else None


def _from_file() -> str | None:
    """Read from ~/.ssh/passphrase (first line, stripped).

    Permission warning (POSIX) is delegated to platform.askpass.
    """
    try:
        if not PASSPHRASE_FILE.exists():
            return None
        # File permission warning (POSIX). Windows: no-op.
        _platform_askpass.warn_file_permission(PASSPHRASE_FILE)
        text = PASSPHRASE_FILE.read_text(encoding="utf-8", errors="replace")
        line = text.splitlines()[0] if text.strip() else ""
        return line.strip() or None
    except Exception:
        return None


def get_passphrase() -> str | None:
    """Get passphrase by priority order. None if no source is available."""
    # 1. Env var (highest priority, for CI/custom setups).
    val = _from_env()
    if val:
        return val

    # 2. File ~/.ssh/passphrase.
    val = _from_file()
    if val:
        return val

    # 3. System keyring (OS logic in platform.askpass).
    return _platform_askpass.get_keyring()


# ============ HELPER SCRIPT ============


def ensure_helper() -> Path | None:
    """Create (or update) the helper script. Returns path or None on failure.

    Tied to the current interpreter: if the file exists but points to a
    different python (e.g. venv change), regenerate so the helper always
    calls `runctx.utils.askpass` in the current environment.
    """
    try:
        SSH_DIR.mkdir(parents=True, exist_ok=True)
        desired = _platform_askpass.helper_content()
        if HELPER_PATH.exists():
            try:
                current = HELPER_PATH.read_text(encoding="utf-8", errors="replace")
            except Exception:
                current = ""
            if current == desired:
                return HELPER_PATH
        HELPER_PATH.write_text(desired, encoding="utf-8", newline="\n")
        _platform_askpass.chmod_executable(HELPER_PATH)
        return HELPER_PATH
    except Exception:
        return None


def setup_env(env: dict) -> None:
    """Set SSH_ASKPASS + SSH_ASKPASS_REQUIRE in env (in-place).

    Only set if SSH_ASKPASS is not already present (do not override user config).
    SSH_ASKPASS_REQUIRE=force makes ssh use askpass even with DISPLAY set,
    avoiding attempts to open a nonexistent GUI askpass.
    """
    if env.get("SSH_ASKPASS"):
        return
    helper = ensure_helper()
    if helper is None:
        return
    env["SSH_ASKPASS"] = str(helper)
    env["SSH_ASKPASS_REQUIRE"] = "force"
    # Some ssh versions require a non-empty DISPLAY to enable askpass.
    # On headless Linux, set a fake value to ensure askpass is invoked.
    if not env.get("DISPLAY"):
        env["DISPLAY"] = ":0"


# ============ CLI (invoked by the helper script) ============


def _cli_main() -> int:
    """Entry point when ssh invokes the helper: print passphrase to stdout.

    ssh reads the first stdout line as the passphrase.
    If no passphrase is available -> print a message to stderr and exit 1.
    """
    val = get_passphrase()
    if val:
        print(val)
        return 0
    print(
        "runctx askpass: no passphrase found. Set it up using one of:\n"
        f"  1. chmod 600 va ghi passphrase vao {PASSPHRASE_FILE}\n"
        "  2. secret-tool store --label='github ssh' service ssh key github\n"
        "  3. export SONSSH_PASSPHRASE=<passphrase>\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(_cli_main())
