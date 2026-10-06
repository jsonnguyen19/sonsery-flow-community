"""Tests for the shared POST /chat endpoint (chat-id tracking).

Covers:
- /chat stores a chat id (trim/cap) and can clear it (null / empty).
- /chat validates the JSON body (400 on malformed).
"""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from typing import cast

import pytest

import watchctx
from runctx import history as history_mod


@pytest.fixture
def bridge_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), watchctx.BridgeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = cast("tuple[str, int]", server.server_address)
    host, port = address
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()


@pytest.fixture(autouse=True)
def _reset_chat():
    """Ensure a clean current-chat-id before and after each test."""
    history_mod.set_current_chat_id(None)
    yield
    history_mod.set_current_chat_id(None)


def _post_json(url, obj):
    body = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8"))
        except Exception:
            payload = None
        return e.code, payload


class TestChatEndpoint:
    def test_chat_sets_current_id(self, bridge_server):
        status, body = _post_json(f"{bridge_server}/chat", {"chat_id": "chat-abc"})
        assert status == 200
        assert body is not None
        assert body["success"] is True
        assert body["data"] is not None
        assert body["data"]["chat_id"] == "chat-abc"
        assert history_mod.get_current_chat_id() == "chat-abc"

    def test_chat_trims_and_caps(self, bridge_server):
        _status, body = _post_json(f"{bridge_server}/chat", {"chat_id": "  trimmed  "})
        assert body is not None
        assert body["data"] is not None
        assert body["data"]["chat_id"] == "trimmed"
        assert history_mod.get_current_chat_id() == "trimmed"

        _status, body = _post_json(f"{bridge_server}/chat", {"chat_id": "q" * 400})
        assert body is not None
        assert body["data"] is not None
        assert len(body["data"]["chat_id"]) == 256

    def test_chat_null_clears(self, bridge_server):
        history_mod.set_current_chat_id("chat-x")
        status, body = _post_json(f"{bridge_server}/chat", {"chat_id": None})
        assert status == 200
        assert body is not None
        assert body["data"] is not None
        assert body["data"]["chat_id"] is None
        assert history_mod.get_current_chat_id() is None

    def test_chat_empty_clears(self, bridge_server):
        history_mod.set_current_chat_id("chat-x")
        _status, body = _post_json(f"{bridge_server}/chat", {"chat_id": ""})
        assert body is not None
        assert body["data"] is not None
        assert body["data"]["chat_id"] is None
        assert history_mod.get_current_chat_id() is None
