#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-}"

if [[ "$MODE" != "quick" && "$MODE" != "publish" && "$MODE" != "cohort" ]]; then
  echo "usage: scripts/run.sh quick|publish|cohort" >&2
  exit 1
fi

LOG="$(mktemp "${TMPDIR:-/tmp}/rextio-benchmark.XXXXXX")"
cleanup() {
  rm -f "$LOG"
}
trap cleanup EXIT

verify_mode() {
  local report="$1"
  local mode="$2"
  "$ROOT/scripts/verify.sh" "$report"
  "$ROOT/profiles/base/.venv/bin/python" - "$report" "$mode" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
mode = sys.argv[2]
report = json.loads(report_path.read_text(encoding="utf-8"))
publishable = report.get("publishable")
expected = mode == "publish"
if publishable is not expected:
    raise SystemExit(
        f"error: {mode} run has publishable={publishable!r}; expected {expected!r}"
    )
PY
}

run_one() {
  local mode="$1"
  : >"$LOG"
  "$ROOT/scripts/benchmark.sh" cpu "$mode" | tee "$LOG"

  local report
  report="$(sed -n '1p' "$LOG")"
  case "$report" in
    "$ROOT"/results/local/benchmark-"$mode"-*.json) ;;
    *)
      echo "error: benchmark did not return the expected local report path" >&2
      exit 3
      ;;
  esac
  if [[ ! -f "$report" ]]; then
    echo "error: benchmark report is missing: $report" >&2
    exit 3
  fi

  verify_mode "$report" "$mode"
  echo "$report"
}

"$ROOT/scripts/bootstrap.sh" cpu
"$ROOT/scripts/build.sh" cpu

if [[ "$MODE" == "cohort" ]]; then
  REPORTS=()
  for _attempt in 1 2 3; do
    REPORTS+=("$(run_one publish | tail -n 1)")
  done
  export PYTHONPATH="$ROOT/src"
  "$ROOT/profiles/base/.venv/bin/python" -m rextio_benchmark cohort "${REPORTS[@]}"
else
  REPORT="$(run_one "$MODE" | tail -n 1)"
  echo "verified $MODE report: $REPORT"
fi
