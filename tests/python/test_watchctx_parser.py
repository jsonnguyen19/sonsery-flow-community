"""Tests for parse_runctx_payload + extract_code_fence in watchctx.py."""

import json

import watchctx


class TestExtractCodeFence:
    def test_no_fence(self):
        assert watchctx.extract_code_fence("plain") == "plain"

    def test_json_fence(self):
        raw = '```json\n{"id": 1}\n```'
        assert watchctx.extract_code_fence(raw) == '{"id": 1}'

    def test_fence_no_lang(self):
        raw = "```\nhi\n```"
        assert watchctx.extract_code_fence(raw) == "hi"

    def test_empty(self):
        assert watchctx.extract_code_fence("") == ""


class TestParseRunctxPayload:
    def _make(self, **kwargs):
        base = {"id": 123, "tool": "shell", "commands": ["ls"]}
        base.update(kwargs)
        return json.dumps(base)

    def test_valid_shell(self):
        data, err = watchctx.parse_runctx_payload(self._make())
        assert data is not None
        assert err == ""
        assert data["tool"] == "shell"

    def test_missing_id_rejected(self):
        payload = json.dumps({"tool": "shell", "commands": ["ls"]})
        data, err = watchctx.parse_runctx_payload(payload)
        assert data is None
        assert "id" in err.lower()

    def test_id_not_int_rejected(self):
        payload = json.dumps({"id": "abc", "tool": "shell", "commands": ["ls"]})
        data, err = watchctx.parse_runctx_payload(payload)
        assert data is None
        assert "integer" in err.lower()

    def test_unknown_tool_rejected(self):
        payload = json.dumps({"id": 1, "tool": "nope"})
        data, _err = watchctx.parse_runctx_payload(payload)
        assert data is None

    def test_shell_empty_commands_rejected(self):
        payload = json.dumps({"id": 1, "tool": "shell", "commands": []})
        data, _err = watchctx.parse_runctx_payload(payload)
        assert data is None

    def test_shell_multiline_command_rejected(self):
        payload = json.dumps({"id": 1, "tool": "shell", "commands": ["a\nb"]})
        data, err = watchctx.parse_runctx_payload(payload)
        assert data is None
        assert "single-line" in err.lower()

    def test_read_missing_path_rejected(self):
        payload = json.dumps({"id": 1, "tool": "read", "files": [{"start": 1}]})
        data, _err = watchctx.parse_runctx_payload(payload)
        assert data is None

    def test_read_start_after_end_rejected(self):
        payload = json.dumps(
            {
                "id": 1,
                "tool": "read",
                "files": [{"path": "a.txt", "start": 5, "end": 2}],
            }
        )
        data, _err = watchctx.parse_runctx_payload(payload)
        assert data is None

    def test_replace_extra_key_rejected(self):
        payload = json.dumps(
            {
                "id": 1,
                "tool": "replace",
                "files": [{"path": "a", "search": "x", "replace": "y", "extra": 1}],
            }
        )
        data, err = watchctx.parse_runctx_payload(payload)
        assert data is None
        assert "only" in err.lower()

    def test_write_extra_key_rejected(self):
        payload = json.dumps(
            {
                "id": 1,
                "tool": "write",
                "files": [{"path": "a", "content": "x", "extra": 1}],
            }
        )
        data, _err = watchctx.parse_runctx_payload(payload)
        assert data is None

    def test_runctx_result_marker_rejected(self):
        data, err = watchctx.parse_runctx_payload("RUNCTX_RESULT {}")
        assert data is None
        assert "RUNCTX_RESULT" in err

    def test_non_dict_root_rejected(self):
        data, _err = watchctx.parse_runctx_payload("- a\n- b")
        assert data is None

    def test_invalid_yaml_rejected(self):
        data, _err = watchctx.parse_runctx_payload("this : is : not : valid")
        assert data is None

    def test_code_fence_wrapped_ok(self):
        payload = '```json\n{"id": 1, "tool": "shell", "commands": ["ls"]}\n```'
        data, _err = watchctx.parse_runctx_payload(payload)
        assert data is not None


class TestInvalidResult:
    def test_basic(self):
        out = json.loads(watchctx.invalid_result("boom"))
        assert out["success"] is False
        assert out["error"] == "boom"
        assert out["data"] == []

    def test_with_id(self):
        out = json.loads(watchctx.invalid_result("x", payload_id=42))
        assert out["id"] == 42

    def test_with_hint(self):
        out = json.loads(watchctx.invalid_result("x", hint="try again"))
        assert out["hint"] == "try again"
