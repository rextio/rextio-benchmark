from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from rextio_benchmark.build_runner import _run
from rextio_benchmark.bundler import bundle_cohort
from rextio_benchmark.cohort import cohort_id, validate_cohort
from rextio_benchmark.integration_targets import (
    TARGET_CONFIG_PATH,
    TARGET_POLICY_ID,
    integration_target_pins,
    parse_integration_targets,
)
from rextio_benchmark.portability import portable_value, require_portable
from rextio_benchmark.readme_blocks import (
    HEADLINE_ROWS,
    VerifiedStabilitySummary,
    generate_blocks,
)
from rextio_benchmark.report import _host_identity
from rextio_benchmark.verification import GateError, sha256_file

DIAGNOSTIC_CASES = (
    "core-native-executable",
    "numpy-blas-dot-negative-control",
    "numpy-mixed-nonfused-phase1",
)


def _verified_summary(report: dict) -> VerifiedStabilitySummary:
    return VerifiedStabilitySummary(
        document={
            "measurement_commit": report["repository"]["commit"],
            "cases": {
                case_id: {
                    "headline_gate": True,
                    "within_threshold": True,
                    "three_run_median": next(
                        case for case in report["cases"] if case["id"] == case_id
                    )["paired"]["median_speedup"],
                }
                for _, case_id in HEADLINE_ROWS
            },
        },
        logical_path="results/canonical/fixture/stability.json",
        sha256="0" * 64,
    )


def _report(timestamp: str, commit: str = "a" * 40) -> dict:
    cases = []
    for index, (_, case_id) in enumerate(HEADLINE_ROWS):
        speedup = 0.75 if index == 0 else 1.0 + index / 10
        cases.append(
            {
                "id": case_id,
                "eligible": True,
                "blockers": [],
                "packages": {"rextio": "0.1.6"},
                "gate": {
                    "evidence": {
                        "input": {
                            "kind": "run-input",
                            "path": f"cases/{case_id}/benchmark.json",
                            "sha256": "0" * 64,
                        },
                        "output": {
                            "kind": "run-output",
                            "path": f"cases/{case_id}/.rextio/reports/build.json",
                            "sha256": "1" * 64,
                        },
                    }
                },
                "lanes": {
                    "python-source": {"steady_state": {"median_ns": 2_000_000.0}},
                    "rextio-native": {"steady_state": {"median_ns": 3_000_000.0}},
                },
                "paired": {"median_speedup": speedup},
            }
        )
    for case_id in DIAGNOSTIC_CASES:
        cases.append(deepcopy(cases[0]))
        cases[-1]["id"] = case_id
        cases[-1]["gate"]["evidence"]["input"]["path"] = f"cases/{case_id}/benchmark.json"
        cases[-1]["gate"]["evidence"]["output"]["path"] = (
            f"cases/{case_id}/.rextio/reports/build.json"
        )
        cases[-1]["paired"]["median_speedup"] = 1.0
    return {
        "schema_version": 1,
        "generated_at": timestamp,
        "mode": "publish",
        "publishable": True,
        "repository": {"commit": commit, "dirty": False},
        "system": {
            "platform": "macOS-15",
            "machine": "arm64",
            "processor": "arm",
            "python_controller": "3.11.9",
            "toolchain": {"rustc": "rustc 1.88", "cargo": "cargo 1.88"},
            "host": {"model": "Mac15,8", "cpu_brand": "Apple M3 Pro"},
        },
        "configuration": {"pairs": 12},
        "cases": cases,
    }


def test_cohort_is_chronological_stable_and_not_fastest() -> None:
    reports = [
        _report("2026-07-26T00:00:00+00:00"),
        _report("2026-07-26T00:01:00+00:00"),
        _report("2026-07-26T00:02:00+00:00"),
    ]
    reports[1]["cases"][0]["paired"]["median_speedup"] = 0.80
    summary = validate_cohort(reports)
    assert summary["selected_report_index"] == 0
    assert summary["selection"] == "chronological-first"
    with pytest.raises(GateError, match="chronological"):
        validate_cohort([reports[1], reports[0], reports[2]])


