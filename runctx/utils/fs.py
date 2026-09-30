"""Filesystem helpers: safe_path, read/write text, read_file_range."""

import sys
from pathlib import Path
from typing import Optional

# Default excluded directories for search/read operations
# (library/vendor code, build output, Python virtualenvs & tool caches)
EXCLUDED_DIRS = {
    "node_modules",
    "vendor",
    ".git",
    "dist",
    "build",
    "coverage",
    ".next",
    "out",
    # Python virtual environments
    "venv",
    ".venv",
    ".venv-test",
    "venv-test",
    # Python caches / tooling
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    "htmlcov",
    ".ipynb_checkpoints",
}


def _is_excluded_path(path: Path) -> bool:
    """Check if path contains any excluded directory."""
    return any(part in EXCLUDED_DIRS for part in path.parts)


def safe_path(value: str) -> Path:
    """Validate path to prevent directory traversal and excluded dirs.

    Default: only relative paths inside pwd are allowed; absolute paths, '..',
    and excluded dirs (node_modules, venv, ...) are all blocked.
    """
    path = Path(value)
    if path.is_absolute():
        print(f"ERROR: absolute paths are not allowed: {value}")
        sys.exit(1)
    if ".." in path.parts:
        print(f"ERROR: parent traversal is not allowed: {value}")
        sys.exit(1)
    if _is_excluded_path(path):
        excluded_part = next(part for part in path.parts if part in EXCLUDED_DIRS)
        print(f"ERROR: path contains excluded directory '{excluded_part}': {value}")
        print("HINT: To access vendor/library code, use explicit shell command instead")
        sys.exit(1)
    return path


def read_text(path: Path) -> str:
    """Read file with error handling."""
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    """Write file with directory creation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def read_file_range(path: Path, start: Optional[int], end: Optional[int]) -> str:
    """Read specific line range from file."""
    lines = read_text(path).splitlines()
    start_line = max(1, int(start or 1))
    end_line = min(len(lines), int(end or len(lines)))
    if start_line > end_line:
        return ""
    selected = lines[start_line - 1 : end_line]
    return "\n".join(f"{idx}: {line}" for idx, line in enumerate(selected, start=start_line))
