import json
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest

from rextio_benchmark.models import load_cases
from rextio_benchmark.report import render_markdown, run_suite
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
    # publishable=true is non-released and therefore requires the full candidate
    # binding before the recomputed-publishability gate runs.
    with pytest.raises(GateError, match="full frozen candidate plugin set|publishability"):
        verify_report(path, ROOT)


def _blocked_case_result(
    case_id: str,
    packages: dict[str, str],
    *,
    package_provenance: dict | None = None,
) -> dict:
    result = {
        "id": case_id,
        "project": "fixture",
        "description": "fixture",
        "context": None,
        "negative_control": False,
        "kind": "python-module",
        "output_table": {},
        "timing_contract": None,
        "gate": None,
        "correctness": {"status": "blocked"},
        "lanes": {},
        "paired": None,
        "eligible": False,
        "blockers": ["fixture-blocker"],
        "packages": packages,
        "python": None,
        "environment": {},
    }
    if package_provenance is not None:
        result["package_provenance"] = package_provenance
    return result


def test_run_suite_allows_heterogeneous_unrelated_package_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Isolated-profile numpy/networkx differences must not abort run_suite."""
    cases = [
        SimpleNamespace(
            benchmark_id="numpy-mixed-fusion",
            kind="python-module",
            profile="base",
            project="numpy",
            raw={"description": "n", "context": None, "negative_control": False},
        ),
        SimpleNamespace(
            benchmark_id="tensorflow-cpu-eager-chain",
            kind="python-module",
            profile="tensorflow-cpu",
            project="tensorflow-cpu",
            raw={"description": "t", "context": None, "negative_control": False},
        ),
    ]
    results = {
        "numpy-mixed-fusion": _blocked_case_result(
            "numpy-mixed-fusion",
            {
                "numpy": "2.3.5",
                "networkx": "3.5",
                "rextio": "0.1.6",
                "rextio-numpy": "0.1.3",
            },
        ),
        "tensorflow-cpu-eager-chain": _blocked_case_result(
            "tensorflow-cpu-eager-chain",
            {
                "numpy": "2.4.6",
                "networkx": "3.6.1",
                "rextio": "0.1.6",
                "rextio-tensorflow": "0.1.3",
            },
        ),
    }

    monkeypatch.setattr("rextio_benchmark.report.load_cases", lambda root: cases)
    monkeypatch.setattr(
        "rextio_benchmark.report.profile_python",
        lambda root, profile: tmp_path / "python",
    )
    (tmp_path / "python").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "rextio_benchmark.report.run_module_case",
        lambda root, python, case, mode: results[case.benchmark_id],
    )
    monkeypatch.setattr(
        "rextio_benchmark.report._repository_state",
        lambda root: {"commit": "a" * 40, "dirty": True},
    )
    monkeypatch.setattr("rextio_benchmark.report._toolchain", lambda: {})
    monkeypatch.setattr(
        "rextio_benchmark.report._host_identity",
        lambda: {"model": "fixture", "cpu_brand": "fixture"},
    )
    monkeypatch.setattr("rextio_benchmark.report._build_receipt", lambda root: None)
    (tmp_path / "results" / "local").mkdir(parents=True)

    report, path = run_suite(tmp_path, "quick")
    assert path.is_file()
    assert report["mode"] == "quick"
    # Per-case packages preserved with heterogeneous unrelated deps.
    by_id = {case["id"]: case["packages"] for case in report["cases"]}
    assert by_id["numpy-mixed-fusion"]["numpy"] == "2.3.5"
    assert by_id["tensorflow-cpu-eager-chain"]["numpy"] == "2.4.6"
    assert "package_provenance" not in report["cases"][0]


def test_run_suite_fails_closed_on_candidate_plugin_version_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cases = [
        SimpleNamespace(
            benchmark_id="numpy-mixed-fusion",
            kind="python-module",
            profile="base",
            project="numpy",
            raw={"description": "n", "context": None, "negative_control": False},
        ),
        SimpleNamespace(
            benchmark_id="numpy-blas-dot-negative-control",
            kind="python-module",
            profile="base",
            project="numpy",
            raw={"description": "b", "context": None, "negative_control": True},
        ),
    ]
    results = {
        "numpy-mixed-fusion": _blocked_case_result(
            "numpy-mixed-fusion",
            {"rextio-numpy": "0.1.3", "numpy": "2.3.5"},
        ),
        "numpy-blas-dot-negative-control": _blocked_case_result(
            "numpy-blas-dot-negative-control",
            {"rextio-numpy": "0.1.2", "numpy": "2.3.5"},
        ),
    }
    monkeypatch.setattr("rextio_benchmark.report.load_cases", lambda root: cases)
    monkeypatch.setattr(
        "rextio_benchmark.report.profile_python",
        lambda root, profile: tmp_path / "python",
    )
    (tmp_path / "python").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "rextio_benchmark.report.run_module_case",
        lambda root, python, case, mode: results[case.benchmark_id],
    )
    monkeypatch.setattr(
        "rextio_benchmark.report._repository_state",
        lambda root: {"commit": "a" * 40, "dirty": True},
    )
    with pytest.raises(RuntimeError, match="package version conflict for rextio-numpy"):
        run_suite(tmp_path, "quick")


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
