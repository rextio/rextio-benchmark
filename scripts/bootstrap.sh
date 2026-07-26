#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLATFORM="${1:-}"
unset PYTHONPATH
unset PYTHONHOME

if [[ "$PLATFORM" != "cpu" ]]; then
  echo "usage: scripts/bootstrap.sh cpu" >&2
  exit 1
fi
for command in uv cargo rustc; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "error: required command is missing: $command" >&2
    exit 2
  fi
done

for profile in base torch-cpu tensorflow-cpu; do
  echo "syncing profiles/$profile"
  uv sync --project "$ROOT/profiles/$profile" --locked --python 3.11
  "$ROOT/profiles/$profile/.venv/bin/python" -c \
    'import sys; assert sys.version_info[:2] == (3, 11), sys.version'
done

echo "CPU profiles are ready."
