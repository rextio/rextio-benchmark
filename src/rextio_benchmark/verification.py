from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .models import BenchmarkCase
from .portability import require_portable, write_portable_snapshot


class GateError(RuntimeError):
    """A benchmark eligibility gate failed closed."""


MEASUREMENT_HARNESS_FILES = (
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def logical_path(path: Path, repository_root: Path) -> str:
    try:
        relative = path.resolve().relative_to(repository_root.resolve())
    except ValueError as error:
        raise GateError(f"evidence path escapes repository: {path}") from error
    if relative.is_absolute() or ".." in relative.parts:
        raise GateError(f"evidence path is not portable: {relative}")
    return relative.as_posix()


def resolve_logical_path(logical: str, repository_root: Path) -> Path:
    path = Path(logical)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise GateError(f"evidence path is not repository-relative: {logical!r}")
    resolved = (repository_root / path).resolve()
    try:
        resolved.relative_to(repository_root.resolve())
    except ValueError as error:
        raise GateError(f"evidence path escapes repository: {logical!r}") from error
    return resolved


def route_record(check: dict[str, Any], qualname: str) -> dict[str, Any]:
    matches = [
        function
        for module in check.get("modules", [])
        for function in module.get("functions", [])
        if function.get("qualname") == qualname
    ]
    if len(matches) != 1:
        raise GateError(f"expected one check.json record for {qualname}, found {len(matches)}")
    return matches[0]


def _has_suffix(path_value: object, suffix: Path) -> bool:
    parts = Path(str(path_value)).parts
    return len(parts) >= len(suffix.parts) and parts[-len(suffix.parts) :] == suffix.parts


def find_native_artifact(
    case: BenchmarkCase,
    build: dict[str, Any],
) -> tuple[Path, dict[str, Path], dict[str, str]]:
    if case.kind == "executable":
        executable = build.get("executable_build") or {}
        if executable.get("status") != "built":
            raise GateError(f"executable build is not built: {executable!r}")
        declared = executable.get("path")
        expected_suffix = Path("dist") / Path(str(declared)).name
        if not declared or not _has_suffix(declared, expected_suffix):
            raise GateError("executable_build.path is not a declared dist artifact")
        runtime = case.project_root / expected_suffix
        if not runtime.is_file():
            raise GateError(f"declared executable artifact is missing: {runtime}")
        return (
            runtime.resolve(),
            {"runtime_artifact": runtime.resolve()},
            {
                "kind": "executable",
                "declared_path": (
                    Path("cases") / case.project_root.name / expected_suffix
                ).as_posix(),
                "runtime_path": (
                    Path("cases") / case.project_root.name / expected_suffix
                ).as_posix(),
            },
        )

    native_build = build.get("native_build") or {}
    if native_build.get("status") != "built":
        raise GateError(f"native build is not built: {native_build!r}")
    build_python = build.get("build_python")
    installed_path = native_build.get("installed_path")
    if not _has_suffix(build_python, Path(".rextio/build/python")):
        raise GateError("build.json build_python is not the case build tree")
    artifact_name = Path(str(installed_path)).name
    if not artifact_name or not _has_suffix(
        installed_path,
        Path(".rextio/generated/python") / artifact_name,
    ):
        raise GateError("native_build.installed_path is not the declared generated artifact")
    declared = case.project_root / ".rextio" / "generated" / "python" / artifact_name
    runtime = case.project_root / ".rextio" / "build" / "python" / artifact_name
    for path in (declared, runtime):
        if not path.is_file():
            raise GateError(f"declared native artifact is missing: {path}")
    if sha256_file(declared) != sha256_file(runtime):
        raise GateError("runtime native artifact differs from build.json installed artifact")
    return (
        runtime.resolve(),
        {
            "declared_native_artifact": declared.resolve(),
            "runtime_artifact": runtime.resolve(),
        },
        {
            "kind": "native-extension",
            "declared_path": (
                Path("cases")
                / case.project_root.name
                / ".rextio/generated/python"
                / artifact_name
            ).as_posix(),
            "runtime_path": (
                Path("cases")
                / case.project_root.name
                / ".rextio/build/python"
                / artifact_name
            ).as_posix(),
        },
    )


def _evidence_record(
    path: Path,
    repository_root: Path,
    *,
    kind: str,
) -> dict[str, str]:
    if not path.is_file():
        raise GateError(f"required evidence file is missing: {path}")
    return {
        "path": logical_path(path, repository_root),
        "sha256": sha256_file(path),
        "kind": kind,
    }


def gate_build(
    case: BenchmarkCase,
    repository_root: Path,
) -> dict[str, Any]:
    report_root = case.project_root / ".rextio" / "reports"
    check_path = report_root / "check.json"
    build_path = report_root / "build.json"
    if not check_path.is_file() or not build_path.is_file():
        raise GateError(f"missing check/build reports for {case.project}")
    check = json.loads(check_path.read_text(encoding="utf-8"))
    build = json.loads(build_path.read_text(encoding="utf-8"))
    record = route_record(check, case.qualname)
    if record.get("route") != case.expected_route:
        raise GateError(
            f"{case.qualname} route {record.get('route')!r} != {case.expected_route!r}"
        )
    if record.get("native_status") != "accepted":
        raise GateError(f"{case.qualname} native status is {record.get('native_status')!r}")
    artifact, artifact_paths, artifact_declaration = find_native_artifact(case, build)
    portable_root = report_root / "portable"
    portable_check_path = portable_root / "check.json"
    portable_build_path = portable_root / "build.json"
    portable_check = write_portable_snapshot(portable_check_path, check, repository_root)
    portable_build = write_portable_snapshot(portable_build_path, build, repository_root)
    require_portable(portable_check, repository_root)
    require_portable(portable_build, repository_root)
    portable_record = route_record(portable_check, case.qualname)
    if (
        portable_record.get("route") != record.get("route")
        or portable_record.get("native_status") != record.get("native_status")
    ):
        raise GateError("portable check snapshot changed route semantics")
    portable_artifact, _, portable_declaration = find_native_artifact(case, portable_build)
    if portable_artifact != artifact or portable_declaration != artifact_declaration:
        raise GateError("portable build snapshot changed artifact declarations")
    module_path = Path(*case.module.split(".")).with_suffix(".py")
    profile_root = repository_root / "profiles" / case.profile
    paths = {
        "check_report": portable_check_path,
        "build_report": portable_build_path,
        "case_config": case.project_root / "rextio.toml",
        "case_manifest": case.project_root / "benchmark.json",
        "case_source": case.project_root / "src" / module_path,
        "profile_manifest": profile_root / "pyproject.toml",
        "profile_lock": profile_root / "uv.lock",
        "repository_manifest": repository_root / "pyproject.toml",
        "report_schema": repository_root
        / "schema"
        / "benchmark-report-v1.schema.json",
        "publication_policy": repository_root / "PUBLICATION.md",
        "bootstrap_script": repository_root / "scripts" / "bootstrap.sh",
        "build_script": repository_root / "scripts" / "build.sh",
        "benchmark_script": repository_root / "scripts" / "benchmark.sh",
        "verify_script": repository_root / "scripts" / "verify.sh",
        "run_script": repository_root / "scripts" / "run.sh",
        "generated_rust_manifest": case.project_root
        / ".rextio/generated/rust/Cargo.toml",
        "generated_rust_lock": case.project_root / ".rextio/generated/rust/Cargo.lock",
        "generated_rust_source": case.project_root / ".rextio/generated/rust/src/lib.rs",
        "generated_python_wrapper": case.project_root
        / ".rextio/generated/python"
        / module_path,
        "generated_python_fallback": case.project_root
        / ".rextio/generated/python"
        / module_path.parent
        / f"_fallback_{module_path.name}",
        **artifact_paths,
    }
    if case.adapter_path.is_file():
        paths["case_adapter"] = case.adapter_path
    if case.kind == "executable":
        paths.update(
            {
                "generated_executable_manifest": case.project_root
                / ".rextio/generated/rust_bin/Cargo.toml",
                "generated_executable_lock": case.project_root
                / ".rextio/generated/rust_bin/Cargo.lock",
                "generated_executable_source": case.project_root
                / ".rextio/generated/rust_bin/src/main.rs",
            }
        )
    harness_root = repository_root / "src" / "rextio_benchmark"
    for name in MEASUREMENT_HARNESS_FILES:
        paths[f"harness_{Path(name).stem}"] = harness_root / name
    return {
        "route": record.get("route"),
        "native_status": record.get("native_status"),
        "native_build_status": (
            (build.get("executable_build") or {}).get("status")
            if case.kind == "executable"
            else (build.get("native_build") or {}).get("status")
        ),
        "artifact": logical_path(artifact, repository_root),
        "artifact_role": "runtime_artifact",
        "artifact_declaration": artifact_declaration,
        "evidence": {
            role: _evidence_record(
                path,
                repository_root,
                kind=(
                    "run-output"
                    if role.startswith("generated_")
                    or role
                    in {
                        "build_report",
                        "check_report",
                        "declared_native_artifact",
                        "runtime_artifact",
                    }
                    else "run-input"
                ),
            )
            for role, path in sorted(paths.items())
        },
    }


def require_import_under(module_file: str, expected_root: Path) -> None:
    resolved = Path(module_file).resolve()
    try:
        resolved.relative_to(expected_root.resolve())
    except ValueError as error:
        raise GateError(f"imported {resolved} outside expected tree {expected_root}") from error


def outputs_close(left: Any, right: Any, *, absolute: float, relative: float) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), abs_tol=absolute, rel_tol=relative)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            outputs_close(a, b, absolute=absolute, relative=relative)
            for a, b in zip(left, right, strict=True)
        )
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            outputs_close(left[key], right[key], absolute=absolute, relative=relative)
            for key in left
        )
    return type(left) is type(right) and left == right
