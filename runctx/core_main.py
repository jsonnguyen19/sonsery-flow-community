"""Entry point for runctx_core (called via subprocess from watchctx runner)."""

import json
import sys
from pathlib import Path

from .dispatcher import process_payload
from .max_response import apply_max_response
from .payload import load_payload


def main():
    """Main entry point for runctx core."""
    if len(sys.argv) < 3:
        print("Usage: python runctx_core.py <input_file> <output_file>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    tmp_path = Path(sys.argv[2])

    # Read payload from input file
    try:
        raw = input_path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as e:
        print(f"ERROR: Failed to read input: {e}")
        sys.exit(1)

    # Parse payload
    data = load_payload(raw)

    # Process payload
    success, data_items, error_msg = process_payload(data)

    # Optional payload `maxResponse`: trim bulk text and tell the AI what is missing
    data_items, max_response_notice = apply_max_response(data, data_items)

    # Write output
    output = {"success": success, "data": data_items, "error": error_msg}
    if max_response_notice:
        output["max_response"] = max_response_notice

    with tmp_path.open("w", encoding="utf-8", newline="\n") as out:
        json.dump(output, out, ensure_ascii=False, indent=2)

    print("BATCH_DONE")


if __name__ == "__main__":
    main()
