#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLATFORM="${1:-}"
MODE="${2:-}"
unset PYTHONHOME

if [[ "$PLATFORM" != "cpu" ]] || [[ "$MODE" != "quick" && "$MODE" != "publish" ]]; then
  echo "usage: scripts/benchmark.sh cpu quick|publish" >&2
  exit 1
fi

export PYTHONPATH="$ROOT/src"
exec "$ROOT/profiles/base/.venv/bin/python" -m rextio_benchmark benchmark cpu "$MODE"
