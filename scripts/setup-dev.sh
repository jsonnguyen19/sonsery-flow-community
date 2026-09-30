#!/usr/bin/env bash
# ============================================================
# Setup dev environment for Sonsery Flow
# Create venv, install dev dependencies (pytest, ruff, basedpyright)
#
# Default index is the official PyPI. The Aliyun mirror is much slower
# for large wheels (e.g. nodejs-wheel-binaries is ~61 MB and can drop
# below 50 kB/s there, which looks like the install has hung).
#
# Override with env:
#   PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ bash scripts/setup-dev.sh
#   PIP_INDEX_URL="" bash scripts/setup-dev.sh   # force official PyPI
#
# Every pip call is wrapped in a hard timeout so the script can never
# hang forever on a slow mirror.
# ============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV=".venv-test"
PYTHON="${PYTHON:-python3}"

# Hard cap for each pip invocation (seconds). A slow mirror will be
# killed instead of hanging the terminal forever.
PIP_HARD_TIMEOUT="${PIP_HARD_TIMEOUT:-600}"

# Index: prefer env PIP_INDEX_URL, default to the official PyPI.
# Set PIP_INDEX_URL="" to explicitly use PyPI (same as default) — kept
# for backwards compatibility with the previous override contract.
DEFAULT_INDEX="https://pypi.org/simple/"
INDEX_URL="${PIP_INDEX_URL-$DEFAULT_INDEX}"

# pip network timeout / retries (per request, not the whole install).
PIP_ARGS=(--timeout 30 --retries 3)
if [ -n "$INDEX_URL" ]; then
  PIP_ARGS+=(-i "$INDEX_URL")
fi

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "❌ Cannot find $PYTHON. Install Python 3.8+ first."
  exit 1
fi

if ! command -v timeout >/dev/null 2>&1; then
  echo "⚠️  'timeout' command not found; install coreutils to enable the hard timeout."
  # Fall back to running pip directly (no hard cap).
  run_pip() { "$@"; }
else
  run_pip() { timeout "$PIP_HARD_TIMEOUT" "$@"; }
fi

if [ ! -d "$VENV" ]; then
  echo "📦 Creating venv at $VENV..."
  "$PYTHON" -m venv "$VENV"
fi

if [ -n "$INDEX_URL" ]; then
  echo "📥 Installing dev dependencies (index: $INDEX_URL)..."
else
  echo "📥 Installing dev dependencies (official PyPI)..."
fi
echo "   NOTE: basedpyright pulls nodejs-wheel-binaries (~61 MB). On a slow"
echo "   mirror this can take a while — a $PIP_HARD_TIMEOUT s hard timeout is applied."

# Do not use -q: keep the progress bar so it does not look "hung".
if ! run_pip "$VENV/bin/pip" install --upgrade pip "${PIP_ARGS[@]}"; then
  echo "❌ pip self-upgrade failed or timed out after ${PIP_HARD_TIMEOUT}s."
  echo "   Try a different index, e.g.:"
  echo "   PIP_INDEX_URL=https://pypi.org/simple/ bash scripts/setup-dev.sh"
  exit 1
fi

if ! run_pip "$VENV/bin/pip" install -r requirements-dev.txt "${PIP_ARGS[@]}"; then
  echo "❌ Dependency install failed or timed out after ${PIP_HARD_TIMEOUT}s."
  echo "   If a large wheel is stuck on a slow mirror, retry with the official PyPI:"
  echo "   PIP_INDEX_URL=https://pypi.org/simple/ bash scripts/setup-dev.sh"
  exit 1
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Available commands:"
echo "  pnpm lint        # ruff check"
echo "  pnpm format      # ruff format"
echo "  pnpm typecheck   # basedpyright"
echo "  pnpm test        # pytest"
echo "  pnpm check       # run everything"
echo ""
