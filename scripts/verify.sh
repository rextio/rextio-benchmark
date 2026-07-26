#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="${1:-}"
unset PYTHONHOME

if [[ -z "$REPORT" ]]; then
  echo "usage: scripts/verify.sh <report>" >&2
  exit 1
fi

export PYTHONPATH="$ROOT/src"
exec "$ROOT/profiles/base/.venv/bin/python" -m rextio_benchmark verify "$REPORT"
