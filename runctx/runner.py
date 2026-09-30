"""run_runctx: execute runctx_core as subprocess with progress bar.

Preserves behavior (progress bar, temp file, queue).
Only difference: base path points to the project root (containing the
runctx_core.py facade) instead of the package dir, so the CLI contract
is unchanged.

Every stdout line read from the subprocess is appended to the terminal log
ring buffer (after filtering \\r and skipping the progress bar) so the
popup/side panel can display it.
"""

import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Tuple

import yaml

from .platform.clipboard import set_clipboard
from .state import append_log
from .utils import askpass
from .utils.fence import extract_code_fence

# Project root = parent of the `runctx/` package
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_RUNCTX_CORE_FACADE = _PROJECT_ROOT / "runctx_core.py"


def _unlink_quiet(path: str) -> None:
    """Delete a file, ignoring all errors (may already be gone)."""
    try:
        os.unlink(path)
    except OSError:
        pass


def _will_need_tty(payload: str) -> bool:
    """True if the payload runs an auth shell command with no passphrase
    available -> the child runs with a TTY (interactive_tty=True).

    ssh then grabs /dev/tty to prompt directly. The runner progress bar must
    be disabled to avoid overwriting the ssh prompt with \\r (ssh does not go
    through the stdout pipe, so the runner cannot detect it from output).
    """
    try:
        parsed = yaml.safe_load(extract_code_fence(payload))
    except Exception:
        return False
    if not isinstance(parsed, dict):
        return False
    if parsed.get("tool") != "shell":
        return False
    commands = parsed.get("commands")
    if not isinstance(commands, list):
        return False
    if not any(isinstance(c, str) and askpass.is_auth_command(c) for c in commands):
        return False
    # TTY is only needed when no passphrase is available (env/file/keyring).
    return askpass.get_passphrase() is None


def run_runctx(payload: str) -> Tuple[int, str]:
    set_clipboard(payload)

    # When the payload is an auth command with no automatic passphrase, the
    # child runs with a TTY (see shell_runner.run_shell). ssh prompts directly
    # on /dev/tty; the runner progress bar must be disabled to not overlap.
    suppress_progress = _will_need_tty(payload)

    env = os.environ.copy()
    env["LANG"] = "C.UTF-8"
    env["LC_ALL"] = "C.UTF-8"
    env["PYTHONUNBUFFERED"] = "1"

    # Write payload to a temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(payload)
        input_file = f.name

    output_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    output_file.close()

    try:
        # Call the runctx_core facade (project root) as a subprocess
        runctx_core_path = str(_RUNCTX_CORE_FACADE)
        process = subprocess.Popen(
            [sys.executable, runctx_core_path, input_file, output_file.name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            bufsize=1,
        )

        output_chunks: list[str] = []
        started_at = time.time()
        last_update = 0
        bar_length = 30

        # Use a queue to pass output from the reader thread to the main thread
        output_queue: queue.Queue[str] = queue.Queue()

        def read_output() -> None:
            if process.stdout is None:
                return

            for line in process.stdout:
                # Terminal log: split on \\r, append ALL non-empty segments
                # (not just the last) to avoid losing output interleaved with the
                # progress bar. Skip segments matching the progress bar prefix.
                # Known limitation: if the subprocess overwrites the same line via
                # \\r (e.g. progress bar redraw), losing old segments is expected.
                try:
                    segments = [s.strip() for s in line.split("\r")]
                    for seg in segments:
                        if not seg:
                            continue
                        if seg.startswith("running runctx ["):
                            continue
                        append_log(seg)
                except Exception:
                    pass
                output_queue.put(line)

        output_thread = threading.Thread(target=read_output, daemon=True)
        output_thread.start()

        # When suppress_progress: no progress bar (avoid overlapping the ssh
        # passphrase prompt). Only stream output normally.
        if suppress_progress:
            print("running runctx (interactive auth, waiting for input)...", flush=True)

        while process.poll() is None:
            now = time.time()
            elapsed = int(now - started_at)

            # Clear the progress bar line before printing output
            if output_queue.qsize() > 0:
                # Clear the entire line
                print("\r" + " " * 80 + "\r", end="", flush=True)

            # Drain all available lines from the queue
            try:
                while True:
                    line = output_queue.get_nowait()
                    print(line, end="", flush=True)
                    output_chunks.append(line)
            except queue.Empty:
                pass

            # Update progress bar every 0.2s, only when the queue is empty
            # and it is not an auth command (avoid overlapping the ssh prompt).
            if not suppress_progress and now - last_update > 0.2 and output_queue.qsize() == 0:
                # Progress bar: [████████░░░░░░] 10s
                filled = int((elapsed % 60) / 60 * bar_length)
                bar = "█" * filled + "░" * (bar_length - filled)
                print(f"\rrunning runctx [{bar}] {elapsed}s", end="", flush=True)
                last_update = now

            time.sleep(0.05)

        # Clear the progress bar line before final output (skip when suppressed:
        # nothing to clear, and avoid erasing ssh's last prompt line).
        if not suppress_progress:
            print("\r" + " " * 80 + "\r", end="", flush=True)

        # Drain any remaining output
        try:
            while True:
                line = output_queue.get_nowait()
                print(line, end="", flush=True)
                output_chunks.append(line)
        except queue.Empty:
            pass

        output_thread.join(timeout=2)

        elapsed = int(time.time() - started_at)
        print(f"\rrunning runctx done ({elapsed}s, exit={process.returncode}).")
        print()
        append_log(f"running runctx done ({elapsed}s, exit={process.returncode}).")

        # Read output from the output file
        try:
            with open(output_file.name, encoding="utf-8") as f:
                output_content = f.read().strip()
            return process.returncode, output_content
        except Exception as e:
            print(f"ERROR: Failed to read output: {e}")
            return process.returncode, f"ERROR: Failed to read output: {e}"
    finally:
        # Cleanup temp files
        _unlink_quiet(input_file)
        _unlink_quiet(output_file.name)
