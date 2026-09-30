"""Tool handlers: shell, read, replace, write."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from . import subruns
from .shell_runner import run_shell
from .utils.fs import read_file_range, read_text, safe_path, write_text


def _print_section(label: str) -> None:
    """Print a section separator line (e.g. '===== READ: file.txt =====')."""
    print(f"===== {label} =====")


def _file_not_found(path) -> Dict[str, Any]:
    """Build a failure result for a missing file."""
    return {"path": str(path), "success": False, "error": f"File not found: {path}"}


def _ok(path, **extra: Any) -> Dict[str, Any]:
    """Build a success result with path + extra fields."""
    return {"path": str(path), "success": True, **extra}


def _fail(path, error: str, **extra: Any) -> Dict[str, Any]:
    """Build a failure result with path + error + extra fields."""
    return {"path": str(path), "success": False, "error": error, **extra}


def _run_one_shell(cmd: str, index: int, payload_id: Optional[int], mode: str) -> Dict[str, Any]:
    """Run one shell command; register a sub-run if payload_id is set."""
    _print_section(f"SHELL: {cmd}")
    sub_id = subruns.make_sub_id(payload_id, index) if payload_id is not None else None
    code, output = run_shell(cmd, sub_id=sub_id, payload_id=payload_id, mode=mode)
    return {"command": cmd, "exit_code": code, "output": output}


def handle_shell(
    commands: List[str],
    *,
    payload_id: Optional[int] = None,
    mode: str = "sequential",
) -> List[Dict[str, Any]]:
    """Execute shell commands.

    mode='sequential' (default): run one after another (old behavior).
    mode='parallel': spawn all at once, wait for all to finish.

    payload_id: when set, each command is registered in the subrun registry
    with sub_id = '<payload_id>:<index>' -> can be killed externally.
    """
    if mode == "parallel":
        with ThreadPoolExecutor(max_workers=len(commands)) as executor:
            futures = [
                executor.submit(_run_one_shell, cmd, i, payload_id, mode)
                for i, cmd in enumerate(commands)
            ]
            return [f.result() for f in futures]

    # Default: sequential
    results = []
    for i, cmd in enumerate(commands):
        results.append(_run_one_shell(cmd, i, payload_id, mode))
    return results


def handle_read(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Read files with optional range."""
    results = []
    for item in files:
        path = safe_path(str(item["path"]))
        start = item.get("start")
        end = item.get("end")

        _print_section(f"READ: {path} {start or 1}-{end or 'EOF'}")

        if not path.exists():
            print(f"SKIPPED: missing {path}")
            results.append(_file_not_found(path))
            continue

        if start is not None or end is not None:
            content = read_file_range(path, start, end)
        else:
            content = read_text(path)

        print(content)
        results.append(_ok(path, content=content))

    return results


def handle_replace(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Replace content in files (search and replace)."""
    results = []
    for item in files:
        path = safe_path(str(item["path"]))
        search = item["search"]
        replace = item["replace"]

        _print_section(f"REPLACE: {path}")

        if not path.exists():
            print(f"ERROR: missing file: {path}")
            results.append(_file_not_found(path))
            continue

        content = read_text(path)
        count = content.count(search)

        if count != 1:
            print(f"ERROR: {path} search matched {count} times")
            print(f"SEARCH: {search!r}")
            results.append(
                _fail(
                    path,
                    f"Search matched {count} times (expected exactly 1)",
                    search=search,
                    matches=count,
                )
            )
            continue

        write_text(path, content.replace(search, replace))
        print(f"OK: updated {path}")
        results.append(_ok(path, message=f"Updated {path}"))

    return results


def handle_write(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Write content to files."""
    results = []
    for item in files:
        path = safe_path(str(item["path"]))
        content = str(item.get("content", "")).rstrip() + "\n"

        _print_section(f"WRITE: {path}")
        write_text(path, content)
        print(f"OK: wrote {path}")
        results.append(_ok(path, message=f"Wrote {path}"))

    return results
