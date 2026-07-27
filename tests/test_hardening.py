import hashlib
import json
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

from rextio_benchmark import verifier as verifier_module
from rextio_benchmark.bundler import bundle_report
from rextio_benchmark.models import BenchmarkCase, paired_orders
from rextio_benchmark.output_table import OutputTable
from rextio_benchmark.processes import THREAD_ENVIRONMENT, measure_command_samples
from rextio_benchmark.report import render_markdown
from rextio_benchmark.statistics import (
    paired_bootstrap_interval,
    paired_speedups,
    summarize,
)
from rextio_benchmark.verification import GateError, sha256_file
from rextio_benchmark.verifier import (
    _run_commit_available,
    _verify_case_measurements,
    _verify_evidence,
)


def _observation(pair_index: int | None, output_ref: str, samples: list[float]) -> dict:
    return {
        "pair_index": pair_index,
        "samples_ns": samples,
        "normalized_output_ref": output_ref,
        "import_ns": 10,
        "first_call_ns": 20,
        "batch_sizes": [1] * len(samples),
        "batch_elapsed_ns": samples,
        "module_path": "cases/fixture/src/fixture/work.py",
        "pid": 123,
    }


def _lane(observations: list[dict]) -> dict:
    samples = [sample for item in observations for sample in item["samples_ns"]]
    return {
        "steady_state": summarize(samples),
        "raw_samples_ns": samples,
        "import_ns": [item["import_ns"] for item in observations],
        "first_call_ns": [item["first_call_ns"] for item in observations],
        "batch_sizes": [size for item in observations for size in item["batch_sizes"]],
        "batch_elapsed_ns": [
            elapsed for item in observations for elapsed in item["batch_elapsed_ns"]
        ],
        "module_files": [item["module_path"] for item in observations],
        "pids": [item["pid"] for item in observations],
        "observations": observations,
    }


def _fixture_case_report() -> tuple[BenchmarkCase, dict, dict]:
    case = BenchmarkCase(
        benchmark_id="fixture",
        project="fixture",
        profile="base",
        project_root=Path("cases/fixture"),
        adapter_path=Path("cases/fixture/benchmark_case.py"),
        kind="python-module",
        module="fixture.work",
        function="run",
        qualname="fixture.work.run",
        expected_route="native-direct",
        tolerance={"absolute": 1e-9, "relative": 1e-9},
        raw={},
    )
    outputs = OutputTable()
    expected_ref = outputs.intern({"value": 3.0})
    source = [
        _observation(0, expected_ref, [10_000_000.0, 12_000_000.0]),
        _observation(1, expected_ref, [11_000_000.0, 13_000_000.0]),
    ]
    native = [
        _observation(0, expected_ref, [5_000_000.0, 6_000_000.0]),
        _observation(1, expected_ref, [5_500_000.0, 6_500_000.0]),
    ]
    fallback = [_observation(None, expected_ref, [10_500_000.0, 11_500_000.0])]
    source_medians = [statistics.median(item["samples_ns"]) for item in source]
    native_medians = [statistics.median(item["samples_ns"]) for item in native]
    speedups = paired_speedups(source_medians, native_medians)
    config = {
        "warmups": 1,
        "samples": 2,
        "minimum_sample_ns": 5_000_000,
        "pairs": 2,
        "bootstrap_resamples": 1000,
    }
    pairs = []
    for index, order in enumerate(paired_orders(2)):
        pairs.append(
            {
                "index": index,
                "order": list(order),
                "source_observation": index,
                "native_observation": index,
            }
        )
    report = {
        "output_table": outputs.values(),
        "timing_contract": {
            "unit": "function-call",
            "process_model": "fresh-persistent-worker-per-observation",
            "minimum_sample_ns": 5_000_000,
            "includes_process_startup": False,
        },
        "correctness": {
            "status": "passed",
            "evidence": {
                "reference_output_ref": expected_ref,
                "fallback_output_ref": expected_ref,
            },
        },
        "environment": {
            **THREAD_ENVIRONMENT,
            "effective_threads": {},
            "module_provenance": {
                "rextio": {
                    "file": "profiles/base/.venv/lib/python3.11/site-packages/rextio/__init__.py",
                    "site_packages": "profiles/base/.venv/lib/python3.11/site-packages",
                }
            },
            "active_module_provenance": {
                "python-source": {
                    "rextio": {
                        "kind": "installed",
                        "file": (
                            "profiles/base/.venv/lib/python3.11/"
                            "site-packages/rextio/__init__.py"
                        ),
                        "root": "profiles/base/.venv/lib/python3.11/site-packages",
                    }
                },
                "rextio-fallback": {
                    "rextio": {
                        "kind": "generated-runtime",
                        "file": (
                            "cases/fixture/.rextio/build/python/rextio/"
                            "__init__.py"
                        ),
                        "root": "cases/fixture/.rextio/build/python",
                    }
                },
                "rextio-native": {
                    "rextio": {
                        "kind": "generated-runtime",
                        "file": (
                            "cases/fixture/.rextio/build/python/rextio/"
                            "__init__.py"
                        ),
                        "root": "cases/fixture/.rextio/build/python",
                    }
                },
            },
            "profile_prefix": "profiles/base/.venv",
        },
        "lanes": {
            "python-source": _lane(source),
            "rextio-native": _lane(native),
            "rextio-fallback": _lane(fallback),
        },
        "paired": {
            "orders": [list(order) for order in paired_orders(2)],
            "source_medians_ns": source_medians,
            "native_medians_ns": native_medians,
            "speedups": speedups,
            "median_speedup": statistics.median(speedups),
            "bootstrap_95": list(
                paired_bootstrap_interval(source_medians, native_medians, resamples=1000)
            ),
            "observations": pairs,
        },
    }
    return case, report, config


