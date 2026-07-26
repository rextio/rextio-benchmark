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
        tmp_path / "profiles/next-candidate.toml",
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
        "integration_targets.py",
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
        "integration_targets.py",
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
        "integration_target_config": "profiles/next-candidate.toml",
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


def test_generated_expectations_require_plugin_rule_and_rust_substring(
    tmp_path: Path,
) -> None:
    from rextio_benchmark.verification import enforce_generated_expectations

    rust = tmp_path / "lib.rs"
    rust.write_text(
        "fn body() { let _ = __rxtnp_echain_demo(&a, &b); }\n"
        "fn target() {\n"
        "    let converted = extract(input);\n"
        "    let guard = enter();\n"
        "    let value = direct_fill(converted);\n"
        "    drop(guard);\n"
        "}\n"
        "fn helper() { direct_fill_sink(); }\n",
        encoding="utf-8",
    )
    check = {
        "modules": [
            {
                "functions": [
                    {
                        "qualname": "numpy_case.workload.mixed_fusion",
                        "route": "native-plugin:rextio-numpy",
                        "native_status": "accepted",
                        "plugin_claims": [
                            {
                                "rule_id": "rextio-numpy/elementwise-chain-fusion",
                                "operand_mode": "leaves",
                            }
                        ],
                    }
                ]
            }
        ]
    }
    case = BenchmarkCase(
        benchmark_id="numpy-mixed-fusion",
        project="numpy",
        profile="base",
        project_root=tmp_path,
        adapter_path=tmp_path / "benchmark_case.py",
        kind="python-module",
        module="numpy_case.workload",
        function="mixed_fusion",
        qualname="numpy_case.workload.mixed_fusion",
        expected_route="native-plugin:rextio-numpy",
        tolerance={"absolute": 0.0, "relative": 0.0},
        raw={
            "generated_expectations": {
                "plugin_rules": [
                    {
                        "rule_id": "rextio-numpy/elementwise-chain-fusion",
                        "operand_mode": "leaves",
                    }
                ],
                "generated_rust_source_substrings": ["__rxtnp_echain_"],
                "rust_functions": [
                    {
                        "name": "target",
                        "required_substrings": ["let guard = enter();", "direct_fill("],
                        "forbidden_substrings": ["nested_guard()"],
                        "substring_counts": {"enter()": 1},
                        "ordered_substrings": [
                            "extract(input)",
                            "let guard = enter();",
                            "direct_fill(converted)",
                            "drop(guard)",
                        ],
                    },
                    {
                        "name": "helper",
                        "required_substrings": ["direct_fill_sink()"],
                        "forbidden_substrings": ["enter()"],
                    },
                ],
            }
        },
    )
    enforce_generated_expectations(case, check, generated_rust_source=rust)

    missing_rule = {
        "modules": [
            {
                "functions": [
                    {
                        "qualname": "numpy_case.workload.mixed_fusion",
                        "route": "native-plugin:rextio-numpy",
                        "native_status": "accepted",
                        "plugin_claims": [],
                    }
                ]
            }
        ]
    }
    with pytest.raises(GateError, match="missing required plugin rule"):
        enforce_generated_expectations(case, missing_rule, generated_rust_source=rust)

    rust.write_text("fn body() { /* no helper */ }\n", encoding="utf-8")
    with pytest.raises(GateError, match="generated Rust source lacks"):
        enforce_generated_expectations(case, check, generated_rust_source=rust)

    rust.write_text(
        "fn body() { let _ = __rxtnp_echain_demo(&a, &b); }\n"
        "fn target() {\n"
        "    let guard = enter();\n"
        "    let value = direct_fill(input);\n"
        "    let nested = enter();\n"
        "    drop(guard);\n"
        "}\n"
        "fn helper() { let nested = enter(); direct_fill_sink(); }\n",
        encoding="utf-8",
    )
    with pytest.raises(GateError, match="expected 1 occurrences"):
        enforce_generated_expectations(case, check, generated_rust_source=rust)


def test_rust_function_expectation_binds_nested_numpy_return_conversion(
    tmp_path: Path,
) -> None:
    from rextio_benchmark.verification import enforce_generated_expectations

    nested = "__rxtnp_release_f64_1d(__rxtnp_add1_as(py, &values, 0.25)?)?"
    rust = tmp_path / "lib.rs"
    rust.write_text(
        "fn numpy_case__workload__boundary_direct_sink() {\n"
        f"    return Ok({nested});\n"
        "}\n",
        encoding="utf-8",
    )
    check = {
        "modules": [
            {
                "functions": [
                    {
                        "qualname": "numpy_case.workload.boundary_direct_sink",
                        "route": "native-plugin:rextio-numpy",
                        "native_status": "accepted",
                    }
                ]
            }
        ]
    }
    case = BenchmarkCase(
        benchmark_id="numpy-f64-1d-boundary-direct-sink",
        project="numpy",
        profile="base",
        project_root=tmp_path,
        adapter_path=tmp_path / "benchmark_case.py",
        kind="python-module",
        module="numpy_case.workload",
        function="boundary_direct_sink",
        qualname="numpy_case.workload.boundary_direct_sink",
        expected_route="native-plugin:rextio-numpy",
        tolerance={"absolute": 0.0, "relative": 0.0},
        raw={
            "generated_expectations": {
                "rust_functions": [
                    {
                        "name": "numpy_case__workload__boundary_direct_sink",
                        "required_substrings": [nested],
                    }
                ]
            }
        },
    )
    enforce_generated_expectations(case, check, generated_rust_source=rust)

    rust.write_text(
        "fn numpy_case__workload__boundary_direct_sink() {\n"
        "    let value = __rxtnp_add1_as(py, &values, 0.25)?;\n"
        "    return Ok(value);\n"
        "}\n"
        "fn unrelated() { __rxtnp_release_f64_1d(value); }\n",
        encoding="utf-8",
    )
    with pytest.raises(GateError, match="lacks '__rxtnp_release_f64_1d"):
        enforce_generated_expectations(case, check, generated_rust_source=rust)


