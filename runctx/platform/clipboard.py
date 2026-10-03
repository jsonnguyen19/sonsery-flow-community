"""Cross-platform clipboard.

All clipboard backends (Linux/macOS/Windows) + OS dispatch live in this file.
Callers only use `get_clipboard()`, `set_clipboard(text)`,
`start_clipboard_listener()`, `clipboard_event_queue` — OS-agnostic.

`_*` functions are private and not exported.
"""

from __future__ import annotations

import base64
import os
import queue
import subprocess
import threading

from ..constants import CLIPBOARD_TIMEOUT
from .system import current_os, is_windows

# ============ PUBLIC STATE ============

# Queue receiving clipboard events from the Windows listener (event-driven mode).
clipboard_event_queue: queue.Queue[str] = queue.Queue()


# ============ LINUX BACKEND ============

_LINUX_GET_COMMANDS = ["xclip -selection clipboard -o", "wl-paste"]
_LINUX_SET_COMMANDS = ["xclip -selection clipboard", "wl-copy"]


def _get_clipboard_linux() -> str:
    """Get clipboard on Linux using xclip or wl-clipboard."""
    for cmd in _LINUX_GET_COMMANDS:
        try:
            result = subprocess.run(
                cmd, shell=True, text=True, capture_output=True, timeout=CLIPBOARD_TIMEOUT
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
    return ""


def _set_clipboard_linux(text: str) -> bool:
    """Set clipboard on Linux using xclip or wl-clipboard."""
    for cmd in _LINUX_SET_COMMANDS:
        try:
            subprocess.run(
                cmd, input=text, text=True, shell=True, timeout=CLIPBOARD_TIMEOUT, check=True
            )
            return True
        except Exception:
            pass
    return False


# ============ MACOS BACKEND ============


def _get_clipboard_macos() -> str:
    """Get clipboard on macOS using pbpaste."""
    try:
        result = subprocess.run(
            ["pbpaste"], text=True, capture_output=True, timeout=CLIPBOARD_TIMEOUT
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _set_clipboard_macos(text: str) -> bool:
    """Set clipboard on macOS using pbcopy."""
    try:
        subprocess.run(["pbcopy"], input=text, text=True, timeout=CLIPBOARD_TIMEOUT, check=True)
        return True
    except Exception:
        return False


# ============ WINDOWS BACKEND ============


def _get_clipboard_windows() -> str:
    """Get clipboard on Windows using PowerShell."""
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); Get-Clipboard",
            ],
            text=True,
            capture_output=True,
            timeout=CLIPBOARD_TIMEOUT,
        )
        return result.stdout.replace("\r", "").strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _set_clipboard_windows(text: str) -> bool:
    """Set clipboard on Windows using PowerShell.

    Text is base64-encoded (UTF-8) and passed via env var so we avoid
    stdin/console-encoding pitfalls entirely.
    """
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    env = {**os.environ, "RUNCTX_CLIP_B64": encoded}
    try:
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Set-Clipboard -Value ([System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:RUNCTX_CLIP_B64)))",
            ],
            env=env,
            text=True,
            timeout=CLIPBOARD_TIMEOUT,
            check=True,
        )
        return True
    except Exception:
        return False


