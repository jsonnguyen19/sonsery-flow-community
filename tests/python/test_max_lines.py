"""Tests for runctx.max_lines (payload `maxLines` cap)."""

import json
import sys

import pytest

from runctx import core_main
from runctx.max_lines import apply_max_lines, get_max_lines, validate_max_lines
from runctx.payload import parse_runctx_payload

SHELL = {"tool": "shell", "maxLines": 100}


def _lines(count: int, start: int = 1) -> str:
    return "\n".join(f"{i}: line {i}" for i in range(start, start + count))


def _apply(payload, items):
    """apply_max_lines but with a guaranteed non-None notice."""
    out, notice = apply_max_lines(payload, items)
    assert notice is not None
    return out, notice


class TestValidate:
    @pytest.mark.parametrize("value", [0, -5, "300", 1.5, True, [], {}])
    def test_rejects_invalid(self, value):
        err = validate_max_lines({"maxLines": value})
        assert err is not None and "maxLines" in err

    def test_accepts_absent_and_positive_int(self):
        assert validate_max_lines({}) is None
        assert validate_max_lines({"maxLines": 1500}) is None
        assert get_max_lines({"maxLines": 1500}) == 1500
        assert get_max_lines({"maxLines": True}) == 0
        assert get_max_lines(None) == 0


class TestParse:
    def test_rejects_bad_value(self):
        text = json.dumps({"id": 1, "tool": "shell", "maxLines": 0, "commands": ["ls"]})
        data, err = parse_runctx_payload(text)
        assert data is None
        assert "maxLines" in err

    def test_accepts_valid_value(self):
        text = json.dumps({"id": 1, "tool": "shell", "maxLines": 1500, "commands": ["ls"]})
        data, err = parse_runctx_payload(text)
        assert err == ""
        assert data is not None
        assert data["maxLines"] == 1500


class TestApply:
    def test_no_limit_is_noop(self):
        items = [{"command": "x", "exit_code": 0, "output": _lines(2000)}]
        assert apply_max_lines({"tool": "shell"}, items) == (items, None)

    def test_under_limit_is_noop(self):
        items = [{"command": "x", "exit_code": 0, "output": _lines(50)}]
        assert apply_max_lines(SHELL, items) == (items, None)

    def test_exactly_at_limit_is_noop(self):
        items = [{"command": "x", "exit_code": 0, "output": _lines(100)}]
        assert apply_max_lines(SHELL, items) == (items, None)

    def test_shell_output_is_cut_to_max_lines(self):
        items = [{"command": "seq", "exit_code": 0, "output": _lines(2000)}]
        out, notice = _apply(SHELL, items)
        meta = out[0]["truncated"]
        assert notice["limit_lines"] == 100
        assert notice["total_lines_before"] == 2000
        assert notice["truncated_items"] == 1
        assert meta == {"shown_lines": 100, "total_lines": 2000, "remaining_lines": 1900}
        assert out[0]["output"] == _lines(100)
        assert out[0]["exit_code"] == 0

    def test_read_reports_next_start(self):
        payload = {
            "tool": "read",
            "maxLines": 50,
            "files": [{"path": "a.txt", "start": 10, "end": 2009}],
        }
        items = [{"path": "a.txt", "success": True, "content": _lines(2000, start=10)}]
        out, _ = _apply(payload, items)
        meta = out[0]["truncated"]
        assert meta["shown_lines"] == 50
        assert meta["next_start"] == 60
        assert out[0]["path"] == "a.txt"

    def test_budget_is_shared_between_items(self):
        items = [{"path": f"f{i}", "success": True, "content": _lines(1000)} for i in range(3)]
        payload = {"tool": "read", "maxLines": 300, "files": [{"path": f"f{i}"} for i in range(3)]}
        out, notice = _apply(payload, items)
        assert notice["truncated_items"] == 3
        shown = [item["truncated"]["shown_lines"] for item in out]
        assert all(n > 0 for n in shown)
        assert sum(shown) <= 300

    def test_small_items_free_budget_for_big_ones(self):
        small = {"command": "pwd", "exit_code": 0, "output": "/tmp"}
        big = {"command": "seq", "exit_code": 0, "output": _lines(2000)}
        out, notice = _apply(SHELL, [small, big])
        assert out[0] == small
        assert out[1]["truncated"]["shown_lines"] == 99
        assert notice["truncated_items"] == 1

    def test_write_and_replace_never_trimmed(self):
        items = [{"path": "a", "success": True, "output": _lines(500)}]
        for tool in ("write", "replace"):
            assert apply_max_lines({"tool": tool, "maxLines": 10}, items) == (items, None)

    def test_items_without_text_are_untouched(self):
        items = [{"path": "a", "success": False, "error": "File not found: a" + "!" * 5000}]
        payload = {"tool": "read", "maxLines": 10}
        assert apply_max_lines(payload, items) == (items, None)

    def test_char_cap_cuts_few_very_long_lines(self):
        # 100 lines fit maxLines=100, but 100 x 500 chars blows the char safety cap.
        body = "\n".join("y" * 500 for _ in range(100))
        items = [{"command": "cat bundle", "exit_code": 0, "output": body}]
        out, _ = _apply(SHELL, items)
        meta = out[0]["truncated"]
        assert 0 < meta["shown_lines"] < 100
        assert len(out[0]["output"]) <= 100 * 160

    def test_single_huge_line_is_hard_cut(self):
        items = [{"command": "cat min.js", "exit_code": 0, "output": "x" * 50000}]
        out, _ = _apply(SHELL, items)
        meta = out[0]["truncated"]
        assert len(out[0]["output"]) == 100 * 160
        assert meta["shown_lines"] == 0
        assert meta["remaining_lines"] == 1

    def test_read_hard_cut_omits_next_start(self):
        # next_start would point back at the same line and loop forever.
        payload = {"tool": "read", "maxLines": 100, "files": [{"path": "min.js"}]}
        items = [{"path": "min.js", "success": True, "content": "x" * 50000}]
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
        payload = {"id": 1, "tool": "shell", "maxLines": 100, "commands": ["seq 1 2000"]}
        result = self._run(tmp_path, monkeypatch, payload)
        assert result["max_lines"]["limit_lines"] == 100
        assert "max_response" not in result
        assert "truncated" in result["data"][0]

    def test_unlimited_without_field(self, tmp_path, monkeypatch):
        payload = {"id": 1, "tool": "shell", "commands": ["seq 1 2000"]}
        result = self._run(tmp_path, monkeypatch, payload)
        assert "max_lines" not in result
        assert "truncated" not in result["data"][0]