def test_gate_build_enforces_generated_expectations_on_portable_check(
    tmp_path: Path,
) -> None:
    """Recorded check_report evidence is the portable snapshot; it must prove claims."""
    from rextio_benchmark.verification import enforce_generated_expectations

    project = tmp_path / "cases" / "numpy"
    reports = project / ".rextio" / "reports"
    generated = project / ".rextio" / "generated"
    source = project / "src" / "numpy_case"
    runtime_artifact = project / ".rextio/build/python/_rextio_native.so"
    declared_artifact = generated / "python/_rextio_native.so"
    source.mkdir(parents=True)
    reports.mkdir(parents=True)
    runtime_artifact.parent.mkdir(parents=True)
    declared_artifact.parent.mkdir(parents=True)
    (source / "workload.py").write_text(
        "def mixed_fusion() -> int:\n    return 1\n",
        encoding="utf-8",
    )
    for path in (
        project / "benchmark_case.py",
        project / "benchmark.json",
        project / "rextio.toml",
        tmp_path / "profiles/base/pyproject.toml",
        tmp_path / "profiles/base/uv.lock",
        tmp_path / "profiles/next-candidate.toml",
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
        generated / "python/numpy_case/workload.py",
        generated / "python/numpy_case/_fallback_workload.py",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
    rust = generated / "rust/src/lib.rs"
    rust.parent.mkdir(parents=True, exist_ok=True)
    rust.write_text(
        "fn body() { let _ = __rxtnp_echain_demo(&a, &b); }\n",
        encoding="utf-8",
    )
    for name in (
        "build_runner.py",
        "canonical.py",
        "case_runner.py",
        "integration_targets.py",
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
    check_payload = {
        "modules": [
            {
                "functions": [
                    {
                        "qualname": "numpy_case.workload.mixed_fusion",
                        "route": "native-plugin:rextio-numpy",
                        "native_status": "accepted",
                        "plugin_claims": [
                            {
                                "rule_id": "rextio-numpy/elementwise-chain-fusion",
                                "operand_mode": "leaves",
                            }
                        ],
                    }
                ]
            }
        ]
    }
    (reports / "check.json").write_text(json.dumps(check_payload), encoding="utf-8")
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
        benchmark_id="numpy-mixed-fusion",
        project="numpy",
        profile="base",
        project_root=project,
        adapter_path=project / "benchmark_case.py",
        kind="python-module",
        module="numpy_case.workload",
        function="mixed_fusion",
        qualname="numpy_case.workload.mixed_fusion",
        expected_route="native-plugin:rextio-numpy",
        tolerance={"absolute": 0.0, "relative": 0.0},
        raw={
            "generated_expectations": {
                "plugin_rules": [
                    {
                        "rule_id": "rextio-numpy/elementwise-chain-fusion",
                        "operand_mode": "leaves",
                    }
                ],
                "generated_rust_source_substrings": ["__rxtnp_echain_"],
            }
        },
    )
    gate = gate_build(case, tmp_path)
    portable_path = project / ".rextio/reports/portable/check.json"
    assert gate["evidence"]["check_report"]["path"] == (
        "cases/numpy/.rextio/reports/portable/check.json"
    )
    assert portable_path.is_file()
    portable_check = json.loads(portable_path.read_text(encoding="utf-8"))
    # The recorded portable evidence itself must satisfy the proof gate.
    enforce_generated_expectations(
        case,
        portable_check,
        generated_rust_source=rust,
    )
    # Missing claims in the portable evidence path fails closed.
    stripped = json.loads(json.dumps(portable_check))
    stripped["modules"][0]["functions"][0]["plugin_claims"] = []
    with pytest.raises(GateError, match="missing required plugin rule"):
        enforce_generated_expectations(
            case,
            stripped,
            generated_rust_source=rust,
        )


def test_phase1_case_has_no_fusion_expectations() -> None:
    from pathlib import Path as PathType

    from rextio_benchmark.models import load_cases

    root = PathType(__file__).resolve().parents[1]
    cases = {case.benchmark_id: case for case in load_cases(root)}
    assert "generated_expectations" not in cases["numpy-mixed-nonfused-phase1"].raw
    fusion = cases["numpy-mixed-fusion"].raw["generated_expectations"]
    assert fusion["plugin_rules"][0]["rule_id"] == ("rextio-numpy/elementwise-chain-fusion")
    assert fusion["plugin_rules"][0]["operand_mode"] == "leaves"
    tf = cases["tensorflow-cpu-eager-chain"].raw["generated_expectations"]
    assert tf["plugin_rules"][0]["rule_id"] == ("rextio-tensorflow/transpose-f32-cpu-2d")
    assert "rextio_tensorflow_runtime::transpose(" in tf["generated_rust_source_substrings"]
