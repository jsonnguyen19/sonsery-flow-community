"""Watcher loop, state, runner, clipboard listener and helper tests (all OS).

The watcher `main()` loop is driven end to end with stubs: a scripted clipboard,
a fake runner, a fake bridge server and tmp state files. When the scripted
clipboard runs out it raises KeyboardInterrupt, which is the loop's normal exit.
"""

from __future__ import annotations

import base64
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

import runctx.root as root_mod
import runctx.subruns as subruns_mod
from runctx import runner as runner_mod
from runctx import state as state_mod
from runctx import watcher as watcher_mod
from runctx.platform import clipboard as clipboard_mod
from runctx.utils import hash as hash_mod
from runctx.utils import process as utils_process_mod

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="requires a POSIX host")


def _payload(payload_id: int = 1, command: str = "echo hi") -> str:
    return json.dumps({"id": payload_id, "tool": "shell", "commands": [command]})


def _drain(q: queue.Queue) -> None:
    try:
        while True:
            q.get_nowait()
    except queue.Empty:
        pass


@pytest.fixture(autouse=True)
def _clean_globals():
    _drain(clipboard_mod.clipboard_event_queue)
    yield
    _drain(clipboard_mod.clipboard_event_queue)
    state_mod.consume_latest_result()


@pytest.fixture
def log_buffer(monkeypatch):
    monkeypatch.setattr(state_mod, "_log_buffer", [])
    monkeypatch.setattr(state_mod, "_log_seq", 0)
    return state_mod


# ============================================================
# Watcher loop harness
# ============================================================


class _FakeServer:
    def __init__(self) -> None:
        self.shutdowns = 0

    def shutdown(self) -> None:
        self.shutdowns += 1


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["watchctx"])
    ns = SimpleNamespace(
        script=[],
        published=[],
        runs=[],
        analytics=[],
        history=[],
        subrun_cleanups=[],
        root_clears=[],
        seen_pid=[],
        seen_pwd=[],
        run_result=(0, "line1\nline2"),
        server=_FakeServer(),
        listener=None,
        hash_in=tmp_path / "in.hash",
        hash_out=tmp_path / "out.hash",
        pid=tmp_path / "watchctx.pid",
        pwd=tmp_path / "watchctx.pwd",
    )

    def _get_clipboard() -> str:
        if ns.pid.exists():
            ns.seen_pid.append(ns.pid.read_text(encoding="utf-8"))
        if ns.pwd.exists():
            ns.seen_pwd.append(ns.pwd.read_text(encoding="utf-8"))
        if not ns.script:
            raise KeyboardInterrupt
        item = ns.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    def _run(payload: str):
        ns.runs.append(payload)
        return ns.run_result

    monkeypatch.setattr(watcher_mod, "shutdown_old_watchctx", lambda _pid_file: None)
    monkeypatch.setattr(watcher_mod, "PID_FILE", ns.pid)
    monkeypatch.setattr(watcher_mod, "PWD_FILE", ns.pwd)
    monkeypatch.setattr(watcher_mod, "LAST_INPUT_HASH_FILE", ns.hash_in)
    monkeypatch.setattr(watcher_mod, "LAST_OUTPUT_HASH_FILE", ns.hash_out)
    monkeypatch.setattr(watcher_mod, "BRIDGE_PORT_FILE", tmp_path / "bridge.port")
    monkeypatch.setattr(watcher_mod, "start_bridge_server", lambda: ns.server)
    monkeypatch.setattr(watcher_mod, "start_clipboard_listener", lambda: ns.listener)
    monkeypatch.setattr(watcher_mod, "get_clipboard", _get_clipboard)
    monkeypatch.setattr(watcher_mod, "set_clipboard", ns.published.append)
    monkeypatch.setattr(watcher_mod, "run_runctx", _run)
    monkeypatch.setattr(watcher_mod, "_IDLE_SLEEP", 0)
    monkeypatch.setattr(watcher_mod, "_QUEUE_TIMEOUT", 0.01)
    monkeypatch.setattr(watcher_mod._analytics, "append", lambda **kw: ns.analytics.append(kw))
    monkeypatch.setattr(watcher_mod._history, "append", lambda **kw: ns.history.append(kw))
    monkeypatch.setattr(subruns_mod, "prune_stale", lambda: {"killed": []})
    monkeypatch.setattr(subruns_mod, "cleanup_all", lambda *a, **k: ns.subrun_cleanups.append(1))
    monkeypatch.setattr(root_mod, "clear_active_root", lambda: ns.root_clears.append(1))
    return ns