def _start_clipboard_listener_windows():
    """Windows-only event-driven listener (PowerShell + WinForms).

    Returns a Popen or None if startup fails (caller falls back to polling).
    """
    CLIPBOARD_LISTENER_PS1 = r"""
$ErrorActionPreference = 'Stop'

try {
    Add-Type -AssemblyName System.Windows.Forms
} catch {
    Write-Output "###LISTENER_ERROR### Cannot load System.Windows.Forms: $($_.Exception.Message)"
    exit 1
}

Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Windows.Forms;

public class RunctxClipboardListener : Form {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool AddClipboardFormatListener(IntPtr hwnd);

    public const int WM_CLIPBOARDUPDATE = 0x031D;
    public event EventHandler ClipboardChanged;

    public RunctxClipboardListener() {
        this.ShowInTaskbar = false;
        this.WindowState = FormWindowState.Minimized;
        this.Load += (s, e) => { AddClipboardFormatListener(this.Handle); };
    }

    protected override void WndProc(ref Message m) {
        if (m.Msg == WM_CLIPBOARDUPDATE) {
            EventHandler handler = ClipboardChanged;
            if (handler != null) {
                handler(this, EventArgs.Empty);
            }
        }
        base.WndProc(ref m);
    }
}
"@ -ReferencedAssemblies System.Windows.Forms

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

try {
    $listener = New-Object RunctxClipboardListener
} catch {
    Write-Output "###LISTENER_ERROR### Cannot create listener form: $($_.Exception.Message)"
    exit 1
}

$listener.add_ClipboardChanged({
    try {
        if ([System.Windows.Forms.Clipboard]::ContainsText()) {
            $text = [System.Windows.Forms.Clipboard]::GetText()
            $bytes = [System.Text.Encoding]::UTF8.GetBytes($text)
            $b64 = [Convert]::ToBase64String($bytes)
            [Console]::Out.WriteLine("###CLIP_START###")
            [Console]::Out.WriteLine($b64)
            [Console]::Out.WriteLine("###CLIP_END###")
            [Console]::Out.Flush()
        }
    } catch {
        [Console]::Error.WriteLine("handler error: $($_.Exception.Message)")
    }
})

Write-Output "###LISTENER_READY###"

try {
    [System.Windows.Forms.Application]::Run($listener)
} catch {
    Write-Output "###LISTENER_ERROR### Run loop failed: $($_.Exception.Message)"
    exit 1
}
"""

    try:
        process = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Sta",
                "-Command",
                CLIPBOARD_LISTENER_PS1,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except Exception as exc:
        print(f"WARN: clipboard listener failed to start: {exc}")
        return None

    ready = threading.Event()
    listener_error: list[str] = []

    def read_listener_output() -> None:
        if process.stdout is None:
            return

        buffer: list[str] = []
        capturing = False

        for line in process.stdout:
            line = line.rstrip("\r\n")

            if line == "###LISTENER_READY###":
                ready.set()
                continue

            if line.startswith("###LISTENER_ERROR###"):
                msg = line[len("###LISTENER_ERROR###") :].strip()
                listener_error.append(msg)
                print(f"WARN: clipboard listener error: {msg}")
                ready.set()
                continue

            if line == "###CLIP_START###":
                capturing = True
                buffer = []
                continue

            if line == "###CLIP_END###":
                capturing = False
                b64_data = "".join(buffer)
                try:
                    text = base64.b64decode(b64_data).decode("utf-8", errors="replace")
                    clipboard_event_queue.put(text)
                except Exception:
                    pass
                continue

            if capturing:
                buffer.append(line)

    def read_listener_stderr() -> None:
        if process.stderr is None:
            return
        for line in process.stderr:
            line = line.rstrip("\r\n")
            if line:
                print(f"WARN: clipboard listener stderr: {line}")

    reader_thread = threading.Thread(target=read_listener_output, daemon=True)
    reader_thread.start()
    stderr_thread = threading.Thread(target=read_listener_stderr, daemon=True)
    stderr_thread.start()

    if not ready.wait(timeout=5):
        print("WARN: clipboard listener did not become ready, falling back to polling")
        try:
            process.terminate()
        except Exception:
            pass
        return None

    # If PowerShell reported an explicit error before ready -> fall back to polling.
    if listener_error:
        print("WARN: clipboard listener exited with error, falling back to polling")
        try:
            process.terminate()
        except Exception:
            pass
        return None

    return process


# ============ PUBLIC API (dispatch by OS) ============
#
# Dict dispatch instead of if/elif chains — works on Python 3.8 (match/case
# requires 3.10). Unknown OS falls back to the Linux backend.

_GET_CLIPBOARD_BY_OS = {
    "Windows": _get_clipboard_windows,
    "Darwin": _get_clipboard_macos,
}

_SET_CLIPBOARD_BY_OS = {
    "Windows": _set_clipboard_windows,
    "Darwin": _set_clipboard_macos,
}


def get_clipboard() -> str:
    """Cross-platform clipboard getter. Caller is OS-agnostic."""
    getter = _GET_CLIPBOARD_BY_OS.get(current_os(), _get_clipboard_linux)
    return getter()


def set_clipboard(text: str) -> None:
    """Cross-platform clipboard setter. Caller is OS-agnostic."""
    setter = _SET_CLIPBOARD_BY_OS.get(current_os(), _set_clipboard_linux)
    setter(text)


def start_clipboard_listener():
    """Start clipboard event listener. Chi Windows ho tro; OS khac -> None
    (watcher se bao mode polling).
    """
    if not is_windows():
        return None
    return _start_clipboard_listener_windows()


__all__ = [
    "clipboard_event_queue",
    "get_clipboard",
    "set_clipboard",
    "start_clipboard_listener",
]
