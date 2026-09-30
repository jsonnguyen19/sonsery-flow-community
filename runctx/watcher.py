"""Main watcher loop: poll/event clipboard -> parse -> run -> publish."""

import json
import os
import queue
import sys
import time
from pathlib import Path
from typing import Any, Optional

import yaml

from . import history as _history
from .bridge import BRIDGE_PORT_FILE, start_bridge_server
from .constants import (
    BRIDGE_HOST,
    BRIDGE_PORT,
    LAST_INPUT_HASH_FILE,
    LAST_OUTPUT_HASH_FILE,
    PID_FILE,
    PWD_FILE,
    RUNCTX_TOOLS,
)
from .constants import (
    IDLE_SLEEP as _IDLE_SLEEP,
)
from .constants import (
    PAYLOAD_PREVIEW_CHARS as _PAYLOAD_PREVIEW_CHARS,
)
from .constants import (
    QUEUE_TIMEOUT as _QUEUE_TIMEOUT,
)
from .constants import (
    TOOL_DECL_PREVIEW_LINES as _TOOL_DECL_PREVIEW_LINES,
)
from .payload import invalid_result, parse_runctx_payload
from .platform.clipboard import (
    clipboard_event_queue,
    get_clipboard,
    set_clipboard,
    start_clipboard_listener,
)
from .runner import run_runctx
from .state import set_latest_result
from .ui import (
    print_banner,
    print_error,
    print_info,
    print_payload_footer,
    print_payload_header,
    print_ready_hint,
    print_result_footer,
    print_result_header,
    print_status,
)
from .utils.fence import extract_code_fence
from .utils.hash import read_hash, sha, write_hash
from .utils.process import shutdown_old_watchctx


def _declares_runctx_tool(text: str) -> bool:
    """Strict check: tool declaration phai nam trong N dong dau tien."""
    cleaned = extract_code_fence(text)
    first_lines = "\n".join(cleaned.splitlines()[:_TOOL_DECL_PREVIEW_LINES])
    for tool in RUNCTX_TOOLS:
        for pattern in (
            f'"tool": "{tool}"',
            f'"tool":"{tool}"',
            f"tool: {tool}",
            f"tool:  {tool}",
        ):
            if pattern in first_lines:
                return True
    return False


def _extract_payload_id(text: str) -> Optional[Any]:
    """Thu extract truong 'id' tu payload (dung cho error response)."""
    try:
        tentative = yaml.safe_load(extract_code_fence(text))
        if isinstance(tentative, dict):
            return tentative.get("id")
    except Exception:
        pass
    return None


def _print_payload_preview(payload: str) -> None:
    """In preview payload (truncate neu qua dai)."""
    print_payload_header()
    print(payload[:_PAYLOAD_PREVIEW_CHARS])
    if len(payload) > _PAYLOAD_PREVIEW_CHARS:
        print("\n... truncated preview ...")
    print_payload_footer()


def _build_output_obj(success: bool, output: str, parsed_payload: Optional[dict]) -> str:
    """Build JSON output object tu ket qua run_runctx."""
    data_items: list = []
    error_msg: Optional[str] = None

    if success:
        # Parse output as structured data
        try:
            # Check if output is already JSON (from batch processing)
            if output.strip().startswith("[") or output.strip().startswith("{"):
                parsed = json.loads(output)
                data_items = parsed if isinstance(parsed, list) else [parsed]
            else:
                # Split by newlines for shell commands
                lines = [line.strip() for line in output.strip().split("\n") if line.strip()]
                data_items = lines if lines else [output] if output.strip() else []
        except Exception:
            data_items = [output] if output.strip() else []
    else:
        error_msg = output or "Command failed"

    # Include id in output if present
    output_obj = {
        "success": success,
        "data": data_items,
        "error": error_msg,
    }
    if parsed_payload and parsed_payload.get("id") is not None:
        output_obj["id"] = parsed_payload.get("id")

    return json.dumps(output_obj, ensure_ascii=False)


def _publish_result(wrapped_output: str) -> str:
    """Publish output len bridge + clipboard + state file. Tra ve hash."""
    set_latest_result(wrapped_output)
    set_clipboard(wrapped_output)
    out_hash = sha(wrapped_output)
    write_hash(LAST_OUTPUT_HASH_FILE, out_hash)
    return out_hash