@pytest.mark.parametrize("tamper", ["median", "speedup", "output", "batch"])
def test_verifier_recomputes_persisted_measurements(tamper: str) -> None:
    case, report, config = _fixture_case_report()
    if tamper == "median":
        report["lanes"]["python-source"]["steady_state"]["median_ns"] += 1_000_000
    elif tamper == "speedup":
        report["paired"]["median_speedup"] += 1.0
    elif tamper == "output":
        reference = report["lanes"]["rextio-native"]["observations"][0][
            "normalized_output_ref"
        ]
        report["output_table"][reference] = {"value": 9.0}
    else:
        report["lanes"]["rextio-native"]["observations"][0]["batch_elapsed_ns"][0] = 1.0
    with pytest.raises(GateError):
        _verify_case_measurements(case, report, config)


def test_verifier_accepts_recomputed_measurements() -> None:
    case, report, config = _fixture_case_report()
    _verify_case_measurements(case, report, config)


def test_verifier_rejects_validly_rekeyed_incorrect_output() -> None:
    case, report, config = _fixture_case_report()
    outputs = OutputTable()
    incorrect_ref = outputs.intern({"value": 9.0})
    report["output_table"][incorrect_ref] = outputs.values()[incorrect_ref]
    report["lanes"]["rextio-native"]["observations"][0][
        "normalized_output_ref"
    ] = incorrect_ref
    with pytest.raises(GateError, match="source/native correctness"):
        _verify_case_measurements(case, report, config)


@pytest.mark.parametrize("kind", ["dangling", "unreferenced", "nonfinite"])
def test_verifier_rejects_invalid_output_table(kind: str) -> None:
    case, report, config = _fixture_case_report()
    if kind == "dangling":
        report["lanes"]["python-source"]["observations"][0][
            "normalized_output_ref"
        ] = "f" * 64
    elif kind == "unreferenced":
        outputs = OutputTable()
        extra_ref = outputs.intern({"value": 4.0})
        report["output_table"][extra_ref] = outputs.values()[extra_ref]
    else:
        reference = next(iter(report["output_table"]))
        report["output_table"][reference] = {"value": float("inf")}
    with pytest.raises(GateError, match=kind if kind != "nonfinite" else "finite"):
        _verify_case_measurements(case, report, config)


def test_evidence_rejects_absolute_paths(tmp_path: Path) -> None:
    gate = {
        "artifact": str(tmp_path / "artifact"),
        "artifact_role": "runtime_artifact",
        "artifact_declaration": {
            "kind": "executable",
            "declared_path": "cases/fixture/dist/artifact",
            "runtime_path": str(tmp_path / "artifact"),
        },
        "evidence": {
            "runtime_artifact": {
                "path": str(tmp_path / "artifact"),
                "sha256": "0" * 64,
                "kind": "run-output",
            }
        },
    }
    with pytest.raises(GateError, match="absolute"):
        _verify_evidence(gate, tmp_path, None)


def test_executable_samples_honor_minimum_duration(tmp_path: Path) -> None:
    result = measure_command_samples(
        [sys.executable, "-c", "print('stable')"],
        samples=2,
        minimum_sample_ns=1_000_000,
        initial_batch_size=1,
        cwd=tmp_path,
        environment={},
    )
    assert result["output"] == "stable\n"
    assert all(value >= 1_000_000 for value in result["batch_elapsed_ns"])


