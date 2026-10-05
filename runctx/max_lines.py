"""maxLines: optional per-payload cap on how many text lines a result may return.

AI chat web apps limit how much text can be pasted into the input box (ChatGPT
refuses input beyond roughly 2000 lines). Lines are a unit that both the user and
the AI understand, so a payload may declare `"maxLines": <n>`: the server returns
at most <n> lines of bulk text (shell `output`, read `content`) in total, shares the
budget fairly between items, and tells the AI exactly what is missing so it can
send a follow-up payload instead of breaking the automation flow.

A secondary char cap (`_CHARS_PER_LINE` per allowed line) protects against a few
huge lines, e.g. a minified bundle, that would still blow the input limit.

Self-contained on purpose. The only hooks are `validate_max_lines` (payload
parsing) and `apply_max_lines` (right after a payload is processed).
"""

from __future__ import annotations

from typing import Any, Dict

__all__ = ["apply_max_lines", "get_max_lines", "validate_max_lines"]

MAX_LINES_KEY = "maxLines"

# Only these tools return bulk text. replace/write results are tiny confirmations
# of side effects that already happened, so they are never trimmed.
_TRIMMABLE_TOOLS = ("shell", "read")

# Result-item fields that carry bulk text (shell -> output, read -> content).
_TEXT_FIELDS = ("output", "content")

# Safety net for very long lines: allowed chars per allowed line.
_CHARS_PER_LINE = 160

_HINT = (
    "Result was cut to fit maxLines. Items with a 'truncated' field are "
    "incomplete: send a NEW payload for the rest (read: start=next_start and "
    "drop the old end; if next_start is absent, use a narrower shell command; "
    "shell: sed -n, head, tail or grep -n). Never assume the missing part."
)

Item = Dict[str, Any]


def _valid(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def validate_max_lines(data: dict[str, Any]) -> str | None:
    """Return an error message when `maxLines` is present but invalid."""
    value = data.get(MAX_LINES_KEY)
    if value is None or _valid(value):
        return None
    return f"'{MAX_LINES_KEY}' must be a positive integer (got {value!r})"


def get_max_lines(payload: Any) -> int:
    """Return the line cap, or 0 when absent/invalid."""
    if not isinstance(payload, dict):
        return 0
    value = payload.get(MAX_LINES_KEY)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0


def _ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def _text_field(item: Item) -> str | None:
    for field in _TEXT_FIELDS:
        if isinstance(item.get(field), str):
            return field
    return None


def _line_count(item: Any) -> int:
    if not isinstance(item, dict):
        return 0
    field = _text_field(item)
    return len(item[field].splitlines()) if field else 0


def _read_specs(payload: dict[str, Any]) -> list[Item]:
    """Per-result request spec for `read` (results come back 1:1 with files)."""
    files = payload.get("files")
    if isinstance(files, list):
        return [f if isinstance(f, dict) else {} for f in files]
    return [payload]


def _trim_item(
    item: Item, line_share: int, char_share: int, spec: Item | None
) -> tuple[Item, Item | None]:
    """Trim one result item to `line_share` lines / `char_share` chars."""
    field = _text_field(item)
    if field is None:
        return item, None
    text = item[field]
    lines = text.splitlines()
    if len(lines) <= line_share and len(text) <= char_share:
        return item, None

    kept: list[str] = []
    used = 0
    for line in lines:
        cost = len(line) + 1
        if len(kept) >= line_share or used + cost > char_share:
            break
        kept.append(line)
        used += cost

    shown = len(kept)
    if shown == 0 and lines and line_share > 0:
        # A first line bigger than the whole char budget (e.g. minified file):
        # hard-cut by characters, counts as 0 shown lines.
        cut_text = lines[0][:char_share]
    else:
        cut_text = "\n".join(kept)

    meta: Item = {
        "shown_lines": shown,
        "total_lines": len(lines),
        "remaining_lines": len(lines) - shown,
    }
    # next_start only when at least one whole line was kept: on a hard-cut the
    # follow-up must switch to a narrower shell command, not re-read the same range.
    if spec is not None and shown > 0:
        meta["next_start"] = int(spec.get("start") or 1) + shown
    return {**item, field: cut_text, "truncated": meta}, meta


def apply_max_lines(payload: Any, items: Any) -> tuple[Any, Item | None]:
    """Trim `items` (a tool result list) to the payload's `maxLines`.

    The line budget is shared fairly: each item may use at most
    ceil(remaining budget / items left), so small results free space for the big
    ones after them. Returns (items, notice); notice is None when nothing was cut.
    """
    limit = get_max_lines(payload)
    if not limit or not isinstance(items, list):
        return items, None
    tool = payload.get("tool")
    if tool not in _TRIMMABLE_TOOLS:
        return items, None

    specs = _read_specs(payload) if tool == "read" else []
    before = sum(_line_count(item) for item in items)
    remaining_lines = limit
    remaining_chars = limit * _CHARS_PER_LINE
    trimmed: list[Any] = []
    cut = 0
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            trimmed.append(item)
            continue
        left = len(items) - index
        spec = specs[index] if index < len(specs) else None
        new_item, meta = _trim_item(
            item,
            _ceil_div(max(0, remaining_lines), left),
            _ceil_div(max(0, remaining_chars), left),
            spec,
        )
        if meta:
            cut += 1
        field = _text_field(new_item)
        if field:
            kept = new_item[field]
            remaining_lines -= len(kept.splitlines())
            remaining_chars -= len(kept)
        trimmed.append(new_item)

    if not cut:
        return items, None
    notice = {
        "limit_lines": limit,
        "total_lines_before": before,
        "truncated_items": cut,
        "hint": _HINT,
    }
    return trimmed, notice
