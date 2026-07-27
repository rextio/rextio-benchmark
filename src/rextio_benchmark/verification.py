from __future__ import annotations

import hashlib
import json
import math
import re
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


def _rust_function_body(source: str, name: str) -> str:
    """Return one generated Rust function body, failing closed on ambiguity."""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None:
        raise GateError(f"invalid generated Rust function name {name!r}")
    matches = list(re.finditer(rf"(?m)^\s*(?:pub\s+)?fn\s+{re.escape(name)}(?:\s*<|\s*\()", source))
    if len(matches) != 1:
        raise GateError(f"generated Rust expected one function {name!r}, found {len(matches)}")
    opening = source.find("{", matches[0].end())
    if opening < 0:
        raise GateError(f"generated Rust function {name!r} lacks a body")
    depth = 0
    in_string = False
    in_char = False
    escaped = False
    line_comment = False
    block_comment_depth = 0
    index = opening
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment_depth:
            if char == "/" and following == "*":
                block_comment_depth += 1
                index += 2
                continue
            if char == "*" and following == "/":
                block_comment_depth -= 1
                index += 2
                continue
            index += 1
            continue
        if in_string or in_char:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif in_string and char == '"':
                in_string = False
            elif in_char and char == "'":
                in_char = False
            index += 1
            continue
        if char == "/" and following == "/":
            line_comment = True
            index += 2
            continue
        if char == "/" and following == "*":
            block_comment_depth = 1
            index += 2
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "'":
            third = source[index + 2] if index + 2 < len(source) else ""
            if not (following.isalpha() or following == "_") or third == "'":
                in_char = True
                index += 1
                continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[opening + 1 : index]
            if depth < 0:
                break
        index += 1
    raise GateError(f"generated Rust function {name!r} has an unbalanced body")


