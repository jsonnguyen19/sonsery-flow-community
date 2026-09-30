"""Shell invocation builder (cross-platform).

Builds the shell argv + command by OS. Callers (shell_runner) spawn the
subprocess from this argv without checking the OS themselves.

Pattern: public `build_shell_candidates()` = dispatcher, private
`_shell_candidates_<platform>()`.

Fallback behavior:
- Windows / macOS: single candidate, no fallback (old behavior).
- Linux: multiple candidates (zsh -> bash -> sh); caller falls back on FileNotFoundError.

On Linux, NVM is sourced when the command needs the Node runtime
(npm/pnpm/yarn/node/...). Avoids the ~3s NVM load overhead for unrelated commands.
"""

from __future__ import annotations

from .system import current_os


def _shell_candidates_windows(cmd: str, needs_nvm: bool) -> list[list[str]]:
    """Windows: PowerShell, no NVM sourcing needed."""
    return [["powershell.exe", "-NoProfile", "-Command", cmd]]


def _shell_candidates_macos(cmd: str, needs_nvm: bool) -> list[list[str]]:
    """macOS: zsh login (default shell on modern macOS). No NVM."""
    return [["zsh", "-ic", cmd]]


def _shell_candidates_linux(cmd: str, needs_nvm: bool) -> list[list[str]]:
    """Linux: zsh -> bash -> sh. Sources NVM when the command needs Node."""
    if needs_nvm:
        wrapped_zsh = f"source ~/.nvm/nvm.sh && {cmd}"
        wrapped_other = f"source ~/.nvm/nvm.sh 2>/dev/null && {cmd}"
    else:
        wrapped_zsh = cmd
        wrapped_other = cmd
    return [
        ["zsh", "-l", "-c", wrapped_zsh],
        ["bash", "-c", wrapped_other],
        ["sh", "-c", wrapped_other],
    ]


_CANDIDATES_BY_OS = {
    "Windows": _shell_candidates_windows,
    "Darwin": _shell_candidates_macos,
}


def build_shell_candidates(cmd: str, needs_nvm: bool = False) -> list[list[str]]:
    """Return the ordered argv candidates for the current OS.

    Windows/macOS: one entry (caller does not fall back).
    Linux: multiple entries (zsh -> bash -> sh).
    Other OS: falls back to Linux.
    """
    builder = _CANDIDATES_BY_OS.get(current_os(), _shell_candidates_linux)
    return builder(cmd, needs_nvm)
