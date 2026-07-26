import json
from pathlib import Path

import jsonschema
import pytest

from rextio_benchmark.models import load_cases
from rextio_benchmark.report import render_markdown
from rextio_benchmark.verification import GateError
from rextio_benchmark.verifier import verify_report

ROOT = Path(__file__).resolve().parents[1]


def blocked_quick_report() -> dict[str, object]:
    cases = []
    for case in load_cases(ROOT):
        cases.append(
            {
                "id": case.benchmark_id,
                "project": case.project,
                "description": case.raw["description"],
                "context": case.raw.get("context"),
                "negative_control": bool(case.raw.get("negative_control", False)),
                "kind": case.kind,
                "output_table": {},
                "timing_contract": None,
                "gate": None,
                "correctness": {"status": "blocked"},
                "lanes": {},
                "paired": None,
                "eligible": False,
                "blockers": ["fixture-blocker"],
                "packages": {},
                "python": None,
                "environment": {},
            }
        )
    return {
        "schema_version": 1,
        "generated_at": "2026-07-26T00:00:00+00:00",
        "mode": "quick",
        "publishable": False,
        "eligibility": {
            "status": "blocked",
            "blockers": ["quick-mode-is-never-publishable"],
        },
        "repository": {"commit": None, "dirty": True},
        "system": {"platform": "fixture"},
        "configuration": {
            "warmups": 1,
            "samples": 3,
            "minimum_sample_ns": 10000000,
            "pairs": 2,
            "bootstrap_resamples": 1000,
        },
        "build": None,
        "cases": cases,
    }


def test_schema_and_semantic_verifier_accept_blocked_quick_report(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(blocked_quick_report()), encoding="utf-8")
    verified = verify_report(path, ROOT)
    assert verified["publishable"] is False


def test_quick_report_cannot_claim_publishability(tmp_path: Path) -> None:
    report = blocked_quick_report()
    report["publishable"] = True
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(GateError, match="publishability"):
        verify_report(path, ROOT)


def test_schema_rejects_unknown_version(tmp_path: Path) -> None:
    report = blocked_quick_report()
    report["schema_version"] = 2
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(jsonschema.ValidationError):
        verify_report(path, ROOT)


def test_markdown_renderer_preserves_blockers() -> None:
    markdown = render_markdown(blocked_quick_report())
    assert "| Case | Source median | Native median | Median speedup | Status |" in markdown
    assert "quick-mode-is-never-publishable" in markdown
    assert "Core executable row includes process startup" in markdown
    assert "Slower and negative-control results are intentionally preserved." in markdown


def test_readme_documents_simple_entrypoints() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for command in (
        "scripts/bootstrap.sh cpu",
        "scripts/build.sh cpu",
        "scripts/benchmark.sh cpu quick",
        "scripts/verify.sh",
    ):
        assert command in readme
    assert "manually vectorized pandas/NumPy rewrite may be faster" in readme