def _enforce_rust_function_expectations(
    benchmark_id: str,
    source: str,
    expectations: object,
) -> None:
    if not isinstance(expectations, list):
        raise GateError(f"{benchmark_id}: rust_functions must be an array")
    for record in expectations:
        if not isinstance(record, dict) or not isinstance(record.get("name"), str):
            raise GateError(f"{benchmark_id}: rust_functions entries need a name")
        name = record["name"]
        body = _rust_function_body(source, name)
        for field in ("required_substrings", "forbidden_substrings"):
            values = record.get(field, []) or []
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value for value in values
            ):
                raise GateError(f"{benchmark_id}: {field} must contain non-empty strings")
        for needle in record.get("required_substrings", []) or []:
            if needle not in body:
                raise GateError(f"{benchmark_id}: Rust function {name!r} lacks {needle!r}")
        for needle in record.get("forbidden_substrings", []) or []:
            if needle in body:
                raise GateError(
                    f"{benchmark_id}: Rust function {name!r} contains forbidden {needle!r}"
                )
        counts = record.get("substring_counts", {}) or {}
        if not isinstance(counts, dict):
            raise GateError(f"{benchmark_id}: substring_counts must be an object")
        for needle, expected_count in counts.items():
            if (
                not isinstance(needle, str)
                or not needle
                or not isinstance(expected_count, int)
                or isinstance(expected_count, bool)
                or expected_count < 0
            ):
                raise GateError(
                    f"{benchmark_id}: substring_counts entries must be string -> integer"
                )
            actual_count = body.count(needle)
            if actual_count != expected_count:
                raise GateError(
                    f"{benchmark_id}: Rust function {name!r} expected "
                    f"{expected_count} occurrences of {needle!r}, found {actual_count}"
                )
        ordered = record.get("ordered_substrings", []) or []
        if not isinstance(ordered, list) or any(
            not isinstance(value, str) or not value for value in ordered
        ):
            raise GateError(f"{benchmark_id}: ordered_substrings must contain non-empty strings")
        position = -1
        for needle in ordered:
            position = body.find(needle, position + 1)
            if position < 0:
                raise GateError(f"{benchmark_id}: Rust function {name!r} lacks ordered {needle!r}")


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
                Path("cases") / case.project_root.name / ".rextio/generated/python" / artifact_name
            ).as_posix(),
            "runtime_path": (
                Path("cases") / case.project_root.name / ".rextio/build/python" / artifact_name
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


def _plugin_claims(record: dict[str, Any]) -> list[dict[str, Any]]:
    claims = record.get("plugin_claims")
    if claims is None:
        return []
    if not isinstance(claims, list):
        raise GateError(f"{record.get('qualname')}: plugin_claims must be a list")
    return [claim for claim in claims if isinstance(claim, dict)]


def enforce_generated_expectations(
    case: BenchmarkCase,
    check: dict[str, Any],
    *,
    generated_rust_source: Path,
) -> None:
    """Fail closed when a case declares plugin-rule / generated-source proof.

    Headline NumPy fusion must show leaves-mode elementwise-chain-fusion and a
    ``__rxtnp_echain_`` helper. TensorFlow transpose must show the exact
    default rank-2 transpose rule and ``rextio_tensorflow_runtime::transpose``.
    Phase-1 and other cases without expectations impose no fusion claim.
    """
    expectations = case.raw.get("generated_expectations")
    if not expectations:
        return
    if not isinstance(expectations, dict):
        raise GateError(f"{case.benchmark_id}: generated_expectations must be an object")
    record = route_record(check, case.qualname)
    claims = _plugin_claims(record)
    for rule in expectations.get("plugin_rules", []) or []:
        if not isinstance(rule, dict) or "rule_id" not in rule:
            raise GateError(f"{case.benchmark_id}: plugin_rules entries need rule_id")
        rule_id = rule["rule_id"]
        required_mode = rule.get("operand_mode")
        matches = [claim for claim in claims if claim.get("rule_id") == rule_id]
        if not matches:
            raise GateError(f"{case.benchmark_id}: missing required plugin rule {rule_id!r}")
        if required_mode is not None:
            modes = [claim.get("operand_mode") or "direct" for claim in matches]
            if required_mode not in modes:
                raise GateError(
                    f"{case.benchmark_id}: rule {rule_id!r} lacks operand_mode={required_mode!r}"
                )
    if not generated_rust_source.is_file():
        raise GateError(f"{case.benchmark_id}: generated Rust source missing for expectations")
    source = generated_rust_source.read_text(encoding="utf-8")
    for needle in expectations.get("generated_rust_source_substrings", []) or []:
        if not isinstance(needle, str) or not needle:
            raise GateError(
                f"{case.benchmark_id}: generated_rust_source_substrings must be strings"
            )
        if needle not in source:
            raise GateError(
                f"{case.benchmark_id}: generated Rust source lacks required substring {needle!r}"
            )
    if "rust_functions" in expectations:
        _enforce_rust_function_expectations(
            case.benchmark_id,
            source,
            expectations["rust_functions"],
        )


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
        raise GateError(f"{case.qualname} route {record.get('route')!r} != {case.expected_route!r}")
    if record.get("native_status") != "accepted":
        raise GateError(f"{case.qualname} native status is {record.get('native_status')!r}")
    generated_rust_source = case.project_root / ".rextio/generated/rust/src/lib.rs"
    # Raw check first (fast fail); portable evidence must also carry the proof.
    enforce_generated_expectations(
        case,
        check,
        generated_rust_source=generated_rust_source,
    )
    artifact, artifact_paths, artifact_declaration = find_native_artifact(case, build)
    portable_root = report_root / "portable"
    portable_check_path = portable_root / "check.json"
    portable_build_path = portable_root / "build.json"
    portable_check = write_portable_snapshot(portable_check_path, check, repository_root)
    portable_build = write_portable_snapshot(portable_build_path, build, repository_root)
    require_portable(portable_check, repository_root)
    require_portable(portable_build, repository_root)
    # Evidence role check_report points at the portable snapshot — enforce there.
    enforce_generated_expectations(
        case,
        portable_check,
        generated_rust_source=generated_rust_source,
    )
    portable_record = route_record(portable_check, case.qualname)
    if portable_record.get("route") != record.get("route") or portable_record.get(
        "native_status"
    ) != record.get("native_status"):
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
        "integration_target_config": repository_root / "profiles/next-candidate.toml",
        "repository_manifest": repository_root / "pyproject.toml",
        "report_schema": repository_root / "schema" / "benchmark-report-v1.schema.json",
        "publication_policy": repository_root / "PUBLICATION.md",
        "bootstrap_script": repository_root / "scripts" / "bootstrap.sh",
        "build_script": repository_root / "scripts" / "build.sh",
        "benchmark_script": repository_root / "scripts" / "benchmark.sh",
        "verify_script": repository_root / "scripts" / "verify.sh",
        "run_script": repository_root / "scripts" / "run.sh",
        "generated_rust_manifest": case.project_root / ".rextio/generated/rust/Cargo.toml",
        "generated_rust_lock": case.project_root / ".rextio/generated/rust/Cargo.lock",
        "generated_rust_source": generated_rust_source,
        "generated_python_wrapper": case.project_root / ".rextio/generated/python" / module_path,
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
