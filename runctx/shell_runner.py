"""Shell execution helpers (cross-platform).

Each spawn may be registered in the subrun registry (if the caller passes
sub_id). Registration is OPTIONAL — omitting sub_id preserves the old behavior
(backward compatible).

Spawns always create a separate process group (POSIX: start_new_session,
Windows: CREATE_NEW_PROCESS_GROUP) so the whole tree can be killed later —
see runctx.platform.system.spawn_kwargs().

On Linux: NVM is sourced only when the command actually needs Node
(npm/pnpm/yarn/node/...). Other commands run directly -> avoid the ~3s NVM
load overhead per run.

See docs/features/subrun-manager.md.
"""

import os
import re
import subprocess
from typing import List, Optional, Tuple

from . import subruns
from .platform import get_pgid, spawn_kwargs
from .platform.shell import build_shell_candidates
from .platform.system import is_windows
from .utils import askpass
from .utils.output import lowercase_first

# Pattern detecting commands that need the Node runtime. If matched -> source NVM.
# Word boundaries prevent false matches (e.g. 'nodemon' would match 'node' without \b).
_NODE_CMD_RE = re.compile(r"\b(npm|pnpm|yarn|npx|node|bun|deno)\b")


def _run_popen(
    args: List[str],
    env=None,
    *,
    sub_id: Optional[str] = None,
    payload_id: Optional[int] = None,
    mode: str = "sequential",
    display_command: Optional[str] = None,
    interactive_tty: bool = False,
) -> Tuple[int, str]:
    """Spawn a subprocess, stream stdout to the console, return (exit_code, output).

    Shared helper for all shell backends (zsh/bash/sh/Windows).

    When `sub_id` is provided (not None), the process is registered in the
    subrun registry so it can be managed/killed externally. Omit -> no
    registration (old behavior).

    `display_command`: the user's original command (without the `source ~/.nvm/...`
    prefix). Used as the registry label for clean UI rendering. Falls back to
    args[-1] if None.

    `interactive_tty=True` (POSIX): does NOT use stdin=DEVNULL and does NOT
    start_new_session -> the child inherits the watcher's controlling terminal,
    so ssh/git can prompt the user for a passphrase like a normal terminal.
    Only used for auth commands when no automatic passphrase is available.
    When enabled, subrun registration is skipped (killpg is unsafe since the
    child shares the watcher's pgid).
    """
    if interactive_tty and not is_windows():
        # Inherit stdin (real TTY) + do not create a new session -> keeps the
        # controlling terminal. ssh then prompts the user directly.
        process = subprocess.Popen(
            args,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=None,
            bufsize=1,
            env=env,
        )
    else:
        process = subprocess.Popen(
            args,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            bufsize=1,
            env=env,
            **spawn_kwargs(),
        )

    # With interactive_tty: skip registration to avoid killpg hitting the
    # watcher's pgid (child did not create its own session).
    if interactive_tty and not is_windows():
        sub_id = None

    # Sub-run registration (optional). Registration errors must not kill the command.
    if sub_id is not None:
        try:
            label = display_command or (args[-1] if args else " ".join(args))
            subruns.register(
                sub_id,
                payload_id=payload_id,
                tool="shell",
                label=label,
                command=label,
                mode=mode,
                pid=process.pid,
                pgid=get_pgid(process.pid),
            )
        except Exception as exc:
            print(f"WARN: subrun register failed for {sub_id}: {exc}")

    chunks = []
    assert process.stdout is not None
    try:
        for line in process.stdout:
            # Console: lowercase the first char for readability.
            # Keep the original `line` in chunks -> do not alter returned data.
            print(lowercase_first(line), end="")
            chunks.append(line)
    finally:
        code = process.wait()
        if sub_id is not None:
            try:
                status = "done" if code == 0 else "error"
                subruns.mark_status(sub_id, status, exit_code=code)
            except Exception as exc:
                print(f"WARN: subrun mark_status failed for {sub_id}: {exc}")

    return code, "".join(chunks)


def run_shell(
    cmd: str,
    *,
    sub_id: Optional[str] = None,
    payload_id: Optional[int] = None,
    mode: str = "sequential",
) -> Tuple[int, str]:
    """Execute a shell command and return (exit_code, output). Cross-platform."""
    env = os.environ.copy()
    env["LANG"] = "C.UTF-8"
    env["LC_ALL"] = "C.UTF-8"
    env["FORCE_COLOR"] = "1"
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"

    # Auth commands (git push/fetch/pull/clone, ssh, scp, sftp):
    # - If the user has an automatic passphrase (env/file/keyring) -> set SSH_ASKPASS
    #   so ssh calls the helper and the command runs unattended.
    # - If NO passphrase is available -> do NOT set SSH_ASKPASS; run the command
    #   with a TTY inherited from the watcher so ssh can prompt the user
    #   directly. Avoids the helper exiting 1 and failing ssh before the user
    #   ever gets a chance to enter a passphrase.
    # Other commands are unaffected -> old behavior preserved.
    interactive_tty = False
    if askpass.is_auth_command(cmd):
        if askpass.get_passphrase():
            askpass.setup_env(env)
        elif not is_windows():
            interactive_tty = True

    # `display_command` = the user's original command, passed down as a clean label.
    common = {
        "sub_id": sub_id,
        "payload_id": payload_id,
        "mode": mode,
        "display_command": cmd,
        "interactive_tty": interactive_tty,
    }

    # Linux - source NVM only when the command needs the Node runtime.
    # Avoids the ~3s NVM load overhead for unrelated commands.
    needs_nvm = bool(_NODE_CMD_RE.search(cmd))

    # Shell argv candidates for the current OS. Windows/macOS: 1 candidate
    # (no fallback — old behavior). Linux: zsh -> bash -> sh.
    candidates = build_shell_candidates(cmd, needs_nvm)

    if len(candidates) == 1:
        # Single candidate: call directly, do not catch FileNotFoundError
        # (old behavior on Windows/macOS).
        return _run_popen(candidates[0], env=env, **common)

    # Multi-candidate (Linux): fall back when a shell is not found.
    for argv in candidates:
        try:
            return _run_popen(argv, env=env, **common)
        except FileNotFoundError:
            continue

    # If all shells fail
    return 127, "No shell found to execute command"


def run_args(
    args: List[str],
    *,
    sub_id: Optional[str] = None,
    payload_id: Optional[int] = None,
    mode: str = "sequential",
) -> Tuple[int, str]:
    """Execute a command with args and return (exit_code, output)."""
    return _run_popen(args, sub_id=sub_id, payload_id=payload_id, mode=mode)
