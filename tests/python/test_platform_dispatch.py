"""Cross-platform dispatch tests.

Verifies that runctx.platform.* dispatchers pick the RIGHT backend when
`current_os()` reports Darwin / Linux / Windows. These tests run on ANY host
OS (including Windows) because `current_os` / `is_windows` / `is_linux` /
`is_macos` are monkeypatched.

Goal: catch regressions in the dispatch tables of:
- runctx.platform.system     (spawn_kwargs, create_new_process_group_flag, get_pgid)
- runctx.platform.shell      (build_shell_candidates)
- runctx.platform.clipboard  (get_clipboard, set_clipboard backend selection)
- runctx.platform.process    (is_group_alive branch selection)

These tests do NOT execute real platform binaries (pbpaste, xclip, taskkill).
They only assert which private backend function gets called.

IMPORTANT: dispatch tables (`_GET_CLIPBOARD_BY_OS`, `_SET_CLIPBOARD_BY_OS`,
`_CANDIDATES_BY_OS`) are built at import time and hold direct references to the
private backends. Monkeypatching the module attribute alone is NOT enough —
the tests also patch the dict entry so the dispatcher picks up the stub.
"""

from __future__ import annotations

import pytest

from runctx.platform import clipboard as clipboard_mod
from runctx.platform import process as process_mod
from runctx.platform import shell as shell_mod
from runctx.platform import system as system_mod

# ============================================================
# Helpers
# ============================================================


def _force_os(monkeypatch, os_name: str) -> None:
    """Force the OS reported by runctx.platform.system.

    Patches the single source of truth (`current_os`) plus the derived
    predicates so every module that imported them sees the same value.
    """
    monkeypatch.setattr(system_mod, "current_os", lambda: os_name)
    monkeypatch.setattr(system_mod, "is_windows", lambda: os_name == "Windows")
    monkeypatch.setattr(system_mod, "is_linux", lambda: os_name == "Linux")
    monkeypatch.setattr(system_mod, "is_macos", lambda: os_name == "Darwin")

    # Modules that did `from .system import is_windows` etc. hold their own ref.
    monkeypatch.setattr(clipboard_mod, "current_os", lambda: os_name)
    monkeypatch.setattr(clipboard_mod, "is_windows", lambda: os_name == "Windows")

    monkeypatch.setattr(shell_mod, "current_os", lambda: os_name)

    monkeypatch.setattr(process_mod, "is_windows", lambda: os_name == "Windows")
    monkeypatch.setattr(process_mod, "is_linux", lambda: os_name == "Linux")


def _stub_get(monkeypatch, os_name: str, value: str) -> None:
    """Patch both the module attribute AND the dispatch table entry."""
    fn = lambda: value  # noqa: E731
    if os_name == "Darwin":
        monkeypatch.setattr(clipboard_mod, "_get_clipboard_macos", fn)
        monkeypatch.setitem(clipboard_mod._GET_CLIPBOARD_BY_OS, "Darwin", fn)
    elif os_name == "Windows":
        monkeypatch.setattr(clipboard_mod, "_get_clipboard_windows", fn)
        monkeypatch.setitem(clipboard_mod._GET_CLIPBOARD_BY_OS, "Windows", fn)
    else:
        monkeypatch.setattr(clipboard_mod, "_get_clipboard_linux", fn)


def _stub_set(monkeypatch, os_name: str, recorder: dict) -> None:
    """Patch both the module attribute AND the dispatch table entry."""

    def _record(text: str) -> bool:
        recorder[os_name.lower()] = text
        return True

    if os_name == "Darwin":
        monkeypatch.setattr(clipboard_mod, "_set_clipboard_macos", _record)
        monkeypatch.setitem(clipboard_mod._SET_CLIPBOARD_BY_OS, "Darwin", _record)
    elif os_name == "Windows":
        monkeypatch.setattr(clipboard_mod, "_set_clipboard_windows", _record)
        monkeypatch.setitem(clipboard_mod._SET_CLIPBOARD_BY_OS, "Windows", _record)
    else:
        monkeypatch.setattr(clipboard_mod, "_set_clipboard_linux", _record)


# ============================================================
# system.py - spawn_kwargs / create_new_process_group_flag
# ============================================================


def test_spawn_kwargs_windows_uses_creationflags(monkeypatch):
    _force_os(monkeypatch, "Windows")
    kwargs = system_mod.spawn_kwargs()
    assert "creationflags" in kwargs
    assert "start_new_session" not in kwargs


def test_spawn_kwargs_macos_uses_start_new_session(monkeypatch):
    _force_os(monkeypatch, "Darwin")
    assert system_mod.spawn_kwargs() == {"start_new_session": True}


