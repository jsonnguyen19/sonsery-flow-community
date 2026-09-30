"""Tests for safe_path - guards against directory traversal.

Isolation: an autouse fixture points state files into `tmp_path`, ensuring
tests never depend on the user's real state.
"""

from pathlib import Path

import pytest

import runctx_core as core


@pytest.fixture(autouse=True)
def _isolate_state(isolated_state):
    return isolated_state


class TestSafePath:
    def test_relative_path_ok(self):
        assert core.safe_path("foo/bar.txt") == Path("foo/bar.txt")

    def test_simple_filename_ok(self):
        assert core.safe_path("a.txt") == Path("a.txt")

    def test_absolute_path_rejected(self):
        with pytest.raises(SystemExit):
            core.safe_path("/etc/passwd")

    def test_parent_traversal_rejected(self):
        with pytest.raises(SystemExit):
            core.safe_path("../../etc/passwd")

    def test_nested_parent_traversal_rejected(self):
        with pytest.raises(SystemExit):
            core.safe_path("foo/../../etc/passwd")

    def test_dotdot_alone_rejected(self):
        with pytest.raises(SystemExit):
            core.safe_path("..")

    def test_path_with_dotdot_in_name_ok(self):
        # "..foo" is not ".." so it is OK
        assert core.safe_path("..foo") == Path("..foo")

    def test_node_modules_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path("node_modules/package/index.js")

    def test_vendor_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path("vendor/lib/file.go")

    def test_git_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path(".git/config")

    def test_dist_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path("dist/bundle.js")

    def test_build_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path("build/output.bin")

    def test_venv_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path("venv/bin/python")

    def test_dot_venv_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path(".venv/lib/python3.12/site-packages/requests/__init__.py")

    def test_venv_test_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path(".venv-test/lib/python3.12/site-packages/flask/app.py")

    def test_nested_venv_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path("backend/venv/lib/site.py")

    def test_pycache_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path("__pycache__/runctx/core_main.cpython-312.pyc")

    def test_pytest_cache_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path(".pytest_cache/v/cache/nodeids")

    def test_mypy_cache_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path(".mypy_cache/3.12/runctx.core_main.data.json")

    def test_ruff_cache_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path(".ruff_cache/0.6.9/0123abcd.data")

    def test_tox_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path(".tox/py312/lib/site.py")

    def test_htmlcov_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path("htmlcov/index.html")

    def test_nested_node_modules_excluded(self):
        with pytest.raises(SystemExit):
            core.safe_path("src/node_modules/pkg/main.js")

    def test_normal_path_still_works(self):
        assert core.safe_path("src/index.js") == Path("src/index.js")

    def test_deep_normal_path_works(self):
        assert core.safe_path("a/b/c/d/e.txt") == Path("a/b/c/d/e.txt")
