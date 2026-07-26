from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from .verification import GateError

POLICY_VERSION = 1
REPORT_COUNT = 3
STABILITY_THRESHOLD = 0.10


def _evidence_declarations(report: dict[str, Any]) -> dict[str, Any]:
    return {
        case["id"]: {
            role: record
            for role, record in sorted(case["gate"]["evidence"].items())
        }
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
        if maximum > STABILITY_THRESHOLD + 1e-12:
            raise GateError(
                f"{case_id} cohort deviation {maximum:.6f} exceeds "
                f"{STABILITY_THRESHOLD:.2f}"
            )
        stability[case_id] = {
            "median_speedups": values,
            "three_run_median": median,
            "relative_deviations": deviations,
            "maximum_relative_deviation": maximum,
            "stable": True,
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
