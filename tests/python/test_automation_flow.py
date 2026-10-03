"""Automation flow tests (shell runner, process groups, locks, keyring) for macOS/POSIX.

Layers:
1. Simulated: Popen/subprocess are faked, so they run on ANY host OS and pin the exact
   behavior of the automation flow (argv, env, tty/session handling, keyring command).
2. Real POSIX: spawn real processes (Linux + macOS runners); skipped on Windows.
3. Real macOS: only on a darwin host (CI macos-latest).
"""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Any

import pytest

from runctx import shell_runner
from runctx.platform import askpass as askpass_mod
from runctx.platform import lock as lock_mod
from runctx.platform import process as process_mod
from runctx.platform import shell as shell_mod
from runctx.platform import system as system_mod

_POSIX = sys.platform != "win32"
_DARWIN = sys.platform == "darwin"

posix_only = pytest.mark.skipif(not _POSIX, reason="requires a POSIX host")
macos_only = pytest.mark.skipif(not _DARWIN, reason="requires a real macOS host")


class _FakeProc:
    def __init__(self, code: int = 0) -> None:
        self.stdout = iter(["ok\n"])
        self.pid = 4242
        self._code = code

    def wait(self) -> int:
        return self._code


class _Result:
    def __init__(self, returncode: int = 0, stdout: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout


def _install_fake_popen(monkeypatch, calls: list, code: int = 0) -> None:
    def _fake(args: Any, **kwargs: Any) -> _FakeProc:
        calls.append((args, kwargs))
        return _FakeProc(code)

    monkeypatch.setattr(shell_runner.subprocess, "Popen", _fake)


def _wait_until(predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


# ============================================================
# Simulated: shell runner flow as seen on macOS
# ============================================================


def test_run_shell_macos_flow_argv_and_env(monkeypatch):
    calls: list = []
    _install_fake_popen(monkeypatch, calls)
    monkeypatch.setattr(shell_mod, "current_os", lambda: "Darwin")
    monkeypatch.setattr(shell_runner, "spawn_kwargs", lambda: {"start_new_session": True})
    code, output = shell_runner.run_shell("echo hello")
    assert (code, output) == (0, "ok\n")
    args, kwargs = calls[0]
    assert args == ["zsh", "-ic", "echo hello"]
    assert kwargs["start_new_session"] is True
    assert kwargs["stdin"] == subprocess.DEVNULL
    env = kwargs["env"]
    assert env["TERM"] == "xterm-256color"
    assert env["COLORTERM"] == "truecolor"
    assert env["FORCE_COLOR"] == "1"
    assert env["LC_ALL"] == "C.UTF-8"


def test_run_shell_macos_node_command_does_not_source_nvm(monkeypatch):
    calls: list = []
    _install_fake_popen(monkeypatch, calls)
    monkeypatch.setattr(shell_mod, "current_os", lambda: "Darwin")
    monkeypatch.setattr(shell_runner, "spawn_kwargs", lambda: {"start_new_session": True})
    shell_runner.run_shell("pnpm install")
    assert calls[0][0] == ["zsh", "-ic", "pnpm install"]


def test_run_shell_propagates_nonzero_exit_code(monkeypatch):
    _install_fake_popen(monkeypatch, [], code=2)
    monkeypatch.setattr(shell_mod, "current_os", lambda: "Darwin")
    monkeypatch.setattr(shell_runner, "spawn_kwargs", lambda: {})
    code, _ = shell_runner.run_shell("false")
    assert code == 2


def test_run_shell_registers_and_marks_subrun(monkeypatch):
    registered: list = []
    marked: list = []

    def _register(sub_id: str, **kwargs: Any) -> None:
        registered.append((sub_id, kwargs))

    def _mark(sub_id: str, status: str, exit_code: int | None = None) -> None:
        marked.append((sub_id, status, exit_code))

    _install_fake_popen(monkeypatch, [])
    monkeypatch.setattr(shell_mod, "current_os", lambda: "Darwin")
    monkeypatch.setattr(shell_runner, "spawn_kwargs", lambda: {})
    monkeypatch.setattr(shell_runner, "get_pgid", lambda pid: pid)
    monkeypatch.setattr(shell_runner.subruns, "register", _register)
    monkeypatch.setattr(shell_runner.subruns, "mark_status", _mark)
    shell_runner.run_shell("echo hi", sub_id="s1", payload_id=7, mode="parallel")
    assert registered[0][0] == "s1"
    assert registered[0][1]["payload_id"] == 7
    assert registered[0][1]["mode"] == "parallel"
    assert registered[0][1]["label"] == "echo hi"
    assert registered[0][1]["pid"] == 4242
    assert marked == [("s1", "done", 0)]


def _run_auth_command(monkeypatch, passphrase: str | None):
    calls: list = []
    setup_calls: list = []
    _install_fake_popen(monkeypatch, calls)
    monkeypatch.setattr(shell_mod, "current_os", lambda: "Darwin")
    monkeypatch.setattr(shell_runner, "is_windows", lambda: False)
    monkeypatch.setattr(shell_runner, "spawn_kwargs", lambda: {"start_new_session": True})
    monkeypatch.setattr(shell_runner.askpass, "get_passphrase", lambda: passphrase)
    monkeypatch.setattr(shell_runner.askpass, "setup_env", setup_calls.append)
    shell_runner.run_shell("git push origin main")
    return calls[0][1], setup_calls


def test_auth_command_without_passphrase_inherits_tty(monkeypatch):
    kwargs, setup_calls = _run_auth_command(monkeypatch, None)
    assert kwargs["stdin"] is None
    assert "start_new_session" not in kwargs
    assert setup_calls == []


def test_auth_command_with_passphrase_runs_unattended(monkeypatch):
    kwargs, setup_calls = _run_auth_command(monkeypatch, "secret")
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["start_new_session"] is True
    assert len(setup_calls) == 1


# ============================================================
# Simulated: macOS Keychain + askpass helper
# ============================================================


def _fake_security(monkeypatch, calls: list, result=None, error: Exception | None = None):
    def _fake_run(args: Any, **kwargs: Any):
        calls.append(args)
        if error is not None:
            raise error
        return result

    monkeypatch.setattr(askpass_mod.shutil, "which", lambda name: "/usr/bin/security")
    monkeypatch.setattr(askpass_mod.subprocess, "run", _fake_run)


def test_keyring_macos_reads_keychain_and_strips(monkeypatch):
    calls: list = []
    _fake_security(monkeypatch, calls, result=_Result(0, "s3cret\n"))
    assert askpass_mod._get_keyring_macos() == "s3cret"
    assert calls[0] == ["security", "find-generic-password", "-s", "ssh", "-a", "github", "-w"]


def test_keyring_macos_item_not_found_returns_none(monkeypatch):
    _fake_security(monkeypatch, [], result=_Result(44, ""))
    assert askpass_mod._get_keyring_macos() is None


def test_keyring_macos_empty_output_returns_none(monkeypatch):
    _fake_security(monkeypatch, [], result=_Result(0, "\n"))
    assert askpass_mod._get_keyring_macos() is None


def test_keyring_macos_timeout_returns_none(monkeypatch):
    _fake_security(monkeypatch, [], error=subprocess.TimeoutExpired("security", 3))
    assert askpass_mod._get_keyring_macos() is None


def test_keyring_macos_missing_binary_returns_none(monkeypatch):
    monkeypatch.setattr(askpass_mod.shutil, "which", lambda name: None)
    assert askpass_mod._get_keyring_macos() is None


def test_helper_content_posix_is_sh_script_with_python():
    content = askpass_mod._helper_content_posix("/opt/py/bin/python3")
    assert content.startswith("#!/bin/sh")
    assert 'exec "/opt/py/bin/python3" -m runctx.utils.askpass' in content


# ============================================================
# Real POSIX (Linux + macOS runners; skipped on Windows)
# ============================================================


@posix_only
def test_real_spawn_kwargs_gives_own_process_group():
    proc = subprocess.Popen(["sleep", "30"], **system_mod.spawn_kwargs())
    try:
        assert system_mod.get_pgid(proc.pid) == proc.pid
        assert process_mod.is_pid_alive(proc.pid) is True
        assert process_mod.is_group_alive(proc.pid) is True
    finally:
        process_mod.kill_group(proc.pid, process_mod.SIGKILL)
        proc.wait(timeout=10)


@posix_only
def test_real_kill_group_terminates_whole_tree():
    argv = ["sh", "-c", "sleep 30 & sleep 30 & wait"]
    proc = subprocess.Popen(argv, **system_mod.spawn_kwargs())
    pgid = system_mod.get_pgid(proc.pid)
    assert pgid == proc.pid
    time.sleep(0.3)  # let sh fork its children
    assert process_mod.kill_group(pgid) is True
    proc.wait(timeout=10)
    assert proc.returncode < 0
    assert _wait_until(lambda: not process_mod.is_group_alive(pgid))


@posix_only
def test_real_kill_on_reaped_process_is_success():
    proc = subprocess.Popen(["true"])
    proc.wait(timeout=10)
    assert process_mod.is_pid_alive(proc.pid) is False
    assert process_mod.kill_pid(proc.pid) is True
    assert process_mod.kill_group(proc.pid) is True


@posix_only
def test_real_shutdown_pid_stops_stale_process():
    proc = subprocess.Popen(["sleep", "30"], **system_mod.spawn_kwargs())
    process_mod.shutdown_pid(proc.pid)
    proc.wait(timeout=10)
    assert proc.returncode < 0


@posix_only
def test_real_run_shell_output_and_exit_code():
    code, output = shell_runner.run_shell("echo runctx-real-ok")
    assert code == 0
    assert "runctx-real-ok" in output
    code, _ = shell_runner.run_shell("exit 3")
    assert code == 3


@posix_only
def test_real_run_shell_unicode_output():
    code, output = shell_runner.run_shell("echo xin chào đại ca")
    assert code == 0
    assert "xin chào đại ca" in output


@posix_only
def test_real_run_shell_exports_color_env():
    code, output = shell_runner.run_shell("echo $COLORTERM-$FORCE_COLOR")
    assert code == 0
    assert "truecolor-1" in output


@posix_only
def test_real_run_args_runs_without_shell():
    code, output = shell_runner.run_args(["echo", "args-ok"])
    assert code == 0
    assert "args-ok" in output


@posix_only
def test_real_file_lock_is_exclusive_across_handles(tmp_path):
    path = tmp_path / "lockfile"
    with path.open("w") as first, path.open("w") as second:
        lock_mod.acquire_lock(first, windows=False)
        with pytest.raises(OSError):
            lock_mod.acquire_lock(second, windows=False)
        lock_mod.release_lock(first, windows=False)
        lock_mod.acquire_lock(second, windows=False)
        lock_mod.release_lock(second, windows=False)


@posix_only
def test_real_askpass_helper_is_executable_valid_sh(tmp_path):
    helper = tmp_path / "askpass.sh"
    helper.write_text(askpass_mod.helper_content(sys.executable), encoding="utf-8")
    askpass_mod.chmod_executable(helper)
    assert helper.stat().st_mode & 0o777 == 0o700
    subprocess.run(["sh", "-n", str(helper)], check=True, timeout=10)


@posix_only
def test_real_warn_file_permission_flags_open_modes(tmp_path, capsys):
    secret = tmp_path / "passfile"
    secret.write_text("x", encoding="utf-8")
    secret.chmod(0o644)
    askpass_mod.warn_file_permission(secret)
    assert "chmod 600" in capsys.readouterr().err
    secret.chmod(0o600)
    askpass_mod.warn_file_permission(secret)
    assert capsys.readouterr().err == ""


# ============================================================
# Real macOS only (CI macos-latest)
# ============================================================


@macos_only
def test_real_macos_platform_detection_and_spawn_kwargs():
    assert system_mod.current_os() == "Darwin"
    assert system_mod.is_macos() is True
    assert system_mod.is_linux() is False
    assert system_mod.spawn_kwargs() == {"start_new_session": True}
    assert system_mod.create_new_process_group_flag() == 0


@macos_only
def test_real_macos_group_alive_uses_killpg_branch():
    proc = subprocess.Popen(["sleep", "30"], **system_mod.spawn_kwargs())
    try:
        assert process_mod.is_group_alive(proc.pid) is True
        assert process_mod._is_group_alive_posix(proc.pid) is True
    finally:
        process_mod.kill_group(proc.pid, process_mod.SIGKILL)
        proc.wait(timeout=10)
    assert _wait_until(lambda: not process_mod.is_group_alive(proc.pid))


@macos_only
def test_real_macos_run_shell_uses_zsh():
    code, output = shell_runner.run_shell("echo zsh-$ZSH_VERSION")
    assert code == 0
    lines = [line.strip() for line in output.splitlines()]
    assert any(line.startswith("zsh-") and len(line) > len("zsh-") for line in lines)


@macos_only
def test_real_macos_keychain_lookup_does_not_crash():
    result = askpass_mod._get_keyring_macos()
    assert result is None or isinstance(result, str)