def test_spawn_kwargs_linux_uses_start_new_session(monkeypatch):
    _force_os(monkeypatch, "Linux")
    assert system_mod.spawn_kwargs() == {"start_new_session": True}


def test_spawn_kwargs_unknown_os_falls_back_to_posix(monkeypatch):
    _force_os(monkeypatch, "FreeBSD")
    assert system_mod.spawn_kwargs() == {"start_new_session": True}


def test_create_new_process_group_flag_non_windows_is_zero(monkeypatch):
    for os_name in ("Darwin", "Linux", "FreeBSD"):
        _force_os(monkeypatch, os_name)
        assert system_mod.create_new_process_group_flag() == 0


# ============================================================
# shell.py - build_shell_candidates
# ============================================================


def test_shell_candidates_macos_is_zsh_ic(monkeypatch):
    _force_os(monkeypatch, "Darwin")
    assert shell_mod.build_shell_candidates("echo hi") == [["zsh", "-ic", "echo hi"]]


def test_shell_candidates_windows_is_powershell(monkeypatch):
    _force_os(monkeypatch, "Windows")
    candidates = shell_mod.build_shell_candidates("echo hi")
    assert len(candidates) == 1
    assert candidates[0][0] == "powershell.exe"
    assert "-NoProfile" in candidates[0]
    assert candidates[0][-1] == "echo hi"


def test_shell_candidates_linux_has_fallback_chain(monkeypatch):
    _force_os(monkeypatch, "Linux")
    candidates = shell_mod.build_shell_candidates("echo hi")
    assert [c[0] for c in candidates] == ["zsh", "bash", "sh"]


def test_shell_candidates_linux_sources_nvm_when_needed(monkeypatch):
    _force_os(monkeypatch, "Linux")
    candidates = shell_mod.build_shell_candidates("npm install", needs_nvm=True)
    assert "source ~/.nvm/nvm.sh" in candidates[0][-1]


def test_shell_candidates_linux_skips_nvm_when_not_needed(monkeypatch):
    _force_os(monkeypatch, "Linux")
    candidates = shell_mod.build_shell_candidates("ls -la", needs_nvm=False)
    assert "source ~/.nvm/nvm.sh" not in candidates[0][-1]


def test_shell_candidates_macos_ignores_needs_nvm(monkeypatch):
    """macOS uses zsh login shell -> NVM sourced via ~/.zshrc, no explicit source."""
    _force_os(monkeypatch, "Darwin")
    candidates = shell_mod.build_shell_candidates("npm install", needs_nvm=True)
    assert "source ~/.nvm/nvm.sh" not in candidates[0][-1]


def test_shell_candidates_unknown_os_falls_back_to_linux(monkeypatch):
    _force_os(monkeypatch, "FreeBSD")
    candidates = shell_mod.build_shell_candidates("echo hi")
    assert [c[0] for c in candidates] == ["zsh", "bash", "sh"]


# ============================================================
# clipboard.py - get_clipboard / set_clipboard backend selection
# ============================================================


def test_get_clipboard_macos_calls_pbpaste_backend(monkeypatch):
    _force_os(monkeypatch, "Darwin")
    _stub_get(monkeypatch, "Darwin", "from-macos")
    _stub_get(monkeypatch, "Windows", "from-windows")
    _stub_get(monkeypatch, "Linux", "from-linux")
    assert clipboard_mod.get_clipboard() == "from-macos"


def test_get_clipboard_linux_calls_xclip_backend(monkeypatch):
    _force_os(monkeypatch, "Linux")
    _stub_get(monkeypatch, "Darwin", "from-macos")
    _stub_get(monkeypatch, "Windows", "from-windows")
    _stub_get(monkeypatch, "Linux", "from-linux")
    assert clipboard_mod.get_clipboard() == "from-linux"


def test_get_clipboard_windows_calls_powershell_backend(monkeypatch):
    _force_os(monkeypatch, "Windows")
    _stub_get(monkeypatch, "Darwin", "from-macos")
    _stub_get(monkeypatch, "Windows", "from-windows")
    _stub_get(monkeypatch, "Linux", "from-linux")
    assert clipboard_mod.get_clipboard() == "from-windows"


def test_get_clipboard_unknown_os_falls_back_to_linux(monkeypatch):
    _force_os(monkeypatch, "FreeBSD")
    _stub_get(monkeypatch, "Darwin", "from-macos")
    _stub_get(monkeypatch, "Windows", "from-windows")
    _stub_get(monkeypatch, "Linux", "from-linux")
    assert clipboard_mod.get_clipboard() == "from-linux"


