#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLATFORM="${1:-}"
unset PYTHONHOME

if [[ "$PLATFORM" != "cpu" ]]; then
  echo "usage: scripts/build.sh cpu" >&2
  exit 1
fi

export PYTHONPATH="$ROOT/src"
exec "$ROOT/profiles/base/.venv/bin/python" -m rextio_benchmark build cpu