def test_run_commit_a_is_verifiable_from_descendant_b(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=tmp_path, check=True)
    path = tmp_path / "input.json"
    path.write_text(json.dumps({"run": "A"}), encoding="utf-8")
    subprocess.run(["git", "add", "input.json"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "run inputs"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    commit_a = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    path.write_text(json.dumps({"run": "A", "report": "B"}), encoding="utf-8")
    subprocess.run(["git", "add", "input.json"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "canonical report"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    commit_b = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert _run_commit_available(tmp_path, commit_a, commit_b)


def _executable_evidence_gate(
    build_path: Path,
    artifact_sha256: str,
    *,
    input_sha256: str | None = None,
) -> dict:
    evidence = {
        "build_report": {
            "path": "cases/fixture/.rextio/reports/build.json",
            "sha256": sha256_file(build_path),
            "kind": "run-output",
        },
        "runtime_artifact": {
            "path": "cases/fixture/dist/artifact",
            "sha256": artifact_sha256,
            "kind": "run-output",
        },
    }
    if input_sha256 is not None:
        evidence["case_config"] = {
            "path": "input.json",
            "sha256": input_sha256,
            "kind": "run-input",
        }
    return {
        "artifact": "cases/fixture/dist/artifact",
        "artifact_role": "runtime_artifact",
        "artifact_declaration": {
            "kind": "executable",
            "declared_path": "cases/fixture/dist/artifact",
            "runtime_path": "cases/fixture/dist/artifact",
        },
        "evidence": evidence,
    }


def test_missing_run_output_requires_bundle(tmp_path: Path) -> None:
    build_path = tmp_path / "cases/fixture/.rextio/reports/build.json"
    build_path.parent.mkdir(parents=True)
    build_path.write_text(
        json.dumps({"executable_build": {"status": "built", "path": "dist/artifact"}}),
        encoding="utf-8",
    )
    gate = _executable_evidence_gate(build_path, "0" * 64)
    with pytest.raises(GateError, match="bundled evidence file is missing"):
        _verify_evidence(gate, tmp_path, "a" * 40)


def test_tampered_bundle_is_rejected(tmp_path: Path) -> None:
    build_path = tmp_path / "cases/fixture/.rextio/reports/build.json"
    build_path.parent.mkdir(parents=True)
    build_path.write_text(
        json.dumps({"executable_build": {"status": "built", "path": "dist/artifact"}}),
        encoding="utf-8",
    )
    expected = hashlib.sha256(b"native").hexdigest()
    bundled = tmp_path / "results/canonical/fixture/objects" / expected
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"evil!!")
    gate = _executable_evidence_gate(build_path, expected)
    with pytest.raises(GateError, match="bundle digest changed"):
        _verify_evidence(
            gate,
            tmp_path,
            "a" * 40,
            bundle_evidence={
                "runtime_artifact": {
                    "kind": "run-output",
                    "logical_path": "cases/fixture/dist/artifact",
                    "bundle_path": bundled.relative_to(tmp_path).as_posix(),
                    "sha256": expected,
                    "size_bytes": len(b"native"),
                }
            },
        )


def test_run_inputs_at_a_and_bundled_outputs_at_b_are_verifiable(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=tmp_path, check=True)
    input_path = tmp_path / "input.json"
    input_path.write_text('{"run":"A"}\n', encoding="utf-8")
    subprocess.run(["git", "add", "input.json"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "run"], cwd=tmp_path, check=True, capture_output=True)
    commit_a = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    bundle_root = tmp_path / "results/canonical/fixture/objects"
    bundle_root.mkdir(parents=True)
    build_bytes = json.dumps(
        {"executable_build": {"status": "built", "path": "dist/artifact"}}
    ).encode()
    artifact_bytes = b"native"
    build_sha = hashlib.sha256(build_bytes).hexdigest()
    artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()
    bundled_build = bundle_root / build_sha
    bundled_artifact = bundle_root / artifact_sha
    bundled_build.write_bytes(build_bytes)
    bundled_artifact.write_bytes(artifact_bytes)
    subprocess.run(["git", "add", "results"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "bundle"], cwd=tmp_path, check=True, capture_output=True)
    commit_b = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    original_build = tmp_path / "build-fixture.json"
    original_build.write_bytes(build_bytes)
    gate = _executable_evidence_gate(
        original_build,
        artifact_sha,
        input_sha256=sha256_file(input_path),
    )
    gate["evidence"]["build_report"]["sha256"] = build_sha
    bundle_evidence = {
        "build_report": {
            "kind": "run-output",
            "logical_path": gate["evidence"]["build_report"]["path"],
            "bundle_path": bundled_build.relative_to(tmp_path).as_posix(),
            "sha256": build_sha,
            "size_bytes": len(build_bytes),
        },
        "runtime_artifact": {
            "kind": "run-output",
            "logical_path": gate["evidence"]["runtime_artifact"]["path"],
            "bundle_path": bundled_artifact.relative_to(tmp_path).as_posix(),
            "sha256": artifact_sha,
            "size_bytes": len(artifact_bytes),
        },
    }
    assert _run_commit_available(tmp_path, commit_a, commit_b)
    _verify_evidence(
        gate,
        tmp_path,
        commit_a,
        bundle_evidence=bundle_evidence,
    )


def test_bundled_run_outputs_win_over_mutated_live_files(tmp_path: Path) -> None:
    """Canonical verification must use bundled bytes, not live ignored .rextio paths."""
    build_bytes = json.dumps(
        {"executable_build": {"status": "built", "path": "dist/artifact"}}
    ).encode()
    artifact_bytes = b"native-original"
    build_sha = hashlib.sha256(build_bytes).hexdigest()
    artifact_sha = hashlib.sha256(artifact_bytes).hexdigest()

    # Live paths exist but are mutated (simulates candidate rebuilds overwriting .rextio).
    live_build = tmp_path / "cases/fixture/.rextio/reports/build.json"
    live_build.parent.mkdir(parents=True)
    live_build.write_text('{"mutated": true}\n', encoding="utf-8")
    live_artifact = tmp_path / "cases/fixture/dist/artifact"
    live_artifact.parent.mkdir(parents=True)
    live_artifact.write_bytes(b"mutated-live")

    bundle_root = tmp_path / "results/canonical/fixture/objects"
    bundle_root.mkdir(parents=True)
    bundled_build = bundle_root / build_sha
    bundled_artifact = bundle_root / artifact_sha
    bundled_build.write_bytes(build_bytes)
    bundled_artifact.write_bytes(artifact_bytes)

    gate = {
        "artifact": "cases/fixture/dist/artifact",
        "artifact_role": "runtime_artifact",
        "artifact_declaration": {
            "kind": "executable",
            "declared_path": "cases/fixture/dist/artifact",
            "runtime_path": "cases/fixture/dist/artifact",
        },
        "evidence": {
            "build_report": {
                "path": "cases/fixture/.rextio/reports/build.json",
                "sha256": build_sha,
                "kind": "run-output",
            },
            "runtime_artifact": {
                "path": "cases/fixture/dist/artifact",
                "sha256": artifact_sha,
                "kind": "run-output",
            },
        },
    }
    bundle_evidence = {
        "build_report": {
            "kind": "run-output",
            "logical_path": "cases/fixture/.rextio/reports/build.json",
            "bundle_path": bundled_build.relative_to(tmp_path).as_posix(),
            "sha256": build_sha,
            "size_bytes": len(build_bytes),
        },
        "runtime_artifact": {
            "kind": "run-output",
            "logical_path": "cases/fixture/dist/artifact",
            "bundle_path": bundled_artifact.relative_to(tmp_path).as_posix(),
            "sha256": artifact_sha,
            "size_bytes": len(artifact_bytes),
        },
    }
    resolved = _verify_evidence(
        gate,
        tmp_path,
        "a" * 40,
        bundle_evidence=bundle_evidence,
    )
    assert resolved["build_report"] == bundled_build
    assert resolved["runtime_artifact"] == bundled_artifact
    assert sha256_file(resolved["build_report"]) == build_sha
    # Live mutation must not affect the result.
    assert sha256_file(live_build) != build_sha


def test_bundle_report_writes_role_keyed_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=tmp_path, check=True)
    ignore = tmp_path / ".gitignore"
    ignore.write_text("cases/*/.rextio/\nresults/local/\n", encoding="utf-8")
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("input\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "run"], cwd=tmp_path, check=True, capture_output=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    policy = tmp_path / "policy.txt"
    policy.write_text("descendant policy\n", encoding="utf-8")
    subprocess.run(["git", "add", "policy.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "policy"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    output = tmp_path / "cases/fixture/.rextio/reports/check.json"
    output.parent.mkdir(parents=True)
    output.write_text('{"accepted":true}\n', encoding="utf-8")
    source_report = tmp_path / "results/local/report.json"
    source_report.parent.mkdir(parents=True)
    report = {
        "mode": "publish",
        "generated_at": "2026-07-26T00:00:00+00:00",
        "repository": {"commit": commit, "dirty": False},
        "publishable": True,
        "system": {"platform": "fixture"},
        "eligibility": {"blockers": []},
        "cases": [
            {
                "id": "fixture",
                "eligible": True,
                "paired": None,
                "gate": {
                    "evidence": {
                        "check_report": {
                            "path": output.relative_to(tmp_path).as_posix(),
                            "sha256": sha256_file(output),
                            "kind": "run-output",
                        },
                        "case_source": {
                            "path": "tracked.txt",
                            "sha256": sha256_file(tracked),
                            "kind": "run-input",
                        },
                    }
                },
            }
        ],
    }
    source_report.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(
        "rextio_benchmark.bundler.verify_report",
        lambda report_path, repository_root: report,
    )
    canonical_report, manifest_path, summary = bundle_report(
        source_report,
        tmp_path,
        name="fixture",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    canonical = json.loads(canonical_report.read_text(encoding="utf-8"))
    record = manifest["cases"]["fixture"]["roles"]["check_report"]
    assert record["logical_path"] == "cases/fixture/.rextio/reports/check.json"
    assert sha256_file(tmp_path / record["bundle_path"]) == record["sha256"]
    assert (
        canonical["canonical_bundle"]["manifest_path"]
        == "results/canonical/fixture/manifest.json"
    )
    markdown = canonical_report.with_suffix(".md")
    assert markdown.read_text(encoding="utf-8") == render_markdown(canonical)
    assert manifest["report_markdown_path"] == "results/canonical/fixture/report.md"
    assert manifest["report_markdown_sha256"] == sha256_file(markdown)
    assert (
        canonical["canonical_bundle"]["report_markdown_sha256"]
        == manifest["report_markdown_sha256"]
    )
    assert summary["stored_bytes"] == output.stat().st_size


def test_canonical_markdown_verification_rejects_tamper_and_rerender_drift(
    tmp_path: Path,
) -> None:
    bundle_root = tmp_path / "results/canonical/fixture"
    bundle_root.mkdir(parents=True)
    report = {
        "mode": "publish",
        "generated_at": "2026-07-26T00:00:00+00:00",
        "publishable": True,
        "system": {"platform": "fixture"},
        "eligibility": {"blockers": []},
        "cases": [],
        "canonical_bundle": {
            "report_markdown_path": "results/canonical/fixture/report.md",
            "report_markdown_sha256": "",
        },
    }
    markdown = bundle_root / "report.md"
    markdown.write_text(render_markdown(report), encoding="utf-8")
    digest = sha256_file(markdown)
    report["canonical_bundle"]["report_markdown_sha256"] = digest
    manifest = {
        "report_markdown_path": "results/canonical/fixture/report.md",
        "report_markdown_sha256": digest,
    }
    verifier_module._verify_canonical_markdown(
        report,
        manifest,
        bundle_root,
        tmp_path,
    )
    markdown.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(GateError, match="digest"):
        verifier_module._verify_canonical_markdown(
            report,
            manifest,
            bundle_root,
            tmp_path,
        )
    forged_digest = sha256_file(markdown)
    manifest["report_markdown_sha256"] = forged_digest
    report["canonical_bundle"]["report_markdown_sha256"] = forged_digest
    with pytest.raises(GateError, match="rendered"):
        verifier_module._verify_canonical_markdown(
            report,
            manifest,
            bundle_root,
            tmp_path,
        )


def test_bundle_report_rejects_dirty_descendant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=tmp_path, check=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("A\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "A"], cwd=tmp_path, check=True, capture_output=True)
    commit_a = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    tracked.write_text("dirty\n", encoding="utf-8")
    source_report = tmp_path / "report.json"
    report = {
        "repository": {"commit": commit_a, "dirty": False},
        "publishable": True,
        "cases": [],
    }
    source_report.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(
        "rextio_benchmark.bundler.verify_report",
        lambda report_path, repository_root: report,
    )
    with pytest.raises(GateError, match="clean"):
        bundle_report(source_report, tmp_path, name="dirty")


def test_bundle_report_rejects_unrelated_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "fixture@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Fixture"], cwd=tmp_path, check=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("A\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "A"], cwd=tmp_path, check=True, capture_output=True)
    commit_a = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "checkout", "--orphan", "unrelated"], cwd=tmp_path, check=True)
    tracked.write_text("unrelated\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "unrelated"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    source_report = tmp_path / "report.json"
    report = {
        "repository": {"commit": commit_a, "dirty": False},
        "publishable": True,
        "cases": [],
    }
    source_report.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(
        "rextio_benchmark.bundler.verify_report",
        lambda report_path, repository_root: report,
    )
    with pytest.raises(GateError, match="ancestor"):
        bundle_report(source_report, tmp_path, name="unrelated")
