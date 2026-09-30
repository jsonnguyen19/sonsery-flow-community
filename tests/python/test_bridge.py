"""Test HTTP bridge server (GET /result, POST /result/consume)."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from typing import cast

import pytest

import watchctx


@pytest.fixture
def bridge_server():
    """Start the bridge server on a random port, clean up after the test."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), watchctx.BridgeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    address = cast("tuple[str, int]", server.server_address)
    host, port = address
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()


def _get(url):
    with urllib.request.urlopen(url, timeout=3) as r:
        return r.status, r.read().decode("utf-8"), dict(r.headers)


def _post(url):
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status, r.read().decode("utf-8"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8"), dict(e.headers)


class TestBridgeGetResult:
    def test_get_returns_json(self, bridge_server):
        watchctx.set_latest_result("hello")
        status, body, headers = _get(f"{bridge_server}/result")
        assert status == 200
        assert headers["Content-Type"].startswith("application/json")
        data = json.loads(body)
        assert data["result"] == "hello"
        assert data["ok"] is True
        assert data["hash"]
        watchctx.consume_latest_result()

    def test_cors_header_present(self, bridge_server):
        _status, _body, headers = _get(f"{bridge_server}/result")
        assert headers.get("Access-Control-Allow-Origin") == "*"

    def test_unknown_get_404(self, bridge_server):
        import urllib.error

        try:
            _get(f"{bridge_server}/nope")
            raise AssertionError("Expected 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404


class TestBridgeConsume:
    def test_consume_clears_result(self, bridge_server):
        watchctx.set_latest_result("abc")
        status, _, _ = _post(f"{bridge_server}/result/consume")
        assert status == 204
        _, body, _ = _get(f"{bridge_server}/result")
        data = json.loads(body)
        assert data["result"] == ""
        assert data["hash"] == ""

    def test_consume_unknown_404(self, bridge_server):
        status, _, _ = _post(f"{bridge_server}/nope")
        assert status == 404


class TestBridgeRaceCondition:
    def test_set_get_consume_get(self, bridge_server):
        watchctx.set_latest_result("v1")
        _, body, _ = _get(f"{bridge_server}/result")
        assert json.loads(body)["result"] == "v1"

        _post(f"{bridge_server}/result/consume")

        _, body2, _ = _get(f"{bridge_server}/result")
        assert json.loads(body2)["result"] == ""

    def test_overwrite_result(self, bridge_server):
        watchctx.set_latest_result("first")
        watchctx.set_latest_result("second")
        _, body, _ = _get(f"{bridge_server}/result")
        assert json.loads(body)["result"] == "second"