def main() -> int:
    # `--about`: print tool info and exit without starting the watcher.
    if "--about" in sys.argv or "-a" in sys.argv:
        try:
            from scripts.about import About

            About().run()
            return 0
        except Exception as exc:  # pragma: no cover - best effort
            print(f"WARN: could not run about: {exc}")
            return 1

    # Shutdown any previous watchctx process
    shutdown_old_watchctx(PID_FILE)

    # Kill orphan sub-runs from a previous session (if the watcher crashed or
    # was kill -9'd, finally never ran -> child processes are still alive).
    # Best-effort, never raises.
    try:
        from . import subruns as _subruns

        _pruned = _subruns.prune_stale()
        if _pruned.get("killed"):
            print(f"Pruned {len(_pruned['killed'])} stale sub-run(s) from previous session")
    except Exception as _exc:
        print(f"WARN: subrun prune_stale failed: {_exc}")

    # Write current PID
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")

    # Write current PWD so Bridge RPC resolves paths against the same root
    # as the clipboard flow (read/write/replace/shell), not the package dir.
    try:
        PWD_FILE.write_text(str(Path.cwd()), encoding="utf-8")
    except OSError:
        pass

    server = start_bridge_server()

    print_banner()

    listener_process = start_clipboard_listener()
    event_driven = listener_process is not None

    # Port thuc te co the khac BRIDGE_PORT neu port goc bi chiem/block.
    # Doc tu bridge.active_bridge_port (duoc set trong start_bridge_server).
    import runctx.bridge as _bridge_mod

    actual_port = _bridge_mod.active_bridge_port or BRIDGE_PORT
    print_status("Bridge", f"http://{BRIDGE_HOST}:{actual_port}")
    mode = "clipboard (event-driven)" if event_driven else "clipboard (polling)"
    print_status("Watching", mode)
    print_status("Ready", "waiting for payload", accent=True)

    print_ready_hint()

    last_input_hash = read_hash(LAST_INPUT_HASH_FILE) or sha(get_clipboard())
    last_output_hash = read_hash(LAST_OUTPUT_HASH_FILE)

    try:
        while True:
            try:
                if event_driven and listener_process is not None:
                    if listener_process.poll() is not None:
                        print("WARN: clipboard listener process died, falling back to polling")
                        event_driven = False
                        text = get_clipboard()
                    else:
                        try:
                            text = clipboard_event_queue.get(timeout=_QUEUE_TIMEOUT)
                        except queue.Empty:
                            continue
                else:
                    text = get_clipboard()

                current_hash = sha(text)

                if text and current_hash != last_input_hash and current_hash != last_output_hash:
                    # Strict check: valid tool declaration must be at the very beginning lines
                    if not _declares_runctx_tool(text):
                        last_input_hash = current_hash
                        write_hash(LAST_INPUT_HASH_FILE, current_hash)
                        time.sleep(_IDLE_SLEEP)
                        continue

                    parsed_payload, invalid_reason = parse_runctx_payload(text)
                    if parsed_payload is None:
                        last_input_hash = current_hash
                        write_hash(LAST_INPUT_HASH_FILE, current_hash)

                        if invalid_reason == "Clipboard contains a previous RUNCTX_RESULT":
                            time.sleep(_IDLE_SLEEP)
                            continue

                        print_error(f"Invalid payload: {invalid_reason}")

                        payload_id = _extract_payload_id(text)

                        ignored_output = invalid_result(
                            invalid_reason,
                            hint="Fix the runctx payload, then copy it again.",
                            payload_id=payload_id,
                        )

                        set_latest_result(ignored_output)
                        set_clipboard(ignored_output)
                        print(ignored_output)
                        print_info("Copied invalid result to clipboard")
                        last_output_hash = sha(ignored_output)
                        write_hash(LAST_OUTPUT_HASH_FILE, last_output_hash)
                        time.sleep(_IDLE_SLEEP)
                        continue

                    payload = extract_code_fence(text)

                    last_input_hash = current_hash
                    write_hash(LAST_INPUT_HASH_FILE, current_hash)

                    _print_payload_preview(payload)

                    _run_started_at = time.time()
                    code, output = run_runctx(payload)
                    _run_duration_ms = int((time.time() - _run_started_at) * 1000)
                    success = code == 0

                    wrapped_output = _build_output_obj(success, output, parsed_payload)
                    last_output_hash = _publish_result(wrapped_output)

                    # Best-effort: write history; must not crash the watcher loop.
                    try:
                        _tool_name = (
                            parsed_payload.get("tool") if isinstance(parsed_payload, dict) else None
                        )
                        _history.append(
                            payload_id=parsed_payload.get("id")
                            if isinstance(parsed_payload, dict)
                            else None,
                            tool=str(_tool_name or "unknown"),
                            payload_preview=payload,
                            result_preview=output if success else (output or "Command failed"),
                            status="success" if success else "error",
                            duration_ms=_run_duration_ms,
                        )
                    except Exception as _hist_exc:
                        print(f"WARN: history append failed: {_hist_exc}")

                    print_result_header(success)
                    print(wrapped_output)
                    print_result_footer()
                    print_info("Copied result to clipboard")
                    print_info("Published result to bridge")

                time.sleep(_IDLE_SLEEP)

            except KeyboardInterrupt:
                print("\nwatchctx stopped")
                return 0
            except Exception as exc:
                print(f"WARN: watchctx loop error: {exc}")
                time.sleep(_IDLE_SLEEP)
    finally:
        # Kill sub-runs BEFORE shutting down the bridge — avoids orphans.
        # Best-effort: cleanup_all never raises even on error.
        try:
            from . import subruns as _subruns

            _subruns.cleanup_all()
        except Exception as _exc:
            print(f"WARN: subrun cleanup_all failed: {_exc}")

        # Remove PID file on exit
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        # Remove PWD file on exit (Bridge falls back to package root).
        try:
            PWD_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        # Remove bridge-port file on exit — tranh extension doc port cu.
        try:
            BRIDGE_PORT_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        # Remove active-root on exit — tranh carry-over sang phien khac.
        # Dung shared helper de dong bo voi root.py.
        try:
            from .root import clear_active_root

            clear_active_root()
        except Exception:
            pass
        if server:
            server.shutdown()
        if listener_process and listener_process.poll() is None:
            try:
                listener_process.terminate()
            except Exception:
                pass
