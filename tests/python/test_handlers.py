"""Tests for handlers: read / replace / write / shell."""

import runctx_core as core


class TestHandleRead:
    def test_read_full_file(self, sample_file):
        results = core.handle_read([{"path": str(sample_file.name)}])
        assert len(results) == 1
        assert results[0]["success"] is True
        assert "line1" in results[0]["content"]

    def test_read_range(self, sample_file):
        results = core.handle_read([{"path": str(sample_file.name), "start": 2, "end": 3}])
        assert results[0]["success"] is True
        assert "2: line2" in results[0]["content"]

    def test_read_missing_file(self):
        results = core.handle_read([{"path": "nope.txt"}])
        assert results[0]["success"] is False
        assert "not found" in results[0]["error"].lower()

    def test_read_multiple_files(self, tmp_project):
        (tmp_project / "a.txt").write_text("AAA", encoding="utf-8")
        (tmp_project / "b.txt").write_text("BBB", encoding="utf-8")
        results = core.handle_read([{"path": "a.txt"}, {"path": "b.txt"}])
        assert len(results) == 2
        assert all(r["success"] for r in results)


class TestHandleReplace:
    def test_replace_single_match_ok(self, tmp_project):
        p = tmp_project / "f.txt"
        p.write_text("hello world\n", encoding="utf-8")
        results = core.handle_replace([{"path": "f.txt", "search": "world", "replace": "there"}])
        assert results[0]["success"] is True
        assert p.read_text(encoding="utf-8") == "hello there\n"

    def test_replace_zero_match_fails(self, tmp_project):
        p = tmp_project / "f.txt"
        p.write_text("hello\n", encoding="utf-8")
        results = core.handle_replace([{"path": "f.txt", "search": "xyz", "replace": "abc"}])
        assert results[0]["success"] is False
        assert "0 times" in results[0]["error"]
        assert p.read_text(encoding="utf-8") == "hello\n"

    def test_replace_multiple_match_fails(self, tmp_project):
        p = tmp_project / "f.txt"
        p.write_text("aa aa aa\n", encoding="utf-8")
        results = core.handle_replace([{"path": "f.txt", "search": "aa", "replace": "bb"}])
        assert results[0]["success"] is False
        assert "3 times" in results[0]["error"]

    def test_replace_missing_file(self):
        results = core.handle_replace([{"path": "nope.txt", "search": "a", "replace": "b"}])
        assert results[0]["success"] is False

    def test_replace_empty_search_matches_many(self, tmp_project):
        p = tmp_project / "f.txt"
        p.write_text("abc\n", encoding="utf-8")
        results = core.handle_replace([{"path": "f.txt", "search": "", "replace": "X"}])
        # empty search matches many times -> must fail
        assert results[0]["success"] is False


class TestHandleWrite:
    def test_write_new_file(self, tmp_project):
        results = core.handle_write([{"path": "new.txt", "content": "hello"}])
        assert results[0]["success"] is True
        assert (tmp_project / "new.txt").read_text(encoding="utf-8") == "hello\n"

    def test_write_overwrites_existing(self, tmp_project):
        p = tmp_project / "f.txt"
        p.write_text("old\n", encoding="utf-8")
        core.handle_write([{"path": "f.txt", "content": "new"}])
        assert p.read_text(encoding="utf-8") == "new\n"

    def test_write_creates_parent_dirs(self, tmp_project):
        core.handle_write([{"path": "a/b/c.txt", "content": "deep"}])
        assert (tmp_project / "a/b/c.txt").read_text(encoding="utf-8") == "deep\n"

    def test_write_empty_content_ok(self, tmp_project):
        results = core.handle_write([{"path": "empty.txt", "content": ""}])
        assert results[0]["success"] is True


class TestHandleShell:
    def test_shell_echo(self):
        results = core.handle_shell(["echo hello_test"])
        assert len(results) == 1
        assert results[0]["exit_code"] == 0
        assert "hello_test" in results[0]["output"]

    def test_shell_nonzero_exit(self):
        results = core.handle_shell(["exit 3"])
        assert results[0]["exit_code"] == 3

    def test_shell_multiple_commands(self):
        results = core.handle_shell(["echo a", "echo b"])
        assert len(results) == 2
        assert "a" in results[0]["output"]
        assert "b" in results[1]["output"]
