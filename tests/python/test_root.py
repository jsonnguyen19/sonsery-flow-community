"""Tests for the Root Bar feature: root resolution, roots scan, git_root setter.

Covers:
- runctx/root.py: get_root(kind), normalize_root_kind, set_active_root.
- rpc._resolve_within_root: validates path against a base_root override.

Isolation: monkeypatches state file paths so ~/.config/sonsery is untouched.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from runctx import root as root_module
from runctx import rpc as rpc_module

# ============ Fixtures ============


def _git_init(path: Path, branch: str = "main") -> None:
    """Init a git repo at path with one empty commit."""
    path.mkdir(parents=True, exist_ok=True)
    env = {
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@test",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@test",
    }
    subprocess.run(["git", "init", "-q", "-b", branch], cwd=path, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-q", "-m", "init"],
        cwd=path,
        check=True,
        env={**os.environ, **env},
    )


# `isolated_state` lives in conftest.py (isolates PWD/active-root state
# files from the user's real state).


@pytest.fixture
def workspace(tmp_path, isolated_state):
    """Workspace containing 2 git sub-repos + 1 plain dir + 1 excluded dir."""
    base = tmp_path / "workspace"
    base.mkdir()
    repo_a = base / "repo-a"
    repo_b = base / "repo-b"
    _git_init(repo_a, branch="main")
    _git_init(repo_b, branch="develop")
    (base / "plain-dir").mkdir()
    (base / "node_modules").mkdir()
    (base / "node_modules" / "junk").mkdir()
    # Write pwd file = workspace
    isolated_state["pwd"].write_text(str(base), encoding="utf-8")
    return base


# ============ root.py ============


def test_get_root_base_reads_pwd_file(workspace, isolated_state):
    assert root_module.get_root(root_module.ROOT_BASE) == workspace


def test_get_root_base_falls_back_to_package_root(isolated_state, monkeypatch):
    # pwd file does not exist
    monkeypatch.setattr(root_module, "PWD_FILE", isolated_state["dir"] / "nonexistent")
    assert root_module.get_root(root_module.ROOT_BASE) == root_module.PACKAGE_ROOT


def test_get_root_base_ignores_invalid_content(isolated_state):
    isolated_state["pwd"].write_text("not-absolute-path", encoding="utf-8")
    assert root_module.get_root(root_module.ROOT_BASE) == root_module.PACKAGE_ROOT


def test_get_root_project_no_active(workspace):
    assert root_module.get_root(root_module.ROOT_PROJECT) == workspace


def test_get_root_project_uses_active_inside_base(workspace, isolated_state):
    active = workspace / "repo-a"
    isolated_state["active"].write_text(str(active), encoding="utf-8")
    assert root_module.get_root(root_module.ROOT_PROJECT) == active


def test_get_root_project_ignores_active_outside_base(workspace, isolated_state, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    isolated_state["active"].write_text(str(outside), encoding="utf-8")
    # active lies outside base → fallback to base
    assert root_module.get_root(root_module.ROOT_PROJECT) == workspace


def test_get_root_project_ignores_missing_active(workspace, isolated_state):
    isolated_state["active"].write_text("/does/not/exist/anywhere", encoding="utf-8")
    assert root_module.get_root(root_module.ROOT_PROJECT) == workspace


def test_set_active_root_writes_file(workspace, isolated_state):
    target = workspace / "repo-a"
    root_module.set_active_root(target)
    assert isolated_state["active"].read_text(encoding="utf-8") == str(target)


def test_set_active_root_none_removes_file(workspace, isolated_state):
    isolated_state["active"].write_text("/whatever", encoding="utf-8")
    root_module.set_active_root(None)
    assert not isolated_state["active"].exists()


def test_clear_active_root_missing_ok(isolated_state):
    # no file → must not raise
    root_module.clear_active_root()
    assert not isolated_state["active"].exists()


def test_resolve_within_root_default_uses_project_root(workspace):
    resolved = rpc_module._resolve_within_root("repo-a")
    assert resolved == (workspace / "repo-a").resolve()


def test_resolve_within_root_custom_base(workspace, tmp_path):
    # With a different base_root, the path resolves against that base
    other = tmp_path / "other"
    other.mkdir()
    resolved = rpc_module._resolve_within_root("sub", base_root=other)
    # 'sub' does not exist → resolve still returns an absolute path, is_relative_to passes
    assert resolved == (other / "sub").resolve()


def test_resolve_within_root_rejects_escape_via_base(workspace, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    # '..' is still rejected before resolve
    with pytest.raises(rpc_module.RpcError) as exc:
        rpc_module._resolve_within_root("../x", base_root=other)
    assert "parent traversal" in exc.value.message


def test_resolve_within_root_symlink_escape_rejected(workspace, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = workspace / "evil"
    link.symlink_to(outside)
    with pytest.raises(rpc_module.RpcError) as exc:
        rpc_module._resolve_within_root("evil")
    assert "escapes" in exc.value.message
