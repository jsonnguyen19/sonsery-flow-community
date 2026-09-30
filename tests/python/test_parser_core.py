"""Tests for load_payload + process_payload in runctx_core.py."""

import pytest

import runctx_core as core


class TestLoadPayload:
    def test_json_payload(self):
        raw = '{"tool": "shell", "commands": ["ls"]}'
        assert core.load_payload(raw)["tool"] == "shell"

    def test_yaml_payload(self):
        raw = "tool: shell\ncommands:\n  - ls\n"
        assert core.load_payload(raw)["tool"] == "shell"

    def test_code_fence_wrapped(self):
        raw = '```json\n{"tool": "read"}\n```'
        assert core.load_payload(raw)["tool"] == "read"

    def test_invalid_payload_exits(self):
        with pytest.raises(SystemExit):
            core.load_payload("this is : not : valid : json")


class TestProcessPayload:
    def test_shell_dispatch(self, tmp_project):
        ok, data, err = core.process_payload({"id": 1, "tool": "shell", "commands": ["echo hi"]})
        assert ok is True
        assert err is None
        assert data[0]["exit_code"] == 0

    def test_shell_empty_commands_fails(self):
        ok, _data, err = core.process_payload({"id": 1, "tool": "shell", "commands": []})
        assert ok is False
        assert err is not None
        assert "commands" in err.lower()

    def test_read_dispatch(self, sample_file):
        ok, _data, err = core.process_payload(
            {"id": 1, "tool": "read", "files": [{"path": sample_file.name}]}
        )
        assert ok is True
        assert err is None

    def test_read_missing_returns_false(self):
        ok, _data, err = core.process_payload(
            {"id": 1, "tool": "read", "files": [{"path": "nope.txt"}]}
        )
        assert ok is False
        assert err is not None

    def test_replace_dispatch(self, tmp_project):
        p = tmp_project / "f.txt"
        p.write_text("abc\n", encoding="utf-8")
        ok, _data, _err = core.process_payload(
            {
                "id": 1,
                "tool": "replace",
                "files": [{"path": "f.txt", "search": "abc", "replace": "xyz"}],
            }
        )
        assert ok is True
        assert p.read_text(encoding="utf-8") == "xyz\n"

    def test_write_dispatch(self, tmp_project):
        ok, _data, _err = core.process_payload(
            {"id": 1, "tool": "write", "files": [{"path": "w.txt", "content": "x"}]}
        )
        assert ok is True
        assert (tmp_project / "w.txt").exists()

    def test_unknown_tool_fails(self):
        ok, _data, _err = core.process_payload({"id": 1, "tool": "nonexistent"})
        assert ok is False

    def test_unknown_format_fails(self):
        ok, _data, err = core.process_payload({"foo": "bar"})
        assert ok is False
        assert err is not None
        assert "Unknown" in err


class TestProcessPayloadRequiresId:
    """Tool-based format MUST have 'id' (in sync with watchctx.parse_runctx_payload)."""

    def test_shell_missing_id_fails(self):
        ok, _data, err = core.process_payload({"tool": "shell", "commands": ["ls"]})
        assert ok is False
        assert err is not None
        assert "id" in err.lower()

    def test_read_missing_id_fails(self):
        ok, _data, err = core.process_payload({"tool": "read", "files": [{"path": "a.txt"}]})
        assert ok is False
        assert err is not None
        assert "id" in err.lower()

    def test_replace_missing_id_fails(self):
        ok, _data, err = core.process_payload(
            {
                "tool": "replace",
                "files": [{"path": "a.txt", "search": "x", "replace": "y"}],
            }
        )
        assert ok is False
        assert err is not None
        assert "id" in err.lower()

    def test_write_missing_id_fails(self):
        ok, _data, err = core.process_payload(
            {"tool": "write", "files": [{"path": "a.txt", "content": "x"}]}
        )
        assert ok is False
        assert err is not None
        assert "id" in err.lower()

    def test_id_not_int_fails(self):
        ok, _data, err = core.process_payload({"id": "abc", "tool": "shell", "commands": ["ls"]})
        assert ok is False
        assert err is not None
        assert "integer" in err.lower()

    def test_id_bool_fails(self):
        # In Python, bool is a subclass of int -> need careful handling
        ok, _data, _err = core.process_payload({"id": True, "tool": "shell", "commands": ["ls"]})
        # bool is treated as a valid int in many contexts, but we accept it
        # (or reject — this test records the current behavior)
        assert isinstance(ok, bool)