def _run_watcher() -> None:
    assert watcher_mod.main() == 0


def test_watcher_runs_valid_payload_and_publishes(env):
    payload = _payload(1)
    env.script = ["", payload]
    _run_watcher()
    assert len(env.runs) == 1
    assert json.loads(env.runs[0])["id"] == 1
    assert len(env.published) == 1
    result = json.loads(env.published[0])
    assert result == {"success": True, "data": ["line1", "line2"], "error": None, "id": 1}
    assert state_mod.get_latest_result_payload()["result"] == env.published[0]
    assert hash_mod.read_hash(env.hash_out) == hash_mod.sha(env.published[0])
    assert hash_mod.read_hash(env.hash_in) == hash_mod.sha(payload)
    assert len(env.analytics) == 1
    assert env.analytics[0]["tool"] == "shell"
    assert env.analytics[0]["success"] is True
    assert env.analytics[0]["payload_id"] == 1
    assert len(env.history) == 1
    assert env.history[0]["status"] == "success"
    assert env.history[0]["tool"] == "shell"


def test_watcher_strips_code_fence_before_running(env):
    env.script = ["", "```json\n" + _payload(2) + "\n```"]
    _run_watcher()
    assert len(env.runs) == 1
    assert "```" not in env.runs[0]
    assert json.loads(env.runs[0])["id"] == 2


def test_watcher_ignores_text_without_tool_declaration(env):
    env.script = ["", "just some copied text", "another thing"]
    _run_watcher()
    assert env.runs == []
    assert env.published == []


def test_watcher_same_payload_runs_only_once(env):
    payload = _payload(3)
    env.script = ["", payload, payload, payload]
    _run_watcher()
    assert len(env.runs) == 1
    assert len(env.published) == 1


def test_watcher_different_payloads_each_run(env):
    env.script = ["", _payload(4), _payload(5)]
    _run_watcher()
    assert [json.loads(r)["id"] for r in env.runs] == [4, 5]
    assert len(env.published) == 2


def test_watcher_skips_payload_matching_last_output_hash(env):
    payload = _payload(6)
    hash_mod.write_hash(env.hash_out, hash_mod.sha(payload))
    env.script = ["", payload]
    _run_watcher()
    assert env.runs == []


def test_watcher_does_not_rerun_last_payload_after_restart(env):
    payload = _payload(7)
    hash_mod.write_hash(env.hash_in, hash_mod.sha(payload))
    env.script = [payload]
    _run_watcher()
    assert env.runs == []


def test_watcher_invalid_payload_publishes_error_once(env):
    bad = json.dumps({"tool": "shell", "commands": ["echo hi"]})
    env.script = ["", bad, bad]
    _run_watcher()
    assert env.runs == []
    assert len(env.published) == 1
    result = json.loads(env.published[0])
    assert result["success"] is False
    assert "id" in result["error"]
    assert result["hint"]


def test_watcher_silently_ignores_previous_result_marker(env):
    env.script = ["", 'RUNCTX_RESULT\n{"tool": "shell"}']
    _run_watcher()
    assert env.runs == []
    assert env.published == []


def test_watcher_reports_failed_run(env):
    env.run_result = (1, "boom")
    env.script = ["", _payload(8)]
    _run_watcher()
    result = json.loads(env.published[0])
    assert result["success"] is False
    assert result["error"] == "boom"
    assert result["data"] == []
    assert result["id"] == 8
    assert env.history[0]["status"] == "error"
    assert env.analytics[0]["success"] is False


