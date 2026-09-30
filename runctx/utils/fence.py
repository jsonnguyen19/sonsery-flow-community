"""Code fence extraction helpers.

Two functions with intentionally different behavior:
- `extract_code_fence` (watchctx): simple fence strip, never exits.
- `strip_code_fence` (runctx_core): regex + sys.exit(1) on RUNCTX_RESULT.

Both are public (no underscore) because the `watchctx.py` facade re-exports them.
"""

import re
import sys


def extract_code_fence(text: str) -> str:
    trimmed = text.strip()
    if not trimmed.startswith("```"):
        return trimmed

    lines = trimmed.splitlines()
    if len(lines) < 2:
        return trimmed

    lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines).strip()


def strip_code_fence(raw: str) -> str:
    """Extract content from markdown code fence."""
    text = raw.strip()

    # Check for RUNCTX_RESULT marker
    if text.startswith("RUNCTX_RESULT"):
        print("ERROR: Clipboard contains RUNCTX_RESULT, not a runctx payload.")
        sys.exit(1)

    # Extract from code fence
    match = re.search(
        r"```(?:json|yaml|yml|zsh|bash|sh)?\s*\n([\s\S]*?)\n```",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return text


__all__ = ["extract_code_fence", "strip_code_fence"]
