"""Tests for Bridge RPC (POST /rpc): validation, whitelist, path, HTTP contract."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from typing import Any, cast

import pytest

import watchctx


@pytest.fixture(autouse=True)
def _isolate_state(isolated_state):
    """Force every test in this module onto a private state dir.

    Without this, tests would read the developer's real state dir
    (~/.config/sonsery/.state) instead of an isolated tmp_path.
    """
    return isolated_state


@pytest.fixture
def rpc_server():
    """Start the bridge server on a random port, clean up after the test."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), watchctx.BridgeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = cast("tuple[str, int]", server.server_address)
    host, port = address
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()


def _post_json(url: str, obj: Any) -> tuple[int, dict[str, Any]]:
    body = json.dumps(obj).encode("utf-8") if not isinstance(obj, bytes) else obj
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


# ============ UNIT: validation (no server needed) ============


def _rpc(req):
    return watchctx.handle_rpc_request(req)


@pytest.mark.parametrize(
    "label,req,expected_status",
    [
        ("id_not_int", {"id": "x", "tool": "get_history"}, 400),
        ("id_bool", {"id": True, "tool": "get_history"}, 400),
        ("missing_tool", {"id": 1}, 400),
        ("tool_not_str", {"id": 1, "tool": 5}, 400),
        ("params_not_dict", {"id": 1, "tool": "get_history", "params": []}, 400),
        ("params_null", {"id": 1, "tool": "get_history", "params": None}, 200),
        ("params_str", {"id": 1, "tool": "get_history", "params": "x"}, 400),
        ("id_false", {"id": False, "tool": "get_history"}, 400),
        ("params_override_id", {"id": 1, "tool": "get_history", "params": {"id": 2}}, 400),
        ("params_override_tool", {"id": 1, "tool": "get_history", "params": {"tool": "x"}}, 400),
        ("disallowed_shell", {"id": 1, "tool": "shell"}, 403),
        ("disallowed_replace", {"id": 1, "tool": "replace"}, 403),
        ("unknown_tool", {"id": 1, "tool": "nope"}, 403),
    ],
)
def test_validation_status(label, req, expected_status):
    status, _body = _rpc(req)
    assert status == expected_status, f"{label}: got {status}, expected {expected_status}"


def test_valid_request_echoes_id():
    status, body = _rpc({"id": 42, "tool": "get_history", "params": {"action": "status"}})
    assert status == 200
    assert body["id"] == 42
    # tool has no handler at Step 1 -> success=false but the body shape is correct
    assert "success" in body and "data" in body and "error" in body


def test_rpc_tools_excludes_dangerous_tools():
    # Community RPC exposes read + settings/history tools only.
    assert "shell" not in watchctx.RPC_TOOLS
    assert "replace" not in watchctx.RPC_TOOLS
    assert "write" not in watchctx.RPC_TOOLS


def test_http_rpc_valid(rpc_server):
    status, body = _post_json(
        f"{rpc_server}/rpc", {"id": 7, "tool": "get_history", "params": {"action": "status"}}
    )
    assert status == 200
    assert body["id"] == 7


def test_http_rpc_malformed_json(rpc_server):
    status, body = _post_json(f"{rpc_server}/rpc", b"{not json")
    assert status == 400
    assert "error" in body


def test_http_rpc_unknown_tool(rpc_server):
    status, body = _post_json(f"{rpc_server}/rpc", {"id": 1, "tool": "nope"})
    assert status == 403
    assert "error" in body


def test_http_rpc_oversized_body(rpc_server):
    # Body must exceed MAX_RPC_REQUEST_BYTES (currently 10 MB).
    big = json.dumps({"id": 1, "tool": "get_history", "params": {"x": "A" * 11_000_000}}).encode(
        "utf-8"
    )
    # Server rejects early (without reading the whole body) -> client may hit a broken pipe.
    # Either outcome means the request was rejected. A real client must handle it.
    try:
        status, body = _post_json(f"{rpc_server}/rpc", big)
    except urllib.error.URLError:
        return
    assert status == 400
    assert "error" in body


# ============ Regression: legacy endpoints still untouched ============


def test_legacy_result_still_works(rpc_server):
    with urllib.request.urlopen(f"{rpc_server}/result", timeout=5) as r:
        assert r.status == 200
        data = json.loads(r.read().decode("utf-8"))
        assert data["ok"] is True


def test_legacy_consume_still_works(rpc_server):
    req = urllib.request.Request(f"{rpc_server}/result/consume", method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        assert r.status == 204
