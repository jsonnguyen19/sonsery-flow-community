"""Shared fixtures + sys.path setup for Python core tests."""

import sys
from pathlib import Path

import pytest

# Ensure runctx_core.py and watchctx.py at project root are importable
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_project(tmp_path, monkeypatch):
    """Chdir into tmp_path so all relative paths are safe."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def sample_file(tmp_project):
    """Create a 5-line sample file to test read ranges."""
    p = tmp_project / "sample.txt"
    p.write_text("line1\nline2\nline3\nline4\nline5\n", encoding="utf-8")
    return p


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    """Point all runctx.root state files into tmp_path.

    Includes: watchctx.pwd, watchctx.active-root.
    Ensures tests never read/write the user's real state (~/.config/sonsery).
    """
    from runctx import root as root_module

    pwd_file = tmp_path / "watchctx.pwd"
    active_file = tmp_path / "watchctx.active-root"
    monkeypatch.setattr(root_module, "PWD_FILE", pwd_file)
    monkeypatch.setattr(root_module, "ACTIVE_ROOT_FILE", active_file)
    monkeypatch.setattr(root_module, "STATE_DIR", tmp_path)
    return {
        "pwd": pwd_file,
        "active": active_file,
        "dir": tmp_path,
    }