def test_watcher_survives_analytics_and_history_errors(env, monkeypatch):
    def _boom(**_kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(watcher_mod._analytics, "append", _boom)
    monkeypatch.setattr(watcher_mod._history, "append", _boom)
    env.script = ["", _payload(9), _payload(10)]
    _run_watcher()
    assert len(env.runs) == 2
    assert len(env.published) == 2


def test_watcher_survives_clipboard_errors(env):
    env.script = ["", RuntimeError("clipboard busy"), _payload(11)]
    _run_watcher()
    assert len(env.runs) == 1


def test_watcher_writes_pid_and_pwd_then_cleans_up(env, tmp_path):
    env.script = [""]
    _run_watcher()
    assert env.seen_pid
    assert set(env.seen_pid) == {str(os.getpid())}
    assert env.seen_pwd
    assert set(env.seen_pwd) == {str(Path.cwd())}
    assert not env.pid.exists()
    assert not env.pwd.exists()
    assert env.server.shutdowns == 1
    assert env.subrun_cleanups == [1]
    assert env.root_clears == [1]


class _FakeEventListener:
    def __init__(self) -> None:
        self.polls = 0
        self.terminated = False

    def poll(self):
        self.polls += 1
        return None if self.polls <= 2 else 1

    def terminate(self) -> None:
        self.terminated = True


def test_watcher_event_driven_mode_then_falls_back_to_polling(env):
    env.listener = _FakeEventListener()
    env.script = [""]
    clipboard_mod.clipboard_event_queue.put(_payload(12))
    _run_watcher()
    assert [json.loads(r)["id"] for r in env.runs] == [12]
    assert len(env.published) == 1


# ============================================================
# Watcher pure helpers
# ============================================================


def test_declares_runctx_tool_variants():
    assert watcher_mod._declares_runctx_tool('{"tool": "read", "id": 1}') is True
    assert watcher_mod._declares_runctx_tool('{"tool":"write"}') is True
    assert watcher_mod._declares_runctx_tool("tool: shell\nid: 1") is True
    assert watcher_mod._declares_runctx_tool("hello world") is False
    assert watcher_mod._declares_runctx_tool('{"tool": "git"}') is False


def test_declares_runctx_tool_only_checks_first_lines():
    late = '{\n  "id": 1,\n  "x": 2,\n  "tool": "shell"\n}'
    early = '{\n  "tool": "shell",\n  "id": 1\n}'
    assert watcher_mod._declares_runctx_tool(late) is False
    assert watcher_mod._declares_runctx_tool(early) is True


def test_extract_payload_id():
    assert watcher_mod._extract_payload_id('{"id": 7, "tool": "shell"}') == 7
    assert watcher_mod._extract_payload_id("{{{ not yaml") is None
    assert watcher_mod._extract_payload_id("[1, 2]") is None


def test_build_output_obj_variants():
    out = json.loads(watcher_mod._build_output_obj(True, "[1, 2]", {"id": 5}))
    assert out == {"success": True, "data": [1, 2], "error": None, "id": 5}
    out = json.loads(watcher_mod._build_output_obj(True, '{"a": 1}', None))
    assert out == {"success": True, "data": [{"a": 1}], "error": None}
    out = json.loads(watcher_mod._build_output_obj(True, "", None))
    assert out["data"] == []
    out = json.loads(watcher_mod._build_output_obj(True, "[broken", None))
    assert out["data"] == ["[broken"]
    out = json.loads(watcher_mod._build_output_obj(False, "", {"id": 1}))
    assert out["error"] == "Command failed"
    assert out["id"] == 1


# ============================================================
# state.py: terminal log ring buffer + latest result
# ============================================================


def test_append_log_strips_ansi_and_skips_blank(log_buffer):
    log_buffer.append_log("\x1b[31mred\x1b[0m")
    log_buffer.append_log("   ")
    log_buffer.append_log("")
    log_buffer.append_log("plain\r\n")
    assert log_buffer.get_log_since(0)["lines"] == ["red", "plain"]


def test_append_log_truncates_long_lines(log_buffer):
    log_buffer.append_log("x" * 600)
    line = log_buffer.get_log_since(0)["lines"][0]
    assert len(line) == 500
    assert line.endswith("…")


def test_get_log_since_cursor_semantics(log_buffer):
    for text in ("a", "b", "c"):
        log_buffer.append_log(text)
    first = log_buffer.get_log_since(0)
    assert first["lines"] == ["a", "b", "c"]
    assert first["next"] == 3
    assert first["first_seq"] == 1
    assert first["dropped"] is False
    assert log_buffer.get_log_since(1)["lines"] == ["b", "c"]
    tail = log_buffer.get_log_since(3)
    assert tail["lines"] == []
    assert tail["next"] == 3


def test_get_log_since_limit_is_clamped(log_buffer):
    for i in range(150):
        log_buffer.append_log(f"line{i}")
    assert len(log_buffer.get_log_since(0, limit=1000)["lines"]) == 100
    assert len(log_buffer.get_log_since(0, limit=0)["lines"]) == 1


def test_log_buffer_drops_oldest_lines_over_cap(log_buffer):
    for i in range(2005):
        log_buffer.append_log(f"l{i}")
    assert len(log_buffer._log_buffer) == 2000
    result = log_buffer.get_log_since(0)
    assert result["dropped"] is True
    assert result["first_seq"] == 6
    assert result["lines"][0] == "l5"


def test_log_buffer_char_cap(log_buffer):
    for _ in range(1500):
        log_buffer.append_log("y" * 499)
    total = sum(len(line) + 1 for line in log_buffer._log_buffer)
    assert total <= 500_000
    assert len(log_buffer._log_buffer) == 1000


def test_append_log_is_thread_safe(log_buffer):
    def _worker(tag: int) -> None:
        for i in range(200):
            log_buffer.append_log(f"{tag}-{i}")

    threads = [threading.Thread(target=_worker, args=(t,)) for t in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert log_buffer._log_seq == 800
    assert len(log_buffer._log_buffer) == 800


def test_latest_result_set_get_consume():
    state_mod.set_latest_result("hello")
    got = state_mod.get_latest_result_payload()
    assert got["ok"] is True
    assert got["result"] == "hello"
    assert got["hash"] == hash_mod.sha("hello")
    state_mod.consume_latest_result()
    cleared = state_mod.get_latest_result_payload()
    assert cleared["result"] == ""
    assert cleared["hash"] == ""


# ============================================================
# runner.py
# ============================================================


def test_will_need_tty_auth_command_without_passphrase(monkeypatch):
    monkeypatch.setattr(runner_mod.askpass, "get_passphrase", lambda: None)
    assert runner_mod._will_need_tty(_payload(1, "git push origin main")) is True


def test_will_need_tty_false_when_passphrase_available(monkeypatch):
    monkeypatch.setattr(runner_mod.askpass, "get_passphrase", lambda: "secret")
    assert runner_mod._will_need_tty(_payload(1, "git push origin main")) is False


def test_will_need_tty_false_for_non_auth_or_non_shell(monkeypatch):
    monkeypatch.setattr(runner_mod.askpass, "get_passphrase", lambda: None)
    assert runner_mod._will_need_tty(_payload(1, "ls -la")) is False
    read_payload = json.dumps({"id": 1, "tool": "read", "files": [{"path": "a.txt"}]})
    assert runner_mod._will_need_tty(read_payload) is False
    assert runner_mod._will_need_tty("{{{ not yaml") is False
    assert runner_mod._will_need_tty("[1, 2]") is False


def test_will_need_tty_handles_code_fence(monkeypatch):
    monkeypatch.setattr(runner_mod.askpass, "get_passphrase", lambda: None)
    fenced = "```json\n" + _payload(1, "git pull") + "\n```"
    assert runner_mod._will_need_tty(fenced) is True


def test_run_runctx_end_to_end_shell(monkeypatch, log_buffer):
    monkeypatch.setattr(runner_mod, "set_clipboard", lambda _text: None)
    code, output = runner_mod.run_runctx(_payload(21, "echo runctx-e2e-ok"))
    assert code == 0
    assert "runctx-e2e-ok" in output
    lines = log_buffer.get_log_since(0)["lines"]
    assert any(line.startswith("running runctx done") and "exit=0" in line for line in lines)


def test_run_runctx_reports_per_command_exit_code(monkeypatch, log_buffer):
    monkeypatch.setattr(runner_mod, "set_clipboard", lambda _text: None)
    code, output = runner_mod.run_runctx(_payload(22, "exit 3"))
    # runctx_core runs the whole batch and exits 0; per-command status lives in data.
    assert code == 0
    result = json.loads(output)
    assert result["success"] is True
    assert result["data"][0]["command"] == "exit 3"
    assert result["data"][0]["exit_code"] == 3


def test_run_runctx_copies_payload_to_clipboard(monkeypatch, log_buffer):
    copied: list[str] = []
    monkeypatch.setattr(runner_mod, "set_clipboard", copied.append)
    payload = _payload(23, "echo copied")
    runner_mod.run_runctx(payload)
    assert copied == [payload]


# ============================================================
# Windows clipboard backend (simulated, runs on any OS)
# ============================================================


class _Result:
    def __init__(self, returncode: int = 0, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


def test_windows_get_strips_carriage_returns(monkeypatch):
    monkeypatch.setattr(clipboard_mod.subprocess, "run", lambda *a, **k: _Result(0, "a\r\nb\r\n"))
    assert clipboard_mod._get_clipboard_windows() == "a\nb"


def test_windows_get_failure_returns_empty(monkeypatch):
    monkeypatch.setattr(clipboard_mod.subprocess, "run", lambda *a, **k: _Result(1, "x"))
    assert clipboard_mod._get_clipboard_windows() == ""

    def _raise(*_a, **_k):
        raise FileNotFoundError("powershell.exe")

    monkeypatch.setattr(clipboard_mod.subprocess, "run", _raise)
    assert clipboard_mod._get_clipboard_windows() == ""


def test_windows_set_passes_utf8_base64_via_env(monkeypatch):
    calls: list = []

    def _fake(args, **kwargs):
        calls.append((args, kwargs))
        return _Result(0)

    monkeypatch.setattr(clipboard_mod.subprocess, "run", _fake)
    assert clipboard_mod._set_clipboard_windows("xin chào đại ca ✓") is True
    args, kwargs = calls[0]
    assert args[0] == "powershell.exe"
    assert kwargs["check"] is True
    decoded = base64.b64decode(kwargs["env"]["RUNCTX_CLIP_B64"]).decode("utf-8")
    assert decoded == "xin chào đại ca ✓"


def test_windows_set_failure_returns_false(monkeypatch):
    def _raise(*_a, **_k):
        raise subprocess.CalledProcessError(1, "powershell.exe")

    monkeypatch.setattr(clipboard_mod.subprocess, "run", _raise)
    assert clipboard_mod._set_clipboard_windows("x") is False


# ============================================================
# Windows clipboard listener protocol (simulated, runs on any OS)
# ============================================================


class _FakeListenerProc:
    def __init__(self, lines: list[str]) -> None:
        self.stdout = iter(lines)
        self.stderr = iter([])
        self.terminated = False

    def poll(self):
        return None

    def terminate(self) -> None:
        self.terminated = True


def test_listener_decodes_clipboard_events(monkeypatch):
    text = "line one\nđại ca ✓"
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    proc = _FakeListenerProc(
        [
            "###LISTENER_READY###\n",
            "###CLIP_START###\n",
            encoded[:12] + "\n",
            encoded[12:] + "\n",
            "###CLIP_END###\n",
        ]
    )
    monkeypatch.setattr(clipboard_mod.subprocess, "Popen", lambda *a, **k: proc)
    assert clipboard_mod._start_clipboard_listener_windows() is proc
    assert clipboard_mod.clipboard_event_queue.get(timeout=5) == text


def test_listener_error_before_ready_falls_back_to_polling(monkeypatch):
    proc = _FakeListenerProc(["###LISTENER_ERROR### cannot load forms\n"])
    monkeypatch.setattr(clipboard_mod.subprocess, "Popen", lambda *a, **k: proc)
    assert clipboard_mod._start_clipboard_listener_windows() is None
    assert proc.terminated is True


def test_listener_start_failure_returns_none(monkeypatch):
    def _raise(*_a, **_k):
        raise OSError("no powershell")

    monkeypatch.setattr(clipboard_mod.subprocess, "Popen", _raise)
    assert clipboard_mod._start_clipboard_listener_windows() is None


# ============================================================
# hash helpers + stale watcher shutdown
# ============================================================


def test_hash_helpers_roundtrip(tmp_path):
    assert hash_mod.read_hash(tmp_path / "missing.hash") == ""
    target = tmp_path / "nested" / "dir" / "x.hash"
    hash_mod.write_hash(target, "abc123")
    assert hash_mod.read_hash(target) == "abc123"
    assert hash_mod.sha("xin chào") == hash_mod.sha("xin chào")
    assert hash_mod.sha("a") != hash_mod.sha("b")
    assert len(hash_mod.sha("")) == 64


def test_shutdown_old_without_pid_file_is_noop(tmp_path, monkeypatch):
    called: list[int] = []
    monkeypatch.setattr(utils_process_mod, "shutdown_pid", called.append)
    utils_process_mod.shutdown_old_watchctx(tmp_path / "none.pid")
    assert called == []


def test_shutdown_old_with_garbage_pid_removes_file(tmp_path, monkeypatch):
    pid_file = tmp_path / "w.pid"
    pid_file.write_text("not-a-number", encoding="utf-8")
    called: list[int] = []
    monkeypatch.setattr(utils_process_mod, "shutdown_pid", called.append)
    utils_process_mod.shutdown_old_watchctx(pid_file)
    assert called == []
    assert not pid_file.exists()


def test_shutdown_old_with_dead_pid_does_not_kill(tmp_path, monkeypatch):
    pid_file = tmp_path / "w.pid"
    pid_file.write_text("4321", encoding="utf-8")
    called: list[int] = []
    monkeypatch.setattr(utils_process_mod, "is_pid_alive", lambda _pid: False)
    monkeypatch.setattr(utils_process_mod, "shutdown_pid", called.append)
    utils_process_mod.shutdown_old_watchctx(pid_file)
    assert called == []
    assert not pid_file.exists()


def test_shutdown_old_with_alive_pid_shuts_it_down(tmp_path, monkeypatch):
    pid_file = tmp_path / "w.pid"
    pid_file.write_text("4321", encoding="utf-8")
    called: list[int] = []
    monkeypatch.setattr(utils_process_mod, "is_pid_alive", lambda _pid: True)
    monkeypatch.setattr(utils_process_mod, "shutdown_pid", called.append)
    utils_process_mod.shutdown_old_watchctx(pid_file)
    assert called == [4321]
    assert not pid_file.exists()


@posix_only
def test_real_shutdown_old_watchctx_stops_stale_process(tmp_path):
    proc = subprocess.Popen(["sleep", "30"])
    pid_file = tmp_path / "w.pid"
    pid_file.write_text(str(proc.pid), encoding="utf-8")
    utils_process_mod.shutdown_old_watchctx(pid_file)
    proc.wait(timeout=10)
    assert proc.returncode < 0
    assert not pid_file.exists()
