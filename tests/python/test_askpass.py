"""Tests for runctx.utils.askpass.

Covers:
- is_auth_command correctly recognizes commands that need auth.
- get_passphrase reads from env / file in priority order.
- setup_env sets SSH_ASKPASS + SSH_ASKPASS_REQUIRE correctly.
- ensure_helper creates the file and returns its path.
"""

import stat
import sys

import pytest

from runctx.utils import askpass

# ============ is_auth_command ============


@pytest.mark.parametrize(
    "cmd",
    [
        "git push",
        "git push origin main",
        "git fetch --all",
        "git pull",
        "git clone git@github.com:x/y.git",
        "git remote add origin git@github.com:x/y.git",
        "git ls-remote origin",
        "git ls-remote --heads origin",
        "git remote show origin",
        "git remote update",
        "git submodule update --init --recursive",
        "ssh user@host",
        "scp file host:/path",
        "sftp host",
        "cd /tmp && git push",
        "pnpm check && git push",
    ],
)
def test_is_auth_command_true(cmd):
    assert askpass.is_auth_command(cmd) is True


@pytest.mark.parametrize(
    "cmd",
    [
        "git status",
        "git log",
        "git diff",
        "git commit -m x",
        "ls -la",
        "echo hello",
        "npm run dev",
        "",
        "git --version",
    ],
)
def test_is_auth_command_false(cmd):
    assert askpass.is_auth_command(cmd) is False


# ============ get_passphrase: env priority ============


def test_get_passphrase_from_env(monkeypatch):
    monkeypatch.setenv("SONSSH_PASSPHRASE", "secret-from-env")
    assert askpass.get_passphrase() == "secret-from-env"


def test_env_overrides_file(monkeypatch, tmp_path):
    fake_file = tmp_path / "passphrase"
    fake_file.write_text("from-file\n", encoding="utf-8")
    monkeypatch.setattr(askpass, "PASSPHRASE_FILE", fake_file)
    monkeypatch.setenv("SONSSH_PASSPHRASE", "from-env")
    assert askpass.get_passphrase() == "from-env"


# ============ get_passphrase: file ============


def test_get_passphrase_from_file(monkeypatch, tmp_path):
    fake_file = tmp_path / "passphrase"
    fake_file.write_text("file-secret\n", encoding="utf-8")
    monkeypatch.setattr(askpass, "PASSPHRASE_FILE", fake_file)
    monkeypatch.delenv("SONSSH_PASSPHRASE", raising=False)
    # Block keyring (may exist on CI) so the file path is exercised.
    monkeypatch.setattr(askpass._platform_askpass, "get_keyring", lambda: None)
    assert askpass.get_passphrase() == "file-secret"


def test_file_with_only_newline(monkeypatch, tmp_path):
    fake_file = tmp_path / "passphrase"
    fake_file.write_text("\n", encoding="utf-8")
    monkeypatch.setattr(askpass, "PASSPHRASE_FILE", fake_file)
    monkeypatch.delenv("SONSSH_PASSPHRASE", raising=False)
    monkeypatch.setattr(askpass._platform_askpass, "get_keyring", lambda: None)
    assert askpass.get_passphrase() is None


def test_missing_file_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(askpass, "PASSPHRASE_FILE", tmp_path / "nonexistent")
    monkeypatch.delenv("SONSSH_PASSPHRASE", raising=False)
    monkeypatch.setattr(askpass._platform_askpass, "get_keyring", lambda: None)
    assert askpass.get_passphrase() is None


# ============ ensure_helper ============


def test_ensure_helper_creates_file(monkeypatch, tmp_path):
    fake_ssh = tmp_path / ".ssh"
    fake_helper = fake_ssh / "askpass-helper"
    monkeypatch.setattr(askpass, "SSH_DIR", fake_ssh)
    monkeypatch.setattr(askpass, "HELPER_PATH", fake_helper)

    result = askpass.ensure_helper()
    assert result == fake_helper
    assert fake_helper.exists()
    content = fake_helper.read_text(encoding="utf-8")
    assert "askpass" in content


def test_ensure_helper_executable_on_posix(monkeypatch, tmp_path):
    if sys.platform == "win32":
        pytest.skip("POSIX only")
    fake_ssh = tmp_path / ".ssh"
    fake_helper = fake_ssh / "askpass-helper"
    monkeypatch.setattr(askpass, "SSH_DIR", fake_ssh)
    monkeypatch.setattr(askpass, "HELPER_PATH", fake_helper)

    askpass.ensure_helper()
    mode = fake_helper.stat().st_mode
    assert mode & stat.S_IXUSR  # user execute bit


def test_ensure_helper_idempotent(monkeypatch, tmp_path):
    fake_ssh = tmp_path / ".ssh"
    fake_helper = fake_ssh / "askpass-helper"
    monkeypatch.setattr(askpass, "SSH_DIR", fake_ssh)
    monkeypatch.setattr(askpass, "HELPER_PATH", fake_helper)

    askpass.ensure_helper()
    first_content = fake_helper.read_text(encoding="utf-8")
    askpass.ensure_helper()
    assert fake_helper.read_text(encoding="utf-8") == first_content


def test_ensure_helper_regenerates_on_interpreter_change(monkeypatch, tmp_path):
    """If the old helper file points to a different interpreter -> regenerate."""
    fake_ssh = tmp_path / ".ssh"
    fake_ssh.mkdir(parents=True)
    fake_helper = fake_ssh / "askpass-helper"
    fake_helper.write_text(
        "#!/bin/sh\nexec /old/python -m runctx.utils.askpass\n", encoding="utf-8"
    )

    monkeypatch.setattr(askpass, "SSH_DIR", fake_ssh)
    monkeypatch.setattr(askpass, "HELPER_PATH", fake_helper)

    result = askpass.ensure_helper()
    assert result == fake_helper
    content = fake_helper.read_text(encoding="utf-8")
    # No longer points to the old interpreter.
    assert "/old/python" not in content
    # Points to the current interpreter (sys.executable).
    assert sys.executable in content


# ============ setup_env ============


def test_setup_env_sets_askpass(monkeypatch, tmp_path):
    fake_ssh = tmp_path / ".ssh"
    fake_helper = fake_ssh / "askpass-helper"
    monkeypatch.setattr(askpass, "SSH_DIR", fake_ssh)
    monkeypatch.setattr(askpass, "HELPER_PATH", fake_helper)

    env = {}
    askpass.setup_env(env)
    assert env["SSH_ASKPASS"] == str(fake_helper)
    assert env["SSH_ASKPASS_REQUIRE"] == "force"
    assert "DISPLAY" in env


def test_setup_env_does_not_override(monkeypatch, tmp_path):
    fake_ssh = tmp_path / ".ssh"
    fake_helper = fake_ssh / "askpass-helper"
    monkeypatch.setattr(askpass, "SSH_DIR", fake_ssh)
    monkeypatch.setattr(askpass, "HELPER_PATH", fake_helper)

    env = {"SSH_ASKPASS": "/custom/path"}
    askpass.setup_env(env)
    assert env["SSH_ASKPASS"] == "/custom/path"


def test_setup_env_keeps_existing_display(monkeypatch, tmp_path):
    fake_ssh = tmp_path / ".ssh"
    fake_helper = fake_ssh / "askpass-helper"
    monkeypatch.setattr(askpass, "SSH_DIR", fake_ssh)
    monkeypatch.setattr(askpass, "HELPER_PATH", fake_helper)

    env = {"DISPLAY": ":1"}
    askpass.setup_env(env)
    assert env["DISPLAY"] == ":1"
