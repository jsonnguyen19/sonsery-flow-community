"""Tests for safe_path — permissive by default, opt-in blocklist.

By default NOTHING is blocked: relative, '~', absolute, and '..' paths are
all accepted. Blocking is opt-in via constants.PATH_BLOCKLIST (empty today).

Isolation: an autouse fixture points state files into `tmp_path`, ensuring
tests never depend on the user's real state.
"""

from pathlib import Path

import pytest

import runctx_core as core


@pytest.fixture(autouse=True)
def _isolate_state(isolated_state):
    return isolated_state


class TestSafePathPermissive:
    # Every path shape is accepted by default (no blocking).

    def test_relative_path_ok(self):
        # Relative stays relative (legacy behavior: opened against CWD).
        assert core.safe_path("foo/bar.txt") == Path("foo/bar.txt")

    def test_simple_filename_ok(self):
        assert core.safe_path("a.txt") == Path("a.txt")

    def test_absolute_path_ok(self):
        assert core.safe_path("/etc/passwd") == Path("/etc/passwd")

    def test_home_expansion_resolves(self, monkeypatch, tmp_path):
        fake_home = tmp_path / "fake-home"
        fake_home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("HOME", str(fake_home))
        from runctx.utils import fs as fs_module

        resolved = fs_module.safe_path("~/notes.txt")
        assert resolved == fake_home / "notes.txt"

    def test_parent_traversal_ok(self):
        # '..' no longer blocked by default.
        assert core.safe_path("../../etc/passwd") == Path("../../etc/passwd")

    def test_nested_parent_traversal_ok(self):
        assert core.safe_path("foo/../../etc/passwd") == Path("foo/../../etc/passwd")

    def test_dotdot_alone_ok(self):
        assert core.safe_path("..") == Path("..")

    def test_path_with_dotdot_in_name_ok(self):
        assert core.safe_path("..foo") == Path("..foo")

    def test_node_modules_ok(self):
        assert core.safe_path("node_modules/package/index.js") == Path(
            "node_modules/package/index.js"
        )

    def test_vendor_ok(self):
        assert core.safe_path("vendor/lib/file.go") == Path("vendor/lib/file.go")

    def test_git_ok(self):
        assert core.safe_path(".git/config") == Path(".git/config")

    def test_venv_ok(self):
        assert core.safe_path("venv/bin/python") == Path("venv/bin/python")

    def test_deep_normal_path_works(self):
        assert core.safe_path("a/b/c/d/e.txt") == Path("a/b/c/d/e.txt")

    def test_empty_path_rejected(self):
        with pytest.raises(SystemExit):
            core.safe_path("")


class TestSafePathBlocklist:
    """Opt-in blocking: entries in PATH_BLOCKLIST reject matching paths."""

    def test_blocklist_empty_allows_everything(self, monkeypatch):
        from runctx import constants as const
        from runctx.utils import fs as fs_module

        monkeypatch.setattr(const, "PATH_BLOCKLIST", [])
        assert fs_module.safe_path("/etc/passwd") == Path("/etc/passwd")

    def test_blocklist_entry_rejects(self, monkeypatch, tmp_path):
        from runctx import constants as const
        from runctx.utils import fs as fs_module

        # Point HOME to a dir we control, then block a substring inside it.
        fake_home = tmp_path / "home"
        (fake_home / ".ssh").mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setattr(const, "PATH_BLOCKLIST", [".ssh"])

        with pytest.raises(SystemExit):
            fs_module.safe_path("~/.ssh/id_rsa")
