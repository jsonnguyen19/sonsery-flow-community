"""Clipboard backend tests (macOS pbcopy/pbpaste, Linux xclip/wl-clipboard).

Two layers:
1. Simulated tests: `subprocess.run` is faked, so they run on ANY host OS and verify
   the exact command, stripping, and error handling of each backend.
2. Real tests: only run on a macOS host (CI macos-latest), they call the real
   pbcopy/pbpaste/zsh to make sure the backends work outside of mocks.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Any

import pytest

from runctx.platform import clipboard as clipboard_mod
from runctx.platform import shell as shell_mod


class _Result:
    def __init__(self, returncode: int = 0, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


def _install_fake_run(monkeypatch, calls: list, behavior) -> None:
    """Replace subprocess.run; `behavior(args, kwargs)` returns a result or raises."""

    def _fake(*args: Any, **kwargs: Any):
        calls.append((args, kwargs))
        return behavior(args, kwargs)

    monkeypatch.setattr(clipboard_mod.subprocess, "run", _fake)


_RUN_ERRORS = [
    FileNotFoundError("missing binary"),
    subprocess.TimeoutExpired("cmd", 1),
    subprocess.CalledProcessError(1, "cmd"),
    OSError("boom"),
]


# ============================================================
# macOS backend (simulated, runs on any OS)
# ============================================================


def test_macos_get_calls_pbpaste_and_strips(monkeypatch):
    calls: list = []
    _install_fake_run(monkeypatch, calls, lambda a, k: _Result(0, "  hello\n"))
    assert clipboard_mod._get_clipboard_macos() == "hello"
    assert calls[0][0][0] == ["pbpaste"]
    assert calls[0][1]["text"] is True
    assert calls[0][1]["capture_output"] is True


def test_macos_get_nonzero_returncode_returns_empty(monkeypatch):
    _install_fake_run(monkeypatch, [], lambda a, k: _Result(1, "ignored"))
    assert clipboard_mod._get_clipboard_macos() == ""


@pytest.mark.parametrize("error", _RUN_ERRORS)
def test_macos_get_swallows_errors(monkeypatch, error):
    def _raise(a, k):
        raise error

    _install_fake_run(monkeypatch, [], _raise)
    assert clipboard_mod._get_clipboard_macos() == ""


def test_macos_set_pipes_text_to_pbcopy(monkeypatch):
    calls: list = []
    _install_fake_run(monkeypatch, calls, lambda a, k: _Result(0))
    assert clipboard_mod._set_clipboard_macos("xin chào") is True
    assert calls[0][0][0] == ["pbcopy"]
    assert calls[0][1]["input"] == "xin chào"
    assert calls[0][1]["check"] is True


@pytest.mark.parametrize("error", _RUN_ERRORS)
def test_macos_set_returns_false_on_errors(monkeypatch, error):
    def _raise(a, k):
        raise error

    _install_fake_run(monkeypatch, [], _raise)
    assert clipboard_mod._set_clipboard_macos("x") is False


# ============================================================
# Linux backend fallback chain (simulated, runs on any OS)
# ============================================================


def test_linux_get_falls_back_to_wl_paste_when_xclip_missing(monkeypatch):
    calls: list = []

    def _behavior(args, kwargs):
        if args[0].startswith("xclip"):
            raise FileNotFoundError("xclip")
        return _Result(0, "from-wayland\n")

    _install_fake_run(monkeypatch, calls, _behavior)
    assert clipboard_mod._get_clipboard_linux() == "from-wayland"
    assert [c[0][0] for c in calls] == ["xclip -selection clipboard -o", "wl-paste"]


def test_linux_get_skips_empty_output_and_tries_next(monkeypatch):
    def _behavior(args, kwargs):
        if args[0].startswith("xclip"):
            return _Result(0, "   \n")
        return _Result(0, "second")

    _install_fake_run(monkeypatch, [], _behavior)
    assert clipboard_mod._get_clipboard_linux() == "second"


def test_linux_get_returns_empty_when_all_backends_fail(monkeypatch):
    _install_fake_run(monkeypatch, [], lambda a, k: _Result(1, ""))
    assert clipboard_mod._get_clipboard_linux() == ""


def test_linux_set_falls_back_to_wl_copy(monkeypatch):
    calls: list = []

    def _behavior(args, kwargs):
        if args[0].startswith("xclip"):
            raise subprocess.CalledProcessError(1, args[0])
        return _Result(0)

    _install_fake_run(monkeypatch, calls, _behavior)
    assert clipboard_mod._set_clipboard_linux("hello") is True
    assert [c[0][0] for c in calls] == ["xclip -selection clipboard", "wl-copy"]
    assert all(c[1]["input"] == "hello" for c in calls)


def test_linux_set_returns_false_when_all_backends_fail(monkeypatch):
    def _raise(a, k):
        raise FileNotFoundError("none")

    _install_fake_run(monkeypatch, [], _raise)
    assert clipboard_mod._set_clipboard_linux("hello") is False


# ============================================================
# Real macOS integration (only on a macOS host, e.g. CI macos-latest)
# ============================================================

_ON_MACOS = sys.platform == "darwin"

needs_macos_clipboard = pytest.mark.skipif(
    not _ON_MACOS or shutil.which("pbcopy") is None or shutil.which("pbpaste") is None,
    reason="requires a real macOS host with pbcopy/pbpaste",
)
needs_macos_zsh = pytest.mark.skipif(
    not _ON_MACOS or shutil.which("zsh") is None,
    reason="requires a real macOS host with zsh",
)


@pytest.fixture
def _restore_macos_clipboard():
    original = clipboard_mod._get_clipboard_macos()
    yield
    if original:
        clipboard_mod._set_clipboard_macos(original)


@needs_macos_clipboard
def test_real_macos_clipboard_roundtrip_ascii(_restore_macos_clipboard):
    text = "runctx-ci-roundtrip-12345"
    assert clipboard_mod._set_clipboard_macos(text) is True
    assert clipboard_mod._get_clipboard_macos() == text


@needs_macos_clipboard
def test_real_macos_clipboard_roundtrip_multiline(_restore_macos_clipboard):
    text = "line1\nline2\n  indented"
    assert clipboard_mod._set_clipboard_macos(text) is True
    assert clipboard_mod._get_clipboard_macos() == text


@needs_macos_clipboard
def test_real_macos_clipboard_roundtrip_unicode(_restore_macos_clipboard):
    text = "xin chào đại ca ✓"
    assert clipboard_mod._set_clipboard_macos(text) is True
    assert clipboard_mod._get_clipboard_macos() == text


@needs_macos_clipboard
def test_real_macos_public_api_roundtrip(_restore_macos_clipboard, monkeypatch):
    monkeypatch.setattr(clipboard_mod, "current_os", lambda: "Darwin")
    clipboard_mod.set_clipboard("public-api-check")
    assert clipboard_mod.get_clipboard() == "public-api-check"


@needs_macos_zsh
def test_real_macos_shell_candidate_runs():
    argv = shell_mod._shell_candidates_macos("echo runctx-shell-ok", needs_nvm=False)[0]
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=60, check=False)
    assert proc.returncode == 0
    assert "runctx-shell-ok" in proc.stdout
