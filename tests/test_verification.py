import json
from pathlib import Path

import pytest

from rextio_benchmark import verification
from rextio_benchmark.models import BenchmarkCase
from rextio_benchmark.verification import (
    GateError,
    gate_build,
    outputs_close,
    require_import_under,
    route_record,
)


def test_route_record_requires_one_exact_qualname() -> None:
    check = {
        "modules": [
            {
                "functions": [
                    {
                        "qualname": "example.work",
                        "route": "native-direct",
                        "native_status": "accepted",
                    }
                ]
            }
        ]
    }
    assert route_record(check, "example.work")["route"] == "native-direct"
    with pytest.raises(GateError, match="expected one"):
        route_record(check, "example.missing")


def test_import_provenance_fails_closed(tmp_path: Path) -> None:
    expected = tmp_path / "build"
    expected.mkdir()
    module = expected / "example.py"
    module.write_text("", encoding="utf-8")
    require_import_under(str(module), expected)
    with pytest.raises(GateError, match="outside"):
        require_import_under(str(tmp_path / "source.py"), expected)


def test_recursive_numeric_tolerance() -> None:
    left = {"shape": [2], "sum": 1.0}
    right = {"shape": [2], "sum": 1.0 + 1e-10}
    assert outputs_close(left, right, absolute=1e-9, relative=0.0)
    assert not outputs_close(left, right, absolute=0.0, relative=0.0)


def test_build_gate_requires_exact_route_and_built_artifact(tmp_path: Path) -> None:
    project = tmp_path / "cases" / "fixture"
    reports = project / ".rextio" / "reports"
    generated = project / ".rextio" / "generated"
    source = project / "src" / "example"
    runtime_artifact = project / ".rextio/build/python/_rextio_native.so"
    declared_artifact = generated / "python/_rextio_native.so"
    source.mkdir(parents=True)
    reports.mkdir(parents=True)
    runtime_artifact.parent.mkdir(parents=True)
    declared_artifact.parent.mkdir(parents=True)
    (source / "work.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")
    for path in (
        project / "benchmark_case.py",
        project / "benchmark.json",
        project / "rextio.toml",
        tmp_path / "profiles/base/pyproject.toml",
        tmp_path / "profiles/base/uv.lock",
        tmp_path / "scripts/bootstrap.sh",
        tmp_path / "scripts/build.sh",
        tmp_path / "scripts/benchmark.sh",
        tmp_path / "scripts/verify.sh",
        tmp_path / "scripts/run.sh",
        tmp_path / "pyproject.toml",
        tmp_path / "schema/benchmark-report-v1.schema.json",
        tmp_path / "PUBLICATION.md",
        generated / "rust/Cargo.toml",
        generated / "rust/Cargo.lock",
        generated / "rust/src/lib.rs",
        generated / "python/example/work.py",
        generated / "python/example/_fallback_work.py",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
    for name in (
        "build_runner.py",
        "canonical.py",
        "case_runner.py",
        "models.py",
        "output_table.py",
        "portability.py",
        "processes.py",
        "report.py",
        "statistics.py",
        "verification.py",
        "verifier.py",
        "worker.py",
    ):
        path = tmp_path / "src/rextio_benchmark" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
    runtime_artifact.write_bytes(b"native")
    declared_artifact.write_bytes(b"native")
    (reports / "check.json").write_text(
        json.dumps(
            {
                "modules": [
                    {
                        "functions": [
                            {
                                "qualname": "example.work.run",
                                "route": "native-direct",
                                "native_status": "accepted",
                            }
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (reports / "build.json").write_text(
        json.dumps(
            {
                "build_python": str(project / ".rextio/build/python"),
                "native_build": {
                    "status": "built",
                    "installed_path": str(declared_artifact),
                },
            }
        ),
        encoding="utf-8",
    )
    case = BenchmarkCase(
        benchmark_id="fixture",
        project="fixture",
        profile="base",
        project_root=project,
        adapter_path=project / "benchmark_case.py",
        kind="python-module",
        module="example.work",
        function="run",
        qualname="example.work.run",
        expected_route="native-direct",
        tolerance={"absolute": 0.0, "relative": 0.0},
        raw={},
    )
    gate = gate_build(case, tmp_path)
    assert gate["native_build_status"] == "built"
    assert gate["route"] == "native-direct"
    assert gate["artifact"] == "cases/fixture/.rextio/build/python/_rextio_native.so"
    assert all(not Path(item["path"]).is_absolute() for item in gate["evidence"].values())
    expected_harness = (
        "build_runner.py",
        "canonical.py",
        "case_runner.py",
        "models.py",
        "output_table.py",
        "portability.py",
        "processes.py",
        "report.py",
        "statistics.py",
        "verification.py",
        "verifier.py",
        "worker.py",
    )
    assert expected_harness == verification.MEASUREMENT_HARNESS_FILES
    expected_inputs = {
        "repository_manifest": "pyproject.toml",
        "report_schema": "schema/benchmark-report-v1.schema.json",
        "publication_policy": "PUBLICATION.md",
        "benchmark_script": "scripts/benchmark.sh",
        "verify_script": "scripts/verify.sh",
        "run_script": "scripts/run.sh",
        **{
            f"harness_{Path(name).stem}": f"src/rextio_benchmark/{name}"
            for name in expected_harness
        },
    }
    for role, logical in expected_inputs.items():
        assert gate["evidence"][role]["path"] == logical
        assert gate["evidence"][role]["kind"] == "run-input"
    check = json.loads((reports / "check.json").read_text(encoding="utf-8"))
    check["modules"][0]["functions"][0]["route"] = "fallback-python"
    (reports / "check.json").write_text(json.dumps(check), encoding="utf-8")
    with pytest.raises(GateError, match="route"):
        gate_build(case, tmp_path)