def test_unstable_nonheadline_case_is_retained_without_veto() -> None:
    reports = [
        _report("2026-07-26T00:00:00+00:00"),
        _report("2026-07-26T00:01:00+00:00"),
        _report("2026-07-26T00:02:00+00:00"),
    ]
    negative = "numpy-blas-dot-negative-control"
    next(case for case in reports[1]["cases"] if case["id"] == negative)["paired"][
        "median_speedup"
    ] = 1.23
    summary = validate_cohort(reports)
    assert set(summary["cases"]) == {case_id for _, case_id in HEADLINE_ROWS} | set(
        DIAGNOSTIC_CASES
    )
    assert summary["cases"][negative]["headline_gate"] is False
    assert summary["cases"][negative]["within_threshold"] is False
    assert all(
        {"headline_gate", "within_threshold"} <= set(record) for record in summary["cases"].values()
    )
    assert summary["cases"][HEADLINE_ROWS[0][1]]["headline_gate"] is True
    assert summary["cases"][HEADLINE_ROWS[0][1]]["within_threshold"] is True


def test_unstable_headline_case_still_rejects() -> None:
    reports = [
        _report("2026-07-26T00:00:00+00:00"),
        _report("2026-07-26T00:01:00+00:00"),
        _report("2026-07-26T00:02:00+00:00"),
    ]
    next(case for case in reports[1]["cases"] if case["id"] == HEADLINE_ROWS[0][1])["paired"][
        "median_speedup"
    ] = 1.0
    with pytest.raises(GateError, match=HEADLINE_ROWS[0][1]):
        validate_cohort(reports)


def test_cohort_freezes_run_output_declarations() -> None:
    reports = [
        _report("2026-07-26T00:00:00+00:00"),
        _report("2026-07-26T00:01:00+00:00"),
        _report("2026-07-26T00:02:00+00:00"),
    ]
    reports[1]["cases"][0]["gate"]["evidence"]["output"]["sha256"] = "2" * 64
    with pytest.raises(GateError, match="frozen run identity"):
        validate_cohort(reports)


