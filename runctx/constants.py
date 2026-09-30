"""Shared constants for the runctx package.

Only true constants: global config values used in many places, or tied to
 tool behavior. Module-local variables (e.g. _lock, _cache, a module's own
regex) do NOT belong here.
"""

from __future__ import annotations

from pathlib import Path

# ============ TOOLS ============

RUNCTX_TOOLS = {"shell", "read", "replace", "write"}

# Separate whitelist for Bridge RPC. Do NOT reuse RUNCTX_TOOLS because that
# set includes write/dangerous tools (shell, replace, write). RPC is read-only.
RPC_TOOLS = {
    # Payload history (MVP: list/get/clear + set cap)
    "get_history",
    "get_history_detail",
    "clear_history",
    "set_history_cap",
}

# ============ CONFIG / STATE DIRS ============

CONFIG_DIR_NAME = ".config"
CONFIG_APP_NAME = "sonsery"

CONFIG_DIR = Path.home() / CONFIG_DIR_NAME / CONFIG_APP_NAME
STATE_DIR = CONFIG_DIR / ".state"

# ============ BRIDGE ============

BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 8765
# Extra ports to scan when BRIDGE_PORT is taken/blocked (e.g. Windows reserved
# ranges from Hyper-V/WSL/Docker). The extension scans the same range.
BRIDGE_PORT_SCAN_RANGE = 20

# Bridge RPC limits
# MAX_RPC_REQUEST_BYTES: guards against oversized request bodies (basic defense
# against misbehaving clients), not for optimization.
MAX_RPC_REQUEST_BYTES = 10_000_000  # 10 MB request body
RPC_SUBPROCESS_TIMEOUT = 10  # seconds, for git/search subprocesses

# Timeout (seconds) for clipboard subprocess operations
CLIPBOARD_TIMEOUT = 2

# ============ STATE FILES (shared) ============

# watchctx PWD at startup. Bridge RPC reads this as the project root
# instead of hardcoding the package parent (same as the clipboard flow).
PWD_FILE = STATE_DIR / "watchctx.pwd"

# Active root chosen by the user (must be inside base root).
ACTIVE_ROOT_FILE = STATE_DIR / "watchctx.active-root"

# watchctx process files.
PID_FILE = STATE_DIR / "watchctx.pid"
LAST_INPUT_HASH_FILE = STATE_DIR / "watchctx.last-input.hash"
LAST_OUTPUT_HASH_FILE = STATE_DIR / "watchctx.last-output.hash"

# Actual bridge port (may differ from BRIDGE_PORT if taken).
BRIDGE_PORT_FILE = STATE_DIR / "watchctx.bridge-port"

# ============ WATCHER ============

# Number of leading lines checked to detect a tool declaration (strict check)
TOOL_DECL_PREVIEW_LINES = 3
# Payload preview length printed to console before running
PAYLOAD_PREVIEW_CHARS = 1200
# Wait between poll cycles (seconds)
IDLE_SLEEP = 0.5
# Clipboard event queue timeout (seconds)
QUEUE_TIMEOUT = 0.5

# ============ HISTORY ============

HISTORY_FILE = STATE_DIR / "payload_history.json"
HISTORY_CAP_FILE = STATE_DIR / "watchctx.history-cap"

DEFAULT_CAP = 100
MIN_CAP = 20
MAX_CAP = 1000

# Truncated preview in list view (avoid RPC responses > 100KB).
HISTORY_PREVIEW_CHARS = 300

# Max size for payload/result stored on disk (avoid unbounded growth on
# large payloads). 20KB/field x 100 rows ~ 4MB worst case.
HISTORY_FULL_CHARS = 20_000

# ============ SUBRUNS ============

SUBUNS_FILE = STATE_DIR / "watchctx.subruns.json"
SUBUNS_LOCK_FILE = STATE_DIR / "watchctx.subruns.lock"
SUBUNS_TMP_FILE = STATE_DIR / "watchctx.subruns.json.tmp"

REGISTRY_VERSION = 1

# Grace period before SIGKILL.
KILL_GRACE_SECONDS = 5.0
KILL_POLL_INTERVAL = 0.2
# Max wait after SIGKILL before marking as 'stuck'.
KILL_FINAL_WAIT = 1.0
# Max wait for cleanup_all (used in the watcher finally block).
CLEANUP_TIMEOUT = 10.0

# ============ ROOT KINDS ============

# 3 root kinds, each with a resolver (see runctx/root.py).
# - project: watchctx pwd/active-root (default for read/write/git tools).
# - package: tool root (prompts/ @@ mentions) — independent of pwd.
# - base:    watchctx pwd, ignores active-root.
ROOT_PROJECT = "project"
ROOT_PACKAGE = "package"
ROOT_BASE = "base"
