"""Tests for runctx.max_response (payload `maxResponse` cap)."""

import json
import sys

import pytest

from runctx import core_main
from runctx.max_response import apply_max_response, get_max_response, validate_max_response
from runctx.payload import parse_runctx_payload

SHELL = {"tool": "shell", "maxResponse": 300}


def _lines(count: int, start: int = 1) -> str:
    return "\n".join(f"{i}: line {i}" for i in range(start, start + count))


def _size(value) -> int:
    return len(json.dumps(value, ensure_ascii=False))


def _apply(payload, items):
    """apply_max_response but with a guaranteed non-None items + notice."""
    out, notice = apply_max_response(payload, items)
    assert notice is not None
    return out, notice


class TestValidate:
    @pytest.mark.parametrize("value", [0, -5, "300", 1.5, True, [], {}])
    def test_rejects_invalid(self, value):
        err = validate_max_response({"maxResponse": value})
        assert err is not None and "maxResponse" in err

    def test_accepts_absent_and_positive_int(self):
        assert validate_max_response({}) is None
        assert validate_max_response({"maxResponse": 500}) is None
        assert get_max_response({"maxResponse": 500}) == 500
        assert get_max_response({"maxResponse": True}) == 0
        assert get_max_response(None) == 0


class TestParse:
    def test_rejects_bad_value(self):
        text = json.dumps({"id": 1, "tool": "shell", "maxResponse": 0, "commands": ["ls"]})
        data, err = parse_runctx_payload(text)
        assert data is None
        assert "maxResponse" in err

    def test_accepts_valid_value(self):
        text = json.dumps({"id": 1, "tool": "shell", "maxResponse": 300, "commands": ["ls"]})
        data, err = parse_runctx_payload(text)
        assert err == ""
        assert data is not None
        assert data["maxResponse"] == 300


class TestApply:
    def test_no_limit_is_noop(self):
        items = [{"command": "x", "exit_code": 0, "output": _lines(2000)}]
        assert apply_max_response({"tool": "shell"}, items) == (items, None)

    def test_under_limit_is_noop(self):
        items = [{"command": "x", "exit_code": 0, "output": "ok"}]
        assert apply_max_response(SHELL, items) == (items, None)

    def test_just_under_cap_is_noop(self):
        # Regression: a result whose JSON size is under limit*4 chars must not
        # be cut, even though the reserved headroom makes the trim budget
        # smaller than the cap.
        limit = 600
        body = _lines(150)
        items = [{"command": "find", "exit_code": 0, "output": body}]
        size = _size(items)
        assert limit * 4 - 400 < size <= limit * 4  # inside the old buggy trigger zone
        assert apply_max_response({"tool": "shell", "maxResponse": limit}, items) == (items, None)

    def test_shell_output_is_cut_on_line_boundary(self):
        items = [{"command": "seq", "exit_code": 0, "output": _lines(2000)}]
        out, notice = _apply(SHELL, items)
        meta = out[0]["truncated"]
        assert notice["limit_tokens"] == 300
        assert notice["truncated_items"] == 1
        assert _size(out) <= 300 * 4
        assert meta["shown_lines"] + meta["remaining_lines"] == meta["total_lines"] == 2000
        assert out[0]["output"] == _lines(meta["shown_lines"])
        assert out[0]["exit_code"] == 0
        assert "next_start" not in meta

    def test_read_reports_next_start(self):
        payload = {
            "tool": "read",
            "maxResponse": 300,
            "files": [{"path": "a.txt", "start": 10, "end": 2009}],
        }
        items = [{"path": "a.txt", "success": True, "content": _lines(2000, start=10)}]
        out, _ = _apply(payload, items)
        meta = out[0]["truncated"]
        assert meta["next_start"] == 10 + meta["shown_lines"]
        assert out[0]["path"] == "a.txt"

    def test_budget_is_shared_between_items(self):
        items = [{"path": f"f{i}", "success": True, "content": _lines(1000)} for i in range(3)]
        payload = {
            "tool": "read",
            "maxResponse": 600,
            "files": [{"path": f"f{i}"} for i in range(3)],
        }
        out, notice = _apply(payload, items)
        assert notice["truncated_items"] == 3
        assert all(item["truncated"]["shown_lines"] > 0 for item in out)
        assert _size(out) <= 600 * 4

    def test_small_items_survive(self):
        small = {"command": "pwd", "exit_code": 0, "output": "/tmp"}
        big = {"command": "seq", "exit_code": 0, "output": _lines(2000)}
        out, notice = _apply(SHELL, [small, big])
        assert out[0] == small
        assert "truncated" in out[1]
        assert notice["truncated_items"] == 1

    def test_write_and_replace_never_trimmed(self):
        items = [{"path": "a", "success": True, "message": "m" * 5000}]
        for tool in ("write", "replace"):
            assert apply_max_response({"tool": tool, "maxResponse": 300}, items) == (items, None)

    def test_items_without_text_are_untouched(self):
        items = [{"path": "a", "success": False, "error": "File not found: a" + "!" * 5000}]
        payload = {"tool": "read", "maxResponse": 300}
        assert apply_max_response(payload, items) == (items, None)

    def test_single_huge_line_is_hard_cut(self):
        items = [{"command": "cat min.js", "exit_code": 0, "output": "x" * 10000}]
        out, _ = _apply(SHELL, items)
        meta = out[0]["truncated"]
        assert 0 < len(out[0]["output"]) < 10000
        assert meta["shown_lines"] == 0
        assert meta["remaining_lines"] == 1

    def test_read_hard_cut_omits_next_start(self):
        # A single huge first line must NOT emit next_start: `start + 0` would
        # point back at the same line and loop forever.
        payload = {"tool": "read", "maxResponse": 100, "files": [{"path": "min.js"}]}
        items = [{"path": "min.js", "success": True, "content": "x" * 10000}]
        out, _ = _apply(payload, items)
        meta = out[0]["truncated"]
        assert meta["shown_lines"] == 0
        assert "next_start" not in meta


class TestCoreMain:
    def _run(self, tmp_path, monkeypatch, payload):
        in_file = tmp_path / "in.json"
        out_file = tmp_path / "out.json"
        in_file.write_text(json.dumps(payload), encoding="utf-8")
        big = [{"command": "seq", "exit_code": 0, "output": _lines(2000)}]
        monkeypatch.setattr(core_main, "process_payload", lambda data: (True, big, None))
        monkeypatch.setattr(sys, "argv", ["runctx_core.py", str(in_file), str(out_file)])
        core_main.main()
        return json.loads(out_file.read_text(encoding="utf-8"))

    def test_notice_added_when_cut(self, tmp_path, monkeypatch):
        payload = {"id": 1, "tool": "shell", "maxResponse": 300, "commands": ["seq 1 2000"]}
        result = self._run(tmp_path, monkeypatch, payload)
        assert result["max_response"]["limit_tokens"] == 300
        assert "truncated" in result["data"][0]

    def test_unlimited_without_field(self, tmp_path, monkeypatch):
        payload = {"id": 1, "tool": "shell", "commands": ["seq 1 2000"]}
        result = self._run(tmp_path, monkeypatch, payload)
        assert "max_response" not in result
        assert "truncated" not in result["data"][0]
