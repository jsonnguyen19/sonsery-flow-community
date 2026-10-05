"""maxResponse: optional per-payload cap on the size of the result.

AI chat web apps limit how much text can be pasted into the input box. A
payload may declare `"maxResponse": <estimated tokens>` (same style as `mode`).
When the result would be larger, the server trims bulk text (shell output, file
content) at line boundaries and tells the AI exactly what is missing, so the AI
sends a follow-up payload for the rest instead of breaking the automation flow.

Self-contained on purpose. The only hooks are `validate_max_response` (payload
parsing) and `apply_max_response` (right after a payload is processed).
"""

from __future__ import annotations

import json
from typing import Any, Dict

__all__ = ["apply_max_response", "get_max_response", "validate_max_response"]

MAX_RESPONSE_KEY = "maxResponse"

# Token estimate (~4 chars / token). Kept local so this module has no
# dependency on `constants.py`.
_TOKEN_CHARS = 4

# Only these tools return bulk text. replace/write results are tiny confirmations
# of side effects that already happened, so they are never trimmed.
_TRIMMABLE_TOOLS = ("shell", "read")

# Result-item fields that carry bulk text (shell -> output, read -> content).
_TEXT_FIELDS = ("output", "content")

# Chars kept free for the outer wrapper (success/error/id) and the notice.
_RESERVED_CHARS = 400

# Chars reserved per trimmed item for its `truncated` metadata.
_META_CHARS = 200

_HINT = (
    "Result was cut to fit maxResponse. Items with a 'truncated' field are "
    "incomplete: send a NEW payload for the rest (read: start=next_start and "
    "drop the old end; if next_start is absent, use a narrower shell command; "
    "shell: sed -n, head, tail or grep -n). Never assume the missing part."
)

Item = Dict[str, Any]


def _valid(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def validate_max_response(data: dict[str, Any]) -> str | None:
    """Return an error message when `maxResponse` is present but invalid."""
    value = data.get(MAX_RESPONSE_KEY)
    if value is None or _valid(value):
        return None
    return f"'{MAX_RESPONSE_KEY}' must be a positive integer (got {value!r})"


def get_max_response(payload: Any) -> int:
    """Return the cap in estimated tokens, or 0 when absent/invalid."""
    if not isinstance(payload, dict):
        return 0
    value = payload.get(MAX_RESPONSE_KEY)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0


def _json_len(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False))


def _trim_lines(text: str, budget: int) -> tuple[str, int, int]:
    """Keep leading whole lines whose JSON size fits `budget`.

    Returns (kept_text, shown_lines, total_lines). A first line bigger than the
    whole budget (e.g. a minified file) is hard-cut by characters and counts as
    0 shown lines.
    """
    lines = text.splitlines()
    kept: list[str] = []
    used = 0
    for line in lines:
        # escaped line + 2 quote chars ~ line + the 2-char newline joiner
        cost = _json_len(line)
        if used + cost > budget:
            break
        kept.append(line)
        used += cost
    if not kept and lines and budget > 0:
        return lines[0][:budget], 0, len(lines)
    return "\n".join(kept), len(kept), len(lines)


def _text_field(item: Item) -> str | None:
    for field in _TEXT_FIELDS:
        if isinstance(item.get(field), str):
            return field
    return None


def _trim_item(item: Item, share: int, spec: Item | None) -> tuple[Item, Item | None]:
    """Trim one result item to roughly `share` chars. Returns (item, meta|None)."""
    field = _text_field(item)
    if field is None or _json_len(item) <= share:
        return item, None

    text = item[field]
    overhead = _json_len({**item, field: ""}) + _META_CHARS
    kept, shown, total = _trim_lines(text, max(0, share - overhead))
    meta: Item = {
        "shown_lines": shown,
        "total_lines": total,
        "remaining_lines": total - shown,
        "remaining_tokens_est": max(0, len(text) - len(kept)) // _TOKEN_CHARS,
    }
    # Only emit next_start when at least one whole line was kept: on a
    # hard-cut (shown==0, e.g. a single huge line) the follow-up must switch
    # to a narrower shell command, not re-read the same range.
    if spec is not None and shown > 0:
        meta["next_start"] = int(spec.get("start") or 1) + shown
    return {**item, field: kept, "truncated": meta}, meta


def _read_specs(payload: dict[str, Any]) -> list[Item]:
    """Per-result request spec for `read` (results come back 1:1 with files)."""
    files = payload.get("files")
    if isinstance(files, list):
        return [f if isinstance(f, dict) else {} for f in files]
    return [payload]


def apply_max_response(payload: Any, items: Any) -> tuple[Any, Item | None]:
    """Trim `items` (a tool result list) to the payload's `maxResponse`.

    Budget is shared fairly: each item may use at most (remaining budget /
    items left), so small results free space for the big ones after them.
    Returns (items, notice). `notice` is None when nothing was cut.
    """
    limit = get_max_response(payload)
    if not limit or not isinstance(items, list):
        return items, None
    tool = payload.get("tool")
    if tool not in _TRIMMABLE_TOOLS:
        return items, None

    # Trigger threshold: cut only when the raw result genuinely exceeds the
    # requested token cap. The reserved headroom below is applied to the
    # trimming budget (so the trimmed output leaves room for the wrapper +
    # notice), never to the trigger — otherwise a result already under the
    # cap could still be cut.
    before = _json_len(items)
    if before <= limit * _TOKEN_CHARS:
        return items, None
    budget = max(0, limit * _TOKEN_CHARS - _RESERVED_CHARS)

    specs = _read_specs(payload) if tool == "read" else []
    trimmed: list[Any] = []
    cut = 0
    remaining = budget
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            trimmed.append(item)
            remaining -= _json_len(item)
            continue
        share = max(0, remaining) // (len(items) - index)
        spec = specs[index] if index < len(specs) else None
        new_item, meta = _trim_item(item, share, spec)
        if meta:
            cut += 1
        remaining -= _json_len(new_item)
        trimmed.append(new_item)

    if not cut:
        return items, None
    notice = {
        "limit_tokens": limit,
        "estimated_tokens_before": before // _TOKEN_CHARS,
        "truncated_items": cut,
        "hint": _HINT,
    }
    return trimmed, notice
