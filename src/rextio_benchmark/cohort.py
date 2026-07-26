from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from .readme_blocks import HEADLINE_ROWS
from .verification import GateError

POLICY_VERSION = 1
REPORT_COUNT = 3
STABILITY_THRESHOLD = 0.10

# Released 0.1.0 complete case set (pre-candidate diagnostic expansion).
RELEASED_CPU_COMPLETE_CASE_IDS = frozenset(
    {
        "core-hybrid",
        "core-native-executable",
        "numpy-mixed-fusion",
        "numpy-blas-dot-negative-control",
        "networkx-dijkstra",
        "pandas-series-map",
        "torch-cpu-deep-mlp",
        "tensorflow-cpu-eager-chain",
    }
)

# Pre-measurement candidate complete case set for plugin 0.1.3 pins.
CANDIDATE_PLUGIN_013_COMPLETE_CASE_IDS = frozenset(
    {
        *RELEASED_CPU_COMPLETE_CASE_IDS,
        "numpy-mixed-nonfused-phase1",
    }
)

HEADLINE_CASE_IDS = frozenset(case_id for _, case_id in HEADLINE_ROWS)

DIAGNOSTIC_CASE_IDS = frozenset(
    {
        "core-native-executable",
        "numpy-blas-dot-negative-control",
        "numpy-mixed-nonfused-phase1",
    }
)

# Exact Git revisions for unreleased candidate plugin builds.
# These are NOT PyPI rextio-numpy 0.1.3 or rextio-tensorflow 0.1.3 releases.
CANDIDATE_PLUGIN_PINS: dict[str, dict[str, str]] = {
    "rextio-numpy": {
        "version": "0.1.3",
        "git_url": "https://github.com/rextio/rextio-numpy",
        "rev": "7316c47393a86f1c701049b878d01e8d8f561cdb",
    },
    "rextio-tensorflow": {
        "version": "0.1.3",
        "git_url": "https://github.com/rextio/rextio-tensorflow",
        "rev": "346ca58148ed2563d4c7547dd8443d60cd4f905b",
    },
}

CANDIDATE_COHORT_POLICY: dict[str, Any] = {
    "policy_id": "candidate-plugin-0.1.3-pre-measurement",
    "policy_version": POLICY_VERSION,
    "status": "pre-measurement",
    "selection": "chronological-first",
    "report_count": REPORT_COUNT,
    "stability_threshold_fraction": STABILITY_THRESHOLD,
    "complete_case_ids": sorted(CANDIDATE_PLUGIN_013_COMPLETE_CASE_IDS),
    # Preserve HEADLINE_ROWS order (not alphabetical sorted-set order).
    "headline_case_ids": [case_id for _, case_id in HEADLINE_ROWS],
    "diagnostic_case_ids": sorted(DIAGNOSTIC_CASE_IDS),
    "candidate_plugins": CANDIDATE_PLUGIN_PINS,
    "notes": (
        "Second frozen cohort definition for commit-pinned rextio-numpy and "
        "rextio-tensorflow 0.1.3 candidates. Not yet measured; invents no "
        "performance numbers. Phase1 is diagnostic only and is not a fusion claim."
    ),
}

# Byte-frozen published cohorts remain verifiable against their original case set.
FROZEN_CANONICAL_COHORTS: dict[str, dict[str, Any]] = {
    "15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8": {
        "policy_id": "released-cpu-0.1.0",
        "policy_version": POLICY_VERSION,
        "complete_case_ids": frozenset(RELEASED_CPU_COMPLETE_CASE_IDS),
        "measurement_commit": "ff7f4fea34199d850bed0446a8a223ef730ddf17",
        "evidence_commit": "e62a3f8fb1637f52288873fb077ba4efba0ead59",
    },
}

# Sorted path:sha256 fingerprint of the frozen released cohort tree contents.
RELEASED_CANONICAL_COHORT_DIR = (
    "results/canonical/cohort-15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8"
)
RELEASED_CANONICAL_COHORT_TREE_SHA256 = (
    "b548eb97c30ddd3a38a7353cc9bc4091a5cee29cb86a077b1a375f3c22b4bd42"
)
RELEASED_CANONICAL_COHORT_FILE_COUNT = 60


def _evidence_declarations(report: dict[str, Any]) -> dict[str, Any]:
    return {
        case["id"]: {role: record for role, record in sorted(case["gate"]["evidence"].items())}
        for case in report["cases"]
    }


def _package_versions(report: dict[str, Any]) -> dict[str, Any]:
    return {case["id"]: case["packages"] for case in report["cases"]}


