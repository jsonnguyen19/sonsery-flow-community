#!/usr/bin/env python3
"""
WATCHCTX - FACADE

All logic has been moved into the `runctx` package. This file only
re-exports the old public API (preserved for tests + the extension) and runs
the entry point when invoked directly.

- `python3 watchctx.py` still works as before.
- `import watchctx` still exposes all the old names (including the globals
  `latest_result`, `latest_result_hash`, `clipboard_event_queue`).
"""

from pathlib import Path

from runctx.bridge import BridgeHandler, start_bridge_server
from runctx.constants import (
    BRIDGE_HOST,
    BRIDGE_PORT,
    CONFIG_APP_NAME,
    CONFIG_DIR_NAME,
    RPC_TOOLS,
    RUNCTX_TOOLS,
)
from runctx.payload import invalid_result, parse_runctx_payload
from runctx.platform.clipboard import (
    clipboard_event_queue,
    get_clipboard,
    set_clipboard,
    start_clipboard_listener,
)
from runctx.rpc import handle_rpc_request, validate_request_only
from runctx.runner import run_runctx
from runctx.state import (
    consume_latest_result,
    get_latest_result_payload,
    latest_result,
    latest_result_hash,
    latest_result_lock,
    set_latest_result,
)
from runctx.utils.fence import extract_code_fence
from runctx.utils.hash import read_hash, sha, write_hash
from runctx.utils.process import is_process_running, shutdown_old_watchctx
from runctx.watcher import main

__all__ = [
    # constants
    "BRIDGE_HOST",
    "BRIDGE_PORT",
    "CONFIG_APP_NAME",
    "CONFIG_DIR_NAME",
    "RPC_TOOLS",
    "RUNCTX_TOOLS",
    # bridge
    "BridgeHandler",
    "handle_rpc_request",
    "start_bridge_server",
    "validate_request_only",
    # clipboard
    "clipboard_event_queue",
    "get_clipboard",
    "set_clipboard",
    "start_clipboard_listener",
    # payload / fence
    "extract_code_fence",
    "invalid_result",
    "parse_runctx_payload",
    # runner
    "run_runctx",
    # state
    "consume_latest_result",
    "get_latest_result_payload",
    "latest_result",
    "latest_result_hash",
    "latest_result_lock",
    "set_latest_result",
    # utils
    "is_process_running",
    "read_hash",
    "sha",
    "shutdown_old_watchctx",
    "write_hash",
    # watcher
    "main",
    # module-level paths
    "CONFIG_DIR",
    "STATE_DIR",
    "LAST_INPUT_HASH_FILE",
    "LAST_OUTPUT_HASH_FILE",
    "PID_FILE",
    "PWD_FILE",
]


# ==== Backward-compat module-level paths (tests may reference these) ====
CONFIG_DIR = Path.home() / CONFIG_DIR_NAME / CONFIG_APP_NAME
STATE_DIR = CONFIG_DIR / ".state"
LAST_INPUT_HASH_FILE = STATE_DIR / "watchctx.last-input.hash"
LAST_OUTPUT_HASH_FILE = STATE_DIR / "watchctx.last-output.hash"
PID_FILE = STATE_DIR / "watchctx.pid"
PWD_FILE = STATE_DIR / "watchctx.pwd"


if __name__ == "__main__":
    raise SystemExit(main())
