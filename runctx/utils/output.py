"""Output normalization helpers."""

from __future__ import annotations


def normalize_output(text: str, limit: int | None = None) -> str:
    """Return the output unchanged. The `limit` param is kept only for
    backward compat with old callers; when limit=None (default) nothing is
    truncated.

    Local tool: no truncation needed, return everything.
    """
    if limit is None or len(text) <= limit:
        return text
    return "\n".join(
        [
            f"... output truncated to last {limit} chars ...",
            text[-limit:],
        ]
    )


# Chars signalling non-prose content (path, JSON, code, URL, ...).
# If encountered before the first letter -> do not lowercase.
_NON_PROSE_PREFIX = set("/\\.,={}[]()<>:;#@$%|&*,!?'`~^+")


def lowercase_first(text: str) -> str:
    r"""Lowercase the first letter of a prose log line.

    Safe with:
    - ANSI escape codes (skipped).
    - Leading unicode icons / box drawing / whitespace (skipped).
    - File paths (e.g. `/home/File.txt`) -> unchanged.
    - ACRONYMS / identifiers / filenames (e.g. README, RUNCTX, OK) -> unchanged.
    - JSON / code / URL starting with non-prose adjacent to alpha (e.g. `{a`, `[x`, `/path`) -> unchanged.
    - Version strings / numeric prefixes + punctuation + space (e.g. `v1.2.3 Release`) -> still lowercased.

    Only lowercases when:
    1. The first alpha char is UPPERCASE.
    2. The second alpha char (if any) is lowercase (i.e. a Capitalized word,
       not an ACRONYM/identifier).
    3. The char immediately BEFORE the first alpha is not non-prose (no path
       separator / punctuation glued to the alpha). A space in between still
       counts as prose (e.g. `- Release` -> lowered).
    """
    if not text:
        return text
    i = 0
    n = len(text)
    first_alpha_idx: int | None = None
    # True if the char immediately before first alpha (ignoring ANSI) is non-prose.
    prev_non_prose_adjacent = False
    while i < n:
        c = text[i]
        # Skip ANSI escape sequence: ESC [ ... <letter>
        if c == "\x1b":
            j = i + 1
            while j < n and not text[j].isalpha():
                j += 1
            i = j + 1 if j < n else n
            continue
        if c.isalpha():
            first_alpha_idx = i
            break
        if c.isspace():
            # Space in between -> reset the "adjacent" flag.
            prev_non_prose_adjacent = False
        elif c in _NON_PROSE_PREFIX:
            # Non-prose adjacent -> mark, keep scanning; bail out only
            # if an alpha follows immediately (no space in between).
            prev_non_prose_adjacent = True
        else:
            # Other chars (digit, emoji, box-drawing, ...) -> not non-prose.
            prev_non_prose_adjacent = False
        i += 1

    if first_alpha_idx is None:
        return text

    # If non-prose sits immediately BEFORE alpha (no space) -> bail out.
    if prev_non_prose_adjacent:
        return text

    first = text[first_alpha_idx]
    if not first.isupper():
        return text

    # Find the next alpha char (skipping non-alpha and ANSI).
    j = first_alpha_idx + 1
    while j < n:
        cj = text[j]
        if cj == "\x1b":
            k = j + 1
            while k < n and not text[k].isalpha():
                k += 1
            j = k + 1 if k < n else n
            continue
        if cj.isalpha():
            if cj.islower():
                # Capitalized word -> lowercase the first char.
                return text[:first_alpha_idx] + first.lower() + text[first_alpha_idx + 1 :]
            # Upper followed by upper -> ACRONYM -> unchanged.
            return text
        # Non-alpha char in between -> not a single contiguous word,
        # treat as ACRONYM/identifier -> unchanged.
        return text

    # Only one alpha char (e.g. "A") -> ambiguous, leave unchanged.
    return text