def cohort_id(report_sha256s: Sequence[str]) -> str:
    payload = {
        "policy_version": POLICY_VERSION,
        "report_sha256s": list(report_sha256s),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def expected_complete_case_ids(
    report: Mapping[str, Any],
    *,
    current_case_ids: frozenset[str],
) -> frozenset[str]:
    """Return the complete case set the report must match.

    Live measurement reports must cover the current manifests. Known frozen
    canonical cohorts keep their historical complete set so old reports stay
    verifiable after the candidate diagnostic case is added.

    Recognition is fail-closed: only an exact registered ``cohort_id`` or an
    exact registered ``measurement_commit`` (for raw three-run reports without
    a canonical bundle) unlocks a historical complete set. All other reports
    use the current complete case set.
    """
    metadata = report.get("canonical_bundle")
    if isinstance(metadata, Mapping):
        identifier = metadata.get("cohort_id")
        if isinstance(identifier, str) and identifier in FROZEN_CANONICAL_COHORTS:
            frozen = FROZEN_CANONICAL_COHORTS[identifier]["complete_case_ids"]
            return frozenset(frozen)
    repository = report.get("repository")
    if isinstance(repository, Mapping):
        commit = repository.get("commit")
        if isinstance(commit, str):
            for frozen in FROZEN_CANONICAL_COHORTS.values():
                if frozen.get("measurement_commit") == commit:
                    return frozenset(frozen["complete_case_ids"])
    return frozenset(current_case_ids)


def validate_cohort(reports: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if len(reports) != REPORT_COUNT:
        raise GateError("canonical cohort requires exactly three reports")
    first = reports[0]
    timestamps = [datetime.fromisoformat(report["generated_at"]) for report in reports]
    if any(left >= right for left, right in zip(timestamps, timestamps[1:], strict=False)):
        raise GateError("cohort report paths must be in strict chronological order")
    for report in reports:
        if report["mode"] != "publish" or report["publishable"] is not True:
            raise GateError("every cohort report must be verified and publishable")
        if any(not case["eligible"] or case["blockers"] for case in report["cases"]):
            raise GateError("every cohort case must be eligible without blockers")

    identities = {
        "repository_commit": first["repository"]["commit"],
        "system": first["system"],
        "configuration": first["configuration"],
        "toolchain": first["system"].get("toolchain"),
        "packages": _package_versions(first),
        "case_ids": [case["id"] for case in first["cases"]],
        "evidence": _evidence_declarations(first),
    }
    for report in reports[1:]:
        candidate = {
            "repository_commit": report["repository"]["commit"],
            "system": report["system"],
            "configuration": report["configuration"],
            "toolchain": report["system"].get("toolchain"),
            "packages": _package_versions(report),
            "case_ids": [case["id"] for case in report["cases"]],
            "evidence": _evidence_declarations(report),
        }
        if candidate != identities:
            raise GateError("cohort reports differ in frozen run identity")

    stability: dict[str, Any] = {}
    for case_id in identities["case_ids"]:
        values = [
            next(case for case in report["cases"] if case["id"] == case_id)["paired"][
                "median_speedup"
            ]
            for report in reports
        ]
        if any(not math.isfinite(value) or value <= 0 for value in values):
            raise GateError(f"{case_id} has a non-finite or non-positive speedup")
        median = float(statistics.median(values))
        deviations = [abs(value - median) / median for value in values]
        maximum = max(deviations)
        headline_gate = case_id in HEADLINE_CASE_IDS
        within_threshold = maximum <= STABILITY_THRESHOLD + 1e-12
        if headline_gate and not within_threshold:
            raise GateError(
                f"{case_id} cohort deviation {maximum:.6f} exceeds {STABILITY_THRESHOLD:.2f}"
            )
        stability[case_id] = {
            "median_speedups": values,
            "three_run_median": median,
            "relative_deviations": deviations,
            "maximum_relative_deviation": maximum,
            "headline_gate": headline_gate,
            "within_threshold": within_threshold,
        }
    return {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "selection": "chronological-first",
        "selected_report_index": 0,
        "report_count": REPORT_COUNT,
        "measurement_commit": identities["repository_commit"],
        "stability_threshold_fraction": STABILITY_THRESHOLD,
        "cases": stability,
    }


def tree_fingerprint(root: Any) -> tuple[str, int]:
    """Return (sha256 of sorted path:digest lines, file count) for *root*."""
    from pathlib import Path

    path = Path(root)
    lines: list[str] = []
    for file_path in sorted(path.rglob("*")):
        if not file_path.is_file():
            continue
        digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
        relative = file_path.relative_to(path).as_posix()
        lines.append(f"{relative}:{digest}")
    payload = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), len(lines)
