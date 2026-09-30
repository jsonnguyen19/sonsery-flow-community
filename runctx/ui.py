"""Console UI helpers: ANSI colors, banner, box drawing.

Colors are automatically disabled when:
- stdout is not a TTY (piped/redirected)
- NO_COLOR env is set (https://no-color.org)
- TERM=dumb

Every print_* function also appends a line to the terminal log ring buffer
(state.append_log) so the popup/side panel can display it.
"""

import os
import sys

from .state import append_log
from .utils.output import lowercase_first

# ============ COLOR DETECTION ============


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


_COLOR = _supports_color()


class _C:
    """ANSI color codes. Empty strings when color is unsupported."""

    RESET = "\033[0m" if _COLOR else ""
    BOLD = "\033[1m" if _COLOR else ""
    DIM = "\033[2m" if _COLOR else ""

    # Foreground
    BLACK = "\033[30m" if _COLOR else ""
    RED = "\033[31m" if _COLOR else ""
    GREEN = "\033[32m" if _COLOR else ""
    YELLOW = "\033[33m" if _COLOR else ""
    BLUE = "\033[34m" if _COLOR else ""
    MAGENTA = "\033[35m" if _COLOR else ""
    CYAN = "\033[36m" if _COLOR else ""
    WHITE = "\033[37m" if _COLOR else ""

    # Bright
    BRIGHT_CYAN = "\033[96m" if _COLOR else ""
    BRIGHT_MAGENTA = "\033[95m" if _COLOR else ""
    BRIGHT_GREEN = "\033[92m" if _COLOR else ""
    BRIGHT_YELLOW = "\033[93m" if _COLOR else ""
    BRIGHT_RED = "\033[91m" if _COLOR else ""


C = _C


# ============ BANNER ============

_BANNER = r"""
   ███████╗ ██████╗ ███╗   ██╗███████╗███████╗██████╗ ██╗   ██╗
   ██╔════╝██╔═══██╗████╗  ██║██╔════╝██╔════╝██╔══██╗╚██╗ ██╔╝
   ███████╗██║   ██║██╔██╗ ██║███████╗█████╗  ██████╔╝ ╚████╔╝
   ╚════██║██║   ██║██║╚██╗██║╚════██║██╔══╝  ██╔══██╗  ╚██╔╝
   ███████║╚██████╔╝██║ ╚████║███████║███████╗██║  ██║   ██║
   ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝╚══════╝╚═╝  ╚═╝   ╚═╝
                        F L O W   ▸  runctx"""


# ============ RENDER HELPERS ============


def _log(line: str) -> None:
    """Append 1 dong plain (da strip ANSI) vao ring buffer."""
    append_log(line)


def print_banner() -> None:
    """In banner lon khi khoi dong watchctx."""
    print()
    print(f"{C.BRIGHT_CYAN}{_BANNER}{C.RESET}")
    print(f"{C.DIM}   ─────────────────────────────────────────────────────────{C.RESET}")
    print()
    _log("watchctx started")
    _log(_BANNER.strip().splitlines()[0].strip())


def print_status(label: str, value: str, *, ok: bool = True, accent: bool = False) -> None:
    """In dong trang thai dang 'label  value' voi icon.

    - ok=True -> icon xanh (mac dinh)
    - accent=True -> icon magenta, value in dam
    """
    if accent:
        icon = f"{C.BRIGHT_MAGENTA}◆{C.RESET}"
        value_str = f"{C.BOLD}{value}{C.RESET}"
    elif ok:
        icon = f"{C.BRIGHT_GREEN}●{C.RESET}"
        value_str = value
    else:
        icon = f"{C.BRIGHT_YELLOW}●{C.RESET}"
        value_str = value
    print(f"   {icon} {C.DIM}{label:<10}{C.RESET} {value_str}")
    _log(f"{label:<10} {value}")


def print_ready_hint() -> None:
    """In goi y che do cho user."""
    print()
    print(
        f"   {C.BRIGHT_MAGENTA}▸{C.RESET} {C.DIM}Copy a runctx payload into your clipboard to trigger a run.{C.RESET}"
    )
    print(f"   {C.BRIGHT_MAGENTA}▸{C.RESET} {C.DIM}Press Ctrl+C to stop.{C.RESET}")
    print()
    _log("Ready. Copy a runctx payload into your clipboard to trigger a run.")


def print_payload_header() -> None:
    """In header khi phat hien payload."""
    print()
    print(f"{C.BRIGHT_YELLOW}   ┌─ RUNCTX PAYLOAD DETECTED ────────────────────────────┐{C.RESET}")
    _log("┌─ RUNCTX PAYLOAD DETECTED ──")


def print_payload_footer() -> None:
    print(f"{C.BRIGHT_YELLOW}   └──────────────────────────────────────────────────────┘{C.RESET}")
    print()
    _log("└────────────────────────────")


def print_result_header(success: bool) -> None:
    if success:
        color, tag = C.BRIGHT_GREEN, "OK"
    else:
        color, tag = C.BRIGHT_RED, "FAIL"
    print()
    print(f"{color}   ┌─ RESULT [{tag}] ──────────────────────────────────────┐{C.RESET}")
    _log(f"┌─ RESULT [{tag}] ──")


def print_result_footer() -> None:
    print(f"{C.DIM}   └──────────────────────────────────────────────────────┘{C.RESET}")
    print()
    _log("└────────────────────────────")


def _print_with_icon(icon: str, color: str, msg: str) -> None:
    """In 1 dong voi icon + mau (dung chung cho error/warn/info/success).

    Tu dong ha chu cai dau cua `msg` xuong chu thuong (tru khi msg bat dau
    bang identifier/path/JSON/ACRONYM — xem `lowercase_first`).
    """
    msg = lowercase_first(msg)
    print(f"{color}   {icon} {msg}{C.RESET}")
    _log(f"{icon} {msg}")


def print_error(msg: str) -> None:
    _print_with_icon("✗", C.BRIGHT_RED, msg)


def print_warn(msg: str) -> None:
    _print_with_icon("⚠", C.BRIGHT_YELLOW, msg)


def print_info(msg: str) -> None:
    _print_with_icon("▸", C.BRIGHT_CYAN, msg)


def print_success(msg: str) -> None:
    _print_with_icon("✓", C.BRIGHT_GREEN, msg)