def test_bundle_cohort_copies_all_reports_and_hashes_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reports = [_report(f"2026-07-26T00:0{index}:00+00:00") for index in range(3)]
    root = Path(__file__).resolve().parents[1]
    ready_config = (root / TARGET_CONFIG_PATH).read_text(encoding="utf-8")
    pins = integration_target_pins(parse_integration_targets(ready_config))
    provenance = {
        name: {
            "version": pin["version"],
            "url": pin["git_url"],
            "vcs": "git",
            "commit_id": pin["rev"],
        }
        for name, pin in pins.items()
    }
    for report in reports:
        report["policy"] = {
            "policy_id": TARGET_POLICY_ID,
            "policy_version": 1,
            "status": "pre-measurement",
            "candidate_packages": pins,
        }
        report["package_provenance"] = provenance
    paths = []
    for index, report in enumerate(reports):
        path = tmp_path / "results/local" / f"{index}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report), encoding="utf-8")
        paths.append(path)
    digests = [sha256_file(path) for path in paths]
    expected_name = f"cohort-{cohort_id(digests)}"

    monkeypatch.setattr(
        "rextio_benchmark.bundler.verify_report",
        lambda path, root: reports[paths.index(path)],
    )
    monkeypatch.setattr("rextio_benchmark.bundler._current_commit", lambda root: "b" * 40)
    monkeypatch.setattr(
        "rextio_benchmark.bundler._run_commit_available",
        lambda root, run, current: run == "a" * 40 and current == "b" * 40,
    )
    monkeypatch.setattr("rextio_benchmark.bundler._worktree_clean", lambda root: True)

    def fake_bundle(path: Path, root: Path, *, name: str | None = None):
        assert name == expected_name
        destination = root / "results/canonical" / name
        destination.mkdir(parents=True)
        markdown = destination / "report.md"
        markdown.write_text("fixture markdown\n", encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "run_commit": "a" * 40,
            "source_report_path": "results/local/0.json",
            "canonical_report_path": f"results/canonical/{name}/report.json",
            "report_markdown_path": f"results/canonical/{name}/report.md",
            "report_markdown_sha256": sha256_file(markdown),
            "file_count": 1,
            "object_count": 1,
            "logical_bytes": 1,
            "stored_bytes": 1,
            "cases": {},
        }
        (destination / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        canonical = deepcopy(reports[0])
        canonical["canonical_bundle"] = {
            "manifest_path": f"results/canonical/{name}/manifest.json",
            "manifest_sha256": "0" * 64,
            "report_markdown_path": f"results/canonical/{name}/report.md",
            "report_markdown_sha256": sha256_file(markdown),
            "file_count": 1,
            "object_count": 1,
            "logical_bytes": 1,
            "stored_bytes": 1,
        }
        (destination / "report.json").write_text(json.dumps(canonical), encoding="utf-8")
        return destination / "report.json", destination / "manifest.json", {}

    monkeypatch.setattr("rextio_benchmark.bundler.bundle_report", fake_bundle)
    canonical, manifest, stability, _ = bundle_cohort(paths, tmp_path)
    assert canonical.parent.name == expected_name
    assert len(list((canonical.parent / "reports").glob("*.json"))) == 3
    document = json.loads(manifest.read_text(encoding="utf-8"))
    assert document["schema_version"] == 3
    assert document["cohort"]["selected_report_index"] == 0
    assert document["cohort"]["candidate_packages"] == pins
    assert document["cohort"]["package_provenance"] == provenance
    assert sha256_file(canonical.with_suffix(".md")) == document["report_markdown_sha256"]
    assert sha256_file(stability) == document["cohort"]["stability_summary_sha256"]
    for bundled_json in canonical.parent.rglob("*.json"):
        content = bundled_json.read_text(encoding="utf-8")
        assert str(tmp_path.resolve()) not in content
        assert str(Path.home().resolve()) not in content


def test_host_identity_uses_mac_sysctl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rextio_benchmark.report.platform.system", lambda: "Darwin")
    monkeypatch.setattr(
        "rextio_benchmark.report._command_text",
        lambda command, cwd: {
            "hw.model": "Mac15,8",
            "machdep.cpu.brand_string": "Apple M3 Pro",
        }[command[-1]],
    )
    assert _host_identity() == {"model": "Mac15,8", "cpu_brand": "Apple M3 Pro"}


def test_portability_removes_repository_and_home_paths(tmp_path: Path) -> None:
    home = tmp_path / "home"
    root = tmp_path / "workspace/rextio-benchmark"
    value = {
        "command": [str(root / "profiles/base/.venv/bin/rextio")],
        "stderr": f"at {root}/cases/core and {home}/.cargo/bin/cargo",
    }
    portable = portable_value(value, root, home)
    require_portable(portable, root, home)
    serialized = json.dumps(portable)
    assert str(root) not in serialized
    assert str(home) not in serialized


def test_build_receipt_sanitizes_commands_and_tails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = Path.home()
    monkeypatch.setattr(
        "rextio_benchmark.build_runner.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=f"built {tmp_path}/cases/fixture\n",
            stderr=f"cargo at {home}/.cargo/bin/cargo\n",
        ),
    )
    record = _run(
        [str(tmp_path / "profiles/base/.venv/bin/rextio"), "check"],
        {},
        tmp_path,
    )
    serialized = json.dumps(record)
    assert str(tmp_path.resolve()) not in serialized
    assert str(home.resolve()) not in serialized
    assert record["command"][0] == "profiles/base/.venv/bin/rextio"


