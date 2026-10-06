"""HTTP bridge server (GET /result, GET /log, POST /result/consume, POST /rpc, POST /shutdown)."""

import json
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .constants import (
    ACTIVE_ROOT_FILE,
    BRIDGE_HOST,
    BRIDGE_PORT,
    BRIDGE_PORT_FILE,
    BRIDGE_PORT_SCAN_RANGE,
    MAX_RPC_REQUEST_BYTES,
    PWD_FILE,
)
from .rpc import handle_rpc_request
from .state import consume_latest_result, get_latest_result_payload, get_log_since

# Actual port the bridge is listening on. Set inside start_bridge_server().
# The watcher and other modules read this variable to print/write the correct port.
active_bridge_port: int = 0


def _read_root_file(path) -> "str | None":
    """Read a root state file (pwd / active-root). Returns None if missing / invalid."""
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return raw or None


def _get_watch_state() -> dict:
    """Snapshot of the watchctx state for the popup header.

    The bridge only runs while watchctx is alive -> `running` is always True here.
    The popup distinguishes alive/dead watchctx by a fetch failure (no response).
    """
    return {
        "success": True,
        "data": {
            "running": True,
            "pwd": _read_root_file(PWD_FILE),
            "active_root": _read_root_file(ACTIVE_ROOT_FILE),
            "bridge_port": active_bridge_port,
        },
        "error": None,
    }


def _cors_headers() -> list:
    """Standard CORS headers for every response."""
    return [
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "*"),
    ]


class BridgeHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self) -> None:
        for key, value in _cors_headers():
            self.send_header(key, value)

    def _send_empty(self, status: int) -> None:
        self.send_response(status)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/log":
            params = parse_qs(parsed.query)
            try:
                since = int(params.get("since", ["0"])[0])
            except (TypeError, ValueError):
                since = 0
            try:
                limit = int(params.get("limit", ["200"])[0])
            except (TypeError, ValueError):
                limit = 200
            # get_log_since clamps to <= 100; clamping here only makes the contract explicit.
            self.send_json(get_log_since(since, limit))
            return

        if path == "/subruns":
            from . import subruns as _subruns

            # Same convention as /rpc: {success, data, error}.
            self.send_json({"success": True, "data": _subruns.list_all(), "error": None})
            return

        if path == "/state":
            self.send_json(_get_watch_state())
            return

        if path.startswith("/result"):
            self.send_json(get_latest_result_payload())
            return

        self._send_empty(404)

    def do_POST(self) -> None:
        if self.path.startswith("/result/consume"):
            consume_latest_result()
            self._send_empty(204)
            return

        if self.path.startswith("/rpc"):
            self._handle_rpc()
            return

        if self.path.startswith("/chat"):
            self._handle_chat()
            return

        if self.path.startswith("/shutdown"):
            self._handle_shutdown()
            return

        self._send_empty(404)

    def _read_json_body(self) -> tuple:
        """Read + parse the JSON body. Returns (payload, None) or (None, error_msg).

        The caller is responsible for sending an error response when payload is None.
        """
        try:
            body = self._read_body()
        except ValueError as exc:
            return None, str(exc)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return None, f"invalid JSON: {exc}"
        if not isinstance(payload, dict):
            return None, "body must be an object"
        return payload, None

    def _handle_chat(self) -> None:
        """POST /chat: store the current conversation id for the next payload.

        Body: {chat_id: "<session id>"} (or {"chat_id": null} to clear).
        The watcher reads it when appending a history row so payloads can be
        grouped/searched per chat.
        """
        payload, err = self._read_json_body()
        if err is not None:
            self.send_json({"success": False, "data": None, "error": err}, status=400)
            return
        from . import history as _history

        chat_id = _history.set_current_chat_id(payload.get("chat_id"))
        self.send_json({"success": True, "data": {"chat_id": chat_id}, "error": None}, status=200)

    def _handle_shutdown(self) -> None:
        """POST /shutdown: reply 204 first, then send SIGTERM to this process.

        A short delay lets the response flush to the client before the process dies.
        """
        self._send_empty(204)

        def _kill() -> None:
            time.sleep(0.1)
            try:
                os.kill(os.getpid(), signal.SIGTERM)
            except Exception:
                # Fallback: hard exit
                os._exit(0)

        threading.Thread(target=_kill, daemon=True).start()

    def _read_body(self) -> bytes:
        """Read the request body with a size limit.

        Raises ValueError if Content-Length is missing/too large.
        """
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except (TypeError, ValueError):
            raise ValueError("invalid Content-Length") from None

        if length <= 0:
            raise ValueError("empty request body")
        if length > MAX_RPC_REQUEST_BYTES:
            raise ValueError(f"request body too large (max {MAX_RPC_REQUEST_BYTES} bytes)")

        return self.rfile.read(length)

    def _handle_rpc(self) -> None:
        """POST /rpc: validate -> dispatch -> return the result immediately.

        Unlike other handlers, /rpc returns {error} (without success/data) on a
        bad request — preserving the old contract.
        """
        request, err = self._read_json_body()
        if err is not None:
            self.send_json({"error": err}, status=400)
            return

        status, response = handle_rpc_request(request)
        self.send_json(response, status=status)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def send_json(self, data: dict, status: int = 200) -> None:
        # No truncation layer here anymore. Previously logic cut the response to
        # fit MAX_RPC_RESPONSE_CHARS, but it caused a bug: an item tree with 1000
        # long entries could not shrink under the threshold -> the bridge
        # returned data: [] (frontend saw "nothing"). The backend already caps
        # counts (MAX_TREE_ENTRIES, MAX_SEARCH_MATCHES), so the response is
        # always bounded.
        body = json.dumps(data, ensure_ascii=False)
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _try_bind(port: int):
    """Try to bind one port. Returns the server or None on failure."""
    try:
        return ThreadingHTTPServer((BRIDGE_HOST, port), BridgeHandler)
    except OSError:
        return None


def _write_port_file(port: int) -> None:
    """Write the listening port to the state file so the extension/CLI can read it."""
    try:
        BRIDGE_PORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        BRIDGE_PORT_FILE.write_text(str(port), encoding="utf-8")
    except OSError:
        pass


def start_bridge_server():
    """Bind the bridge server.

    Tries the fixed port (BRIDGE_PORT) first. If it is taken/blocked (Windows
    WinError 10013 due to a Hyper-V/WSL reserved port range, or another process
    using it), fall back to scanning nearby ports in BRIDGE_PORT_SCAN_RANGE.

    The actual port is written to BRIDGE_PORT_FILE so the extension/CLI can read it.

    Returns the started server, or None if every port fails.
    """
    global active_bridge_port

    tried: list[int] = []

    # Prefer the fixed port
    server = _try_bind(BRIDGE_PORT)
    if server is None:
        tried.append(BRIDGE_PORT)
        # Fallback scan of nearby ports
        for offset in range(1, BRIDGE_PORT_SCAN_RANGE + 1):
            port = BRIDGE_PORT + offset
            server = _try_bind(port)
            if server is not None:
                break
            tried.append(port)

    if server is None:
        print(
            f"WARN: bridge server unavailable on http://{BRIDGE_HOST}:{BRIDGE_PORT} "
            f"(tried ports: {tried})"
        )
        return None

    active_bridge_port = server.server_address[1]
    _write_port_file(active_bridge_port)

    if active_bridge_port != BRIDGE_PORT:
        print(
            f"WARN: port {BRIDGE_PORT} unavailable (tried: {tried}); "
            f"bridge listening on http://{BRIDGE_HOST}:{active_bridge_port}"
        )

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