def test_set_clipboard_macos_calls_pbcopy_backend(monkeypatch):
    _force_os(monkeypatch, "Darwin")
    captured: dict = {}
    _stub_set(monkeypatch, "Darwin", captured)
    _stub_set(monkeypatch, "Windows", captured)
    _stub_set(monkeypatch, "Linux", captured)
    clipboard_mod.set_clipboard("hello")
    assert captured == {"darwin": "hello"}


def test_set_clipboard_windows_calls_powershell_backend(monkeypatch):
    _force_os(monkeypatch, "Windows")
    captured: dict = {}
    _stub_set(monkeypatch, "Darwin", captured)
    _stub_set(monkeypatch, "Windows", captured)
    _stub_set(monkeypatch, "Linux", captured)
    clipboard_mod.set_clipboard("hello")
    assert captured == {"windows": "hello"}


def test_set_clipboard_linux_calls_xclip_backend(monkeypatch):
    _force_os(monkeypatch, "Linux")
    captured: dict = {}
    _stub_set(monkeypatch, "Darwin", captured)
    _stub_set(monkeypatch, "Windows", captured)
    _stub_set(monkeypatch, "Linux", captured)
    clipboard_mod.set_clipboard("hello")
    assert captured == {"linux": "hello"}


def test_start_clipboard_listener_macos_returns_none(monkeypatch):
    """Only Windows has the event-driven listener; macOS/Linux -> None (polling)."""
    _force_os(monkeypatch, "Darwin")
    assert clipboard_mod.start_clipboard_listener() is None


def test_start_clipboard_listener_linux_returns_none(monkeypatch):
    _force_os(monkeypatch, "Linux")
    assert clipboard_mod.start_clipboard_listener() is None


# ============================================================
# process.py - is_group_alive branch selection
# ============================================================


def test_is_group_alive_macos_uses_posix_branch(monkeypatch):
    """macOS has no /proc -> must NOT call the Linux branch."""
    _force_os(monkeypatch, "Darwin")
    called = {"linux": 0, "posix": 0, "windows": 0}

    def _linux(p):
        called["linux"] += 1
        return True

    def _posix(p):
        called["posix"] += 1
        return True

    def _windows(p):
        called["windows"] += 1
        return True

    monkeypatch.setattr(process_mod, "_is_group_alive_linux", _linux)
    monkeypatch.setattr(process_mod, "_is_group_alive_posix", _posix)
    monkeypatch.setattr(process_mod, "_is_group_alive_windows", _windows)

    assert process_mod.is_group_alive(1234) is True
    assert called == {"linux": 0, "posix": 1, "windows": 0}


def test_is_group_alive_linux_uses_proc_scan_branch(monkeypatch):
    _force_os(monkeypatch, "Linux")
    called = {"linux": 0, "posix": 0}

    def _linux(p):
        called["linux"] += 1
        return True

    def _posix(p):
        called["posix"] += 1
        return True

    monkeypatch.setattr(process_mod, "_is_group_alive_linux", _linux)
    monkeypatch.setattr(process_mod, "_is_group_alive_posix", _posix)

    assert process_mod.is_group_alive(1234) is True
    assert called == {"linux": 1, "posix": 0}


def test_is_group_alive_windows_uses_pid_branch(monkeypatch):
    _force_os(monkeypatch, "Windows")
    called = {"windows": 0}

    def _windows(p):
        called["windows"] += 1
        return True

    monkeypatch.setattr(process_mod, "_is_group_alive_windows", _windows)

    assert process_mod.is_group_alive(1234) is True
    assert called == {"windows": 1}


def test_is_group_alive_invalid_pgid_returns_false(monkeypatch):
    _force_os(monkeypatch, "Darwin")
    assert process_mod.is_group_alive(0) is False
    assert process_mod.is_group_alive(-1) is False


# ============================================================
# Sanity: dispatch dicts are complete for the 3 supported OSes
# ============================================================


@pytest.mark.parametrize("os_name", ["Windows", "Darwin", "Linux"])
def test_clipboard_dispatch_tables_cover_all_supported_oses(os_name):
    """Windows + Darwin are explicit keys; Linux is the fallback default."""
    if os_name == "Linux":
        assert "Linux" not in clipboard_mod._GET_CLIPBOARD_BY_OS
        return
    assert os_name in clipboard_mod._GET_CLIPBOARD_BY_OS
    assert os_name in clipboard_mod._SET_CLIPBOARD_BY_OS


@pytest.mark.parametrize("os_name", ["Windows", "Darwin", "Linux"])
def test_shell_dispatch_tables_cover_all_supported_oses(os_name):
    """Windows + Darwin are explicit keys; Linux is the fallback default."""
    if os_name == "Linux":
        assert "Linux" not in shell_mod._CANDIDATES_BY_OS
        return
    assert os_name in shell_mod._CANDIDATES_BY_OS
