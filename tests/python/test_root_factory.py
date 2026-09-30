"""Test root factory: get_root(kind), normalize_root_kind, resolve_tool_path.

Isolation: the `isolated_state` fixture (conftest.py) points PWD_FILE +
ACTIVE_ROOT_FILE into tmp_path so the real ~/.config/sonsery is never used.
"""

from __future__ import annotations

import pytest

from runctx import root as root_module
from runctx import rpc as rpc_module


@pytest.fixture
def workspace(tmp_path, isolated_state):
    base = tmp_path / "workspace"
    base.mkdir()
    (base / "sub").mkdir()
    isolated_state["pwd"].write_text(str(base), encoding="utf-8")
    return base


def test_root_kinds_registered():
    assert set(root_module.ROOT_KINDS) == {"project", "package", "base"}


def test_normalize_root_kind_only_package_selectable():
    assert root_module.normalize_root_kind("package") == "package"
    assert root_module.normalize_root_kind("project") == "project"
    assert root_module.normalize_root_kind(None) == "project"
    assert root_module.normalize_root_kind("weird") == "project"
    # 'base' is an internal root; the client cannot select it.
    assert root_module.normalize_root_kind("base") == "project"


def test_get_root_dispatch_by_kind(workspace, isolated_state):
    active = workspace / "sub"
    isolated_state["active"].write_text(str(active), encoding="utf-8")

    assert root_module.get_root("base") == workspace
    assert root_module.get_root("project") == active
    assert root_module.get_root("package") == root_module.PACKAGE_ROOT


def test_get_root_default_is_project(workspace):
    assert root_module.get_root() == workspace


def test_get_root_unknown_kind_raises(workspace):
    with pytest.raises(ValueError):
        root_module.get_root("nope")


def test_resolve_tool_path_unknown_kind_falls_back_to_project(workspace):
    assert root_module.resolve_tool_path("sub", "nope") == workspace / "sub"


def test_resolve_tool_path_delegates_to_normalize(workspace):
    # 'base' is internal-only → falls back to project (never escapes to base root).
    assert root_module.resolve_tool_path("sub", "base") == workspace / "sub"


def test_resolve_tool_path_uses_factory(workspace):
    assert (
        root_module.resolve_tool_path("prompts", "package") == root_module.PACKAGE_ROOT / "prompts"
    )
    assert root_module.resolve_tool_path("sub", "project") == workspace / "sub"


# ============ Client-khong-chon-duoc 'base' (rpc boundary) ============


def test_rpc_validate_rejects_client_root_base(workspace, isolated_state):
    """A client sending root='base' over rpc must NOT resolve against the base root.

    normalize_root_kind maps 'base' → 'project'. So _validate_params_paths
    must validate the path against the project root (active-root), not the base root.
    Setup: active-root = workspace/sub, base = workspace.
    Send path='./' (valid for both) — only checks it does not crash and goes
    through the non-package branch (i.e. project), never ROOT_BASE.
    """
    active = workspace / "sub"
    isolated_state["active"].write_text(str(active), encoding="utf-8")

    # If the code were wrong (mapping 'base' → base root), path 'sub' would be
    # treated as an escape since base root = workspace and 'sub' lives inside it
    # — no error. This test asserts behavior via a clearer get_root dispatch:
    kind = root_module.normalize_root_kind("base")
    assert kind == root_module.ROOT_PROJECT
    # And rpc._validate_params_paths must not raise with path '.' + root='base'
    rpc_module._validate_params_paths("list", {"path": ".", "root": "base"})


def test_rpc_validate_package_still_boundary_package_root(workspace):
    """root='package' → validate against PACKAGE_ROOT, not the project root."""
    # 'prompts' exists in PACKAGE_ROOT but not in the workspace.
    # If the code were wrong (validating against project root), it would raise an escape error.
    rpc_module._validate_params_paths("list", {"path": "prompts", "root": "package"})
