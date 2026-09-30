#!/usr/bin/env python3
"""
SONSERY RUNCTX CORE ENGINE - FACADE

All logic has been moved into the `runctx` package. This file only
re-exports the old public API (preserved for tests + the extension) and runs
the entry point when invoked directly as a CLI.

- `python3 runctx_core.py <input> <output>` still works as before.
- `import runctx_core as core` still exposes all the old function names.
"""

from runctx.core_main import main
from runctx.dispatcher import process_payload
from runctx.handlers import (
    handle_read,
    handle_replace,
    handle_shell,
    handle_write,
)
from runctx.payload import load_payload
from runctx.shell_runner import run_args, run_shell
from runctx.utils.fence import strip_code_fence
from runctx.utils.fs import (
    read_file_range,
    read_text,
    safe_path,
    write_text,
)
from runctx.utils.output import normalize_output

__all__ = [
    "handle_read",
    "handle_replace",
    "handle_shell",
    "handle_write",
    "load_payload",
    "main",
    "normalize_output",
    "process_payload",
    "read_file_range",
    "read_text",
    "run_args",
    "run_shell",
    "safe_path",
    "strip_code_fence",
    "write_text",
]


if __name__ == "__main__":
    main()