def test_readme_blocks_keep_row_order_links_and_slow_values() -> None:
    from rextio_benchmark.cohort import CANDIDATE_COHORT_POLICY, CANDIDATE_PLUGIN_PINS

    report = _report("2026-07-26T00:00:00+00:00")
    for case in report["cases"]:
        case["packages"] = {
            "rextio": "0.1.6",
            "rextio-numpy": "0.1.3",
            "rextio-tensorflow": "0.1.3",
        }
    report["canonical_bundle"] = {
        "manifest_path": "results/canonical/cohort/manifest.json",
        "report_markdown_path": "results/canonical/cohort/report.md",
    }
    report["policy"] = {
        "policy_id": CANDIDATE_COHORT_POLICY["policy_id"],
        "policy_version": CANDIDATE_COHORT_POLICY["policy_version"],
        "status": "pre-measurement",
        "candidate_plugins": {
            name: {
                "version": pin["version"],
                "git_url": pin["git_url"],
                "rev": pin["rev"],
            }
            for name, pin in CANDIDATE_PLUGIN_PINS.items()
        },
    }
    report["package_provenance"] = {
        name: {
            "version": pin["version"],
            "url": pin["git_url"],
            "vcs": "git",
            "commit_id": pin["rev"],
            "requested_revision": pin["rev"],
        }
        for name, pin in CANDIDATE_PLUGIN_PINS.items()
    }
    blocks = generate_blocks(
        report,
        report_logical_path="results/canonical/cohort/report.json",
        measurement_commit="a" * 40,
        evidence_commit="b" * 40,
        github_url="https://github.com/rextio/rextio-benchmark",
        stability_summary=_verified_summary(report),
    )
    assert list(blocks) == [
        "README.md",
        "README.ko.md",
        "README.ja.md",
        "README.zh-hans.md",
        "README.zh-hant.md",
    ]
    version_labels = {
        "README.md": "Versions:",
        "README.ko.md": "버전:",
        "README.ja.md": "バージョン:",
        "README.zh-hans.md": "版本:",
        "README.zh-hant.md": "版本:",
    }
    for filename, block in blocks.items():
        assert version_labels[filename] in block
    for block in blocks.values():
        positions = [block.index(label) for label, _ in HEADLINE_ROWS]
        assert positions == sorted(positions)
        assert "pandas Series.map" in block
        assert "0.750×" in block
        assert "/blob/" + "b" * 40 in block
        assert "/report.md)" in block
        assert "/report.json)" not in block
        assert "/commit/" + "a" * 40 in block
        assert "numpy-mixed-nonfused-phase1" not in block
        assert "phase1" not in block.lower()


def test_readme_blocks_state_candidate_commit_caveats() -> None:
    from rextio_benchmark.cohort import CANDIDATE_COHORT_POLICY, CANDIDATE_PLUGIN_PINS

    report = _report("2026-07-26T00:00:00+00:00")
    for case in report["cases"]:
        case["packages"] = {
            "rextio": "0.1.6",
            "rextio-numpy": "0.1.3",
            "rextio-tensorflow": "0.1.3",
        }
    report["canonical_bundle"] = {
        "manifest_path": "results/canonical/cohort/manifest.json",
        "report_markdown_path": "results/canonical/cohort/report.md",
    }
    report["policy"] = {
        "policy_id": CANDIDATE_COHORT_POLICY["policy_id"],
        "policy_version": CANDIDATE_COHORT_POLICY["policy_version"],
        "status": "pre-measurement",
        "candidate_plugins": {
            name: {
                "version": pin["version"],
                "git_url": pin["git_url"],
                "rev": pin["rev"],
            }
            for name, pin in CANDIDATE_PLUGIN_PINS.items()
        },
    }
    report["package_provenance"] = {
        name: {
            "version": pin["version"],
            "url": pin["git_url"],
            "vcs": "git",
            "commit_id": pin["rev"],
            "requested_revision": pin["rev"],
        }
        for name, pin in CANDIDATE_PLUGIN_PINS.items()
    }
    blocks = generate_blocks(
        report,
        report_logical_path="results/canonical/cohort/report.json",
        measurement_commit="a" * 40,
        evidence_commit="b" * 40,
        github_url="https://github.com/rextio/rextio-benchmark",
        stability_summary=_verified_summary(report),
    )
    english = blocks["README.md"]
    assert "rextio-numpy 0.1.3 candidate@7316c47393a8" in english
    assert "rextio-tensorflow 0.1.3 candidate@346ca58148ed" in english
    assert "not" in english.lower() and "PyPI" in english
    assert (
        blocks["README.md"]
        == generate_blocks(
            report,
            report_logical_path="results/canonical/cohort/report.json",
            measurement_commit="a" * 40,
            evidence_commit="b" * 40,
            github_url="https://github.com/rextio/rextio-benchmark",
            stability_summary=_verified_summary(report),
        )["README.md"]
    )
    for block in blocks.values():
        assert "candidate" in block.lower() or "Candidate" in block
        data_rows = [
            line
            for line in block.splitlines()
            if line.startswith("| ") and not line.startswith("| ---")
        ]
        # header + six headline rows; phase1 diagnostic never appears
        assert len(data_rows) == 7
        assert "numpy-mixed-nonfused-phase1" not in block
