from __future__ import annotations

import hashlib
import json
import math
import statistics
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

import jsonschema

from .cohort import cohort_id, validate_cohort
from .models import BenchmarkCase, load_cases, paired_orders
from .output_table import validate_output_table
from .portability import require_portable
from .processes import THREAD_ENVIRONMENT
from .statistics import paired_bootstrap_interval, paired_speedups, summarize
from .verification import (
    GateError,
    outputs_close,
    resolve_logical_path,
    sha256_file,
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)


def _numbers_equal(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-6)


def _require_numbers(left: list[float], right: list[float], message: str) -> None:
    _require(len(left) == len(right), f"{message}: length mismatch")
    _require(
        all(_numbers_equal(a, b) for a, b in zip(left, right, strict=True)),
        message,
    )


def _git(
    repository_root: Path,
    arguments: list[str],
    *,
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository_root,
        capture_output=True,
        text=text,
    )


def _current_commit(repository_root: Path) -> str | None:
    result = _git(repository_root, ["rev-parse", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else None


def _worktree_clean(repository_root: Path) -> bool:
    result = _git(repository_root, ["status", "--porcelain"])
    return result.returncode == 0 and not result.stdout.strip()


def _run_commit_available(
    repository_root: Path,
    run_commit: str | None,
    current_commit: str | None,
) -> bool:
    if not run_commit or not current_commit:
        return False
    exists = _git(repository_root, ["cat-file", "-e", f"{run_commit}^{{commit}}"])
    if exists.returncode:
        return False
    ancestor = _git(repository_root, ["merge-base", "--is-ancestor", run_commit, current_commit])
    return ancestor.returncode == 0


def _git_blob(repository_root: Path, commit: str, logical_path: str) -> bytes | None:
    result = _git(repository_root, ["show", f"{commit}:{logical_path}"], text=False)
    return result.stdout if result.returncode == 0 else None


def _verify_bundle_record(
    role: str,
    record: dict[str, Any],
    bundled: dict[str, Any],
    repository_root: Path,
) -> Path:
    _require(
        set(bundled)
        == {"kind", "logical_path", "bundle_path", "sha256", "size_bytes"},
        f"bundle record shape differs: {role}",
    )
    _require(bundled["kind"] == "run-output", f"invalid bundle kind: {role}")
    _require(
        bundled["logical_path"] == record["path"],
        f"bundle logical path differs: {role}",
    )
    _require(bundled["sha256"] == record["sha256"], f"bundle digest declaration differs: {role}")
    bundle_path = resolve_logical_path(bundled["bundle_path"], repository_root)
    _require(bundle_path.is_file(), f"bundled evidence file is missing: {role}")
    _require(sha256_file(bundle_path) == record["sha256"], f"bundle digest changed: {role}")
    _require(
        bundle_path.stat().st_size == bundled["size_bytes"],
        f"bundle size changed: {role}",
    )
    return bundle_path


def _verify_evidence(
    gate: dict[str, Any],
    repository_root: Path,
    run_commit: str | None,
    *,
    bundle_evidence: dict[str, Any] | None = None,
) -> None:
    evidence = gate["evidence"]
    _require(gate["artifact_role"] in evidence, "artifact role is missing")
    _require(
        gate["artifact"] == evidence[gate["artifact_role"]]["path"],
        "artifact path differs from its evidence role",
    )
    declaration = gate["artifact_declaration"]
    for key in ("declared_path", "runtime_path"):
        _require(not Path(declaration[key]).is_absolute(), "absolute artifact declaration")
        resolve_logical_path(declaration[key], repository_root)
    _require(
        declaration["runtime_path"] == gate["artifact"],
        "runtime artifact declaration differs",
    )
    if declaration["kind"] == "native-extension":
        _require(
            declaration["declared_path"]
            == evidence["declared_native_artifact"]["path"],
            "declared installed artifact differs",
        )
    seen_paths: set[str] = set()
    resolved_outputs: dict[str, Path] = {}
    for role, record in evidence.items():
        logical = record["path"]
        _require(not Path(logical).is_absolute(), f"{role} uses an absolute path")
        path = resolve_logical_path(logical, repository_root)
        _require(logical not in seen_paths, f"duplicate evidence path: {logical}")
        seen_paths.add(logical)
        bundled = (bundle_evidence or {}).get(role)
        bundled_path = None
        if bundled is not None:
            _require(record["kind"] == "run-output", f"run input cannot use bundle: {role}")
            bundled_path = _verify_bundle_record(role, record, bundled, repository_root)
        blob = _git_blob(repository_root, run_commit, logical) if run_commit else None
        if record["kind"] == "run-input" and run_commit:
            _require(blob is not None, f"run input is absent from commit: {logical}")
            actual = hashlib.sha256(blob).hexdigest()
            _require(actual == record["sha256"], f"run-commit digest changed: {role}")
        elif path.is_file():
            _require(
                sha256_file(path) == record["sha256"],
                f"evidence digest changed: {role}",
            )
            if record["kind"] == "run-output":
                resolved_outputs[role] = path
        else:
            _require(
                record["kind"] == "run-output" and bundled_path is not None,
                f"bundled evidence file is missing: {role}",
            )
            resolved_outputs[role] = bundled_path
    if bundle_evidence is not None:
        _require(
            not set(bundle_evidence).difference(evidence),
            "bundle contains unknown evidence roles",
        )

    build_report_path = resolved_outputs["build_report"]
    build = json.loads(build_report_path.read_text(encoding="utf-8"))
    if declaration["kind"] == "executable":
        declared = (build.get("executable_build") or {}).get("path")
        _require(
            declared
            and Path(str(declared)).parts[-2:]
            == Path(declaration["declared_path"]).parts[-2:],
            "executable artifact differs from build.json declaration",
        )
    else:
        build_python = build.get("build_python")
        installed = (build.get("native_build") or {}).get("installed_path")
        _require(
            build_python
            and Path(str(build_python)).parts[-3:] == (".rextio", "build", "python"),
            "runtime tree differs from build.json declaration",
        )
        _require(
            installed
            and Path(str(installed)).parts[-4:]
            == Path(declaration["declared_path"]).parts[-4:],
            "native artifact differs from build.json declaration",
        )


def _load_canonical_bundle(
    report: dict[str, Any],
    report_path: Path,
    repository_root: Path,
) -> dict[str, dict[str, Any]] | None:
    metadata = report.get("canonical_bundle")
    if metadata is None:
        return None
    manifest_path = resolve_logical_path(metadata["manifest_path"], repository_root)
    _require(manifest_path.is_file(), "canonical bundle manifest is missing")
    _require(
        sha256_file(manifest_path) == metadata["manifest_sha256"],
        "canonical bundle manifest digest changed",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base_keys = {
        "schema_version",
        "run_commit",
        "source_report_path",
        "canonical_report_path",
        "file_count",
        "object_count",
        "logical_bytes",
        "stored_bytes",
        "cases",
    }
    version = manifest["schema_version"]
    _require(version in {1, 2}, "canonical bundle schema differs")
    _require(
        set(manifest) == (base_keys if version == 1 else base_keys | {"cohort"}),
        "canonical bundle manifest shape differs",
    )
    _require(manifest["run_commit"] == report["repository"]["commit"], "bundle commit differs")
    _require(
        manifest["canonical_report_path"] == resolve_logical_path(
            manifest["canonical_report_path"], repository_root
        ).relative_to(repository_root.resolve()).as_posix(),
        "canonical report path is not portable",
    )
    _require(
        report_path.resolve()
        == resolve_logical_path(manifest["canonical_report_path"], repository_root),
        "canonical report path differs from manifest",
    )
    bundle_root = manifest_path.parent
    _require(
        bundle_root.parent == (repository_root / "results" / "canonical").resolve(),
        "canonical bundle is outside results/canonical",
    )
    _require(
        report_path.resolve() == bundle_root / "report.json",
        "canonical report is outside its bundle",
    )
    resolve_logical_path(manifest["source_report_path"], repository_root)
    if version == 2:
        cohort = manifest["cohort"]
        _require(
            set(cohort)
            == {
                "cohort_id",
                "selection",
                "selected_report_index",
                "report_count",
                "stability_summary_path",
                "stability_summary_sha256",
                "reports",
            },
            "cohort manifest shape differs",
        )
        _require(cohort["selection"] == "chronological-first", "cohort selection differs")
        _require(cohort["selected_report_index"] == 0, "cohort selected report differs")
        _require(cohort["report_count"] == 3, "cohort report count differs")
        for key in (
            "cohort_id",
            "report_count",
            "stability_summary_path",
            "stability_summary_sha256",
        ):
            _require(metadata.get(key) == cohort[key], f"canonical {key} differs")
        records = cohort["reports"]
        _require(len(records) == 3, "cohort must contain three raw reports")
        raw_reports = []
        digests = []
        for index, record in enumerate(records):
            _require(record["index"] == index, "cohort report index differs")
            _require(record["selected"] is (index == 0), "cohort selection differs")
            bundled_report = resolve_logical_path(record["bundle_path"], repository_root)
            _require(bundled_report.is_file(), "bundled raw report is missing")
            _require(
                sha256_file(bundled_report) == record["sha256"],
                "bundled raw report digest changed",
            )
            raw_reports.append(json.loads(bundled_report.read_text(encoding="utf-8")))
            digests.append(record["sha256"])
        _require(cohort_id(digests) == cohort["cohort_id"], "cohort id differs")
        recomputed = validate_cohort(raw_reports)
        recomputed["cohort_id"] = cohort["cohort_id"]
        recomputed["reports"] = records
        stability_path = resolve_logical_path(
            cohort["stability_summary_path"], repository_root
        )
        _require(stability_path.is_file(), "stability summary is missing")
        _require(
            sha256_file(stability_path) == cohort["stability_summary_sha256"],
            "stability summary digest changed",
        )
        _require(
            json.loads(stability_path.read_text(encoding="utf-8")) == recomputed,
            "stability summary differs from raw reports",
        )
        selected = deepcopy(report)
        selected.pop("canonical_bundle", None)
        _require(selected == raw_reports[0], "canonical report is not chronological first")

    expected: dict[str, dict[str, Any]] = {}
    for case in report["cases"]:
        if not case["eligible"]:
            continue
        expected[case["id"]] = {
            role: record
            for role, record in case["gate"]["evidence"].items()
            if record["kind"] == "run-output"
        }
    _require(set(manifest["cases"]) == set(expected), "canonical bundle case set differs")
    logical_bytes = 0
    objects: dict[str, tuple[str, int]] = {}
    result: dict[str, dict[str, Any]] = {}
    for case_id, records in expected.items():
        case_manifest = manifest["cases"][case_id]
        _require(set(case_manifest) == {"roles"}, f"bundle case shape differs: {case_id}")
        roles = case_manifest["roles"]
        _require(set(roles) == set(records), f"bundle evidence roles differ: {case_id}")
        result[case_id] = roles
        for role, record in records.items():
            bundled = roles[role]
            expected_bundle_path = (
                Path("results")
                / "canonical"
                / bundle_root.name
                / "objects"
                / "sha256"
                / record["sha256"]
            ).as_posix()
            _require(
                bundled["bundle_path"] == expected_bundle_path,
                f"bundle object path differs: {case_id}/{role}",
            )
            _verify_bundle_record(role, record, bundled, repository_root)
            logical_bytes += bundled["size_bytes"]
            prior = objects.setdefault(
                bundled["bundle_path"],
                (bundled["sha256"], bundled["size_bytes"]),
            )
            _require(
                prior == (bundled["sha256"], bundled["size_bytes"]),
                f"bundle object declaration differs: {case_id}/{role}",
            )
    stored_bytes = sum(size for _, size in objects.values())
    counts = {
        "file_count": sum(len(records) for records in expected.values()),
        "object_count": len(objects),
        "logical_bytes": logical_bytes,
        "stored_bytes": stored_bytes,
    }
    for key, value in counts.items():
        _require(manifest[key] == value, f"manifest {key} differs")
        _require(metadata[key] == value, f"report bundle {key} differs")
    return result


def _verify_lane(
    case: BenchmarkCase,
    lane_name: str,
    lane: dict[str, Any],
    minimum_sample_ns: int,
    expected_samples: int,
) -> list[dict[str, Any]]:
    observations = lane["observations"]
    flattened: list[float] = []
    flattened_sizes: list[int] = []
    flattened_elapsed: list[float] = []
    for observation in observations:
        samples = observation["samples_ns"]
        sizes = observation["batch_sizes"]
        elapsed = observation["batch_elapsed_ns"]
        _require(
            len(samples) == expected_samples
            and len(samples) == len(sizes) == len(elapsed),
            f"{case.benchmark_id}/{lane_name} batch evidence",
        )
        _require(not Path(observation["module_path"]).is_absolute(), "absolute module path")
        for sample, size, batch_ns in zip(samples, sizes, elapsed, strict=True):
            _require(sample > 0 and size > 0, "non-positive sample or batch")
            _require(batch_ns >= minimum_sample_ns, "retained batch below minimum duration")
            _require(_numbers_equal(sample * size, batch_ns), "sample/batch arithmetic mismatch")
        flattened.extend(samples)
        flattened_sizes.extend(sizes)
        flattened_elapsed.extend(elapsed)
    _require_numbers(
        flattened,
        lane["raw_samples_ns"],
        f"{case.benchmark_id}/{lane_name} raw samples",
    )
    _require(flattened_sizes == lane["batch_sizes"], "flattened batch sizes differ")
    _require_numbers(flattened_elapsed, lane["batch_elapsed_ns"], "flattened batch elapsed differs")
    recomputed = summarize(flattened)
    for key, value in recomputed.items():
        reported = lane["steady_state"][key]
        if isinstance(value, int):
            _require(value == reported, f"{case.benchmark_id}/{lane_name} {key}")
        else:
            _require(_numbers_equal(value, reported), f"{case.benchmark_id}/{lane_name} {key}")
    _require(
        lane["module_files"] == [item["module_path"] for item in observations],
        "module path summary differs",
    )
    return observations


def _is_under(logical: str, parent: str) -> bool:
    path = Path(logical)
    root = Path(parent)
    return len(path.parts) > len(root.parts) and path.parts[: len(root.parts)] == root.parts


def _verify_environment(
    case: BenchmarkCase,
    environment: dict[str, Any],
    repository_root: Path,
) -> None:
    expected_prefix = (Path("profiles") / case.profile / ".venv").as_posix()
    _require(environment["profile_prefix"] == expected_prefix, "profile prefix differs")
    resolve_logical_path(environment["profile_prefix"], repository_root)
    provenance = environment["module_provenance"]
    _require(set(provenance) == set(case.required_modules), "required module set differs")
    for module_name, record in provenance.items():
        for key in ("file", "site_packages"):
            _require(not Path(record[key]).is_absolute(), f"{module_name} has absolute path")
            resolve_logical_path(record[key], repository_root)
        _require(
            _is_under(record["site_packages"], expected_prefix),
            f"{module_name} site-packages escaped selected profile",
        )
        _require(
            _is_under(record["file"], record["site_packages"]),
            f"{module_name} module escaped selected profile",
        )
    active = environment["active_module_provenance"]
    if case.kind == "executable":
        _require(active == {}, "executable active module provenance must be empty")
    else:
        expected_lanes = {
            "python-source",
            "rextio-fallback",
            "rextio-native",
        }
        _require(set(active) == expected_lanes, "active provenance lane set differs")
        generated_root = (
            Path("cases") / case.project / ".rextio" / "build" / "python"
        ).as_posix()
        for lane, modules in active.items():
            _require(
                set(modules) == set(case.required_modules),
                f"{lane} active module set differs",
            )
            for module_name, record in modules.items():
                for key in ("file", "root"):
                    _require(
                        not Path(record[key]).is_absolute(),
                        f"{lane}/{module_name} has absolute active path",
                    )
                    resolve_logical_path(record[key], repository_root)
                installed_record = provenance[module_name]
                generated_rextio = module_name == "rextio" and lane != "python-source"
                if generated_rextio:
                    _require(
                        record["kind"] == "generated-runtime",
                        f"{lane} rextio runtime kind differs",
                    )
                    _require(
                        record["root"] == generated_root,
                        "generated runtime root differs",
                    )
                    _require(
                        _is_under(record["file"], f"{generated_root}/rextio"),
                        "generated runtime file escaped generated package",
                    )
                else:
                    _require(
                        record["kind"] == "installed",
                        f"{lane}/{module_name} runtime kind differs",
                    )
                    _require(
                        record["root"] == installed_record["site_packages"],
                        f"{lane}/{module_name} active root differs",
                    )
                    _require(
                        record["file"] == installed_record["file"],
                        f"{lane}/{module_name} active file differs",
                    )
    for name, value in THREAD_ENVIRONMENT.items():
        _require(environment[name] == value, f"thread setting differs: {name}")
    effective = environment["effective_threads"]
    if case.profile == "torch-cpu":
        _require(
            effective.get("torch") == {
                "intraop_threads": 1,
                "interop_threads": 1,
            },
            "Torch effective threads differ",
        )
    if case.profile == "tensorflow-cpu":
        _require(
            effective.get("tensorflow") == {
                "intraop_threads": 1,
                "interop_threads": 1,
            },
            "TensorFlow effective threads differ",
        )


def _verify_case_measurements(
    case: BenchmarkCase,
    case_report: dict[str, Any],
    configuration: dict[str, Any],
    repository_root: Path | None = None,
) -> None:
    contract = case_report["timing_contract"]
    _require(contract is not None, "eligible case has no timing contract")
    _require(
        contract["minimum_sample_ns"] == configuration["minimum_sample_ns"],
        "case timing minimum differs from suite configuration",
    )
    if case.kind == "executable":
        _require(contract["unit"] == "fresh-process", "executable timing unit differs")
        _require(contract["includes_process_startup"], "executable excludes process startup")
    else:
        _require(contract["unit"] == "function-call", "module timing unit differs")
        _require(not contract["includes_process_startup"], "module includes process startup")
    root = repository_root or case.project_root.parents[1]
    _verify_environment(case, case_report["environment"], root)
    lanes = case_report["lanes"]
    source = _verify_lane(
        case,
        "python-source",
        lanes["python-source"],
        configuration["minimum_sample_ns"],
        configuration["samples"],
    )
    native = _verify_lane(
        case,
        "rextio-native",
        lanes["rextio-native"],
        configuration["minimum_sample_ns"],
        configuration["samples"],
    )
    fallback = (
        _verify_lane(
            case,
            "rextio-fallback",
            lanes["rextio-fallback"],
            configuration["minimum_sample_ns"],
            configuration["samples"],
        )
        if case.kind == "python-module"
        else []
    )
    paired = case_report["paired"]
    pair_records = paired["observations"]
    expected_orders = [list(order) for order in paired_orders(configuration["pairs"])]
    _require(paired["orders"] == expected_orders, "counterbalanced orders differ")
    _require(len(pair_records) == len(expected_orders), "pair evidence count differs")
    _require(len(source) == len(native) == len(pair_records), "lane observation count differs")
    _require(
        len(fallback) == (1 if case.kind == "python-module" else 0),
        "fallback observation count differs",
    )
    evidence = case_report["correctness"]["evidence"]
    referenced_outputs = {
        observation["normalized_output_ref"]
        for lane in lanes.values()
        for observation in lane["observations"]
    }
    referenced_outputs.add(evidence["reference_output_ref"])
    if evidence["fallback_output_ref"] is not None:
        referenced_outputs.add(evidence["fallback_output_ref"])
    output_table = validate_output_table(
        case_report["output_table"],
        referenced_outputs,
    )
    source_medians: list[float] = []
    native_medians: list[float] = []
    reference = output_table[evidence["reference_output_ref"]]
    for index, pair in enumerate(pair_records):
        _require(
            pair["index"] == index and pair["order"] == expected_orders[index],
            "pair identity differs",
        )
        _require(
            0 <= pair["source_observation"] < len(source)
            and 0 <= pair["native_observation"] < len(native),
            "pair observation index is out of range",
        )
        source_obs = source[pair["source_observation"]]
        native_obs = native[pair["native_observation"]]
        _require(
            source_obs["pair_index"] == index == native_obs["pair_index"],
            "pair index mapping differs",
        )
        source_output = output_table[source_obs["normalized_output_ref"]]
        native_output = output_table[native_obs["normalized_output_ref"]]
        _require(
            outputs_close(
                source_output,
                native_output,
                absolute=case.tolerance["absolute"],
                relative=case.tolerance["relative"],
            ),
            f"{case.benchmark_id} source/native correctness",
        )
        _require(
            outputs_close(
                reference,
                source_output,
                absolute=case.tolerance["absolute"],
                relative=case.tolerance["relative"],
            ),
            f"{case.benchmark_id} reference output differs",
        )
        source_medians.append(statistics.median(source_obs["samples_ns"]))
        native_medians.append(statistics.median(native_obs["samples_ns"]))
    fallback_output_ref = evidence["fallback_output_ref"]
    if fallback:
        _require(
            fallback_output_ref == fallback[0]["normalized_output_ref"],
            "fallback evidence differs",
        )
        fallback_output = output_table[fallback_output_ref]
        _require(
            outputs_close(
                reference,
                fallback_output,
                absolute=case.tolerance["absolute"],
                relative=case.tolerance["relative"],
            ),
            f"{case.benchmark_id} source/fallback correctness",
        )
    else:
        _require(fallback_output_ref is None, "executable cannot claim fallback output")
    _require(case_report["correctness"]["status"] == "passed", "correctness status differs")
    _require_numbers(source_medians, paired["source_medians_ns"], "source pair medians differ")
    _require_numbers(native_medians, paired["native_medians_ns"], "native pair medians differ")
    speedups = paired_speedups(source_medians, native_medians)
    _require_numbers(speedups, paired["speedups"], "paired speedups differ")
    _require(
        _numbers_equal(statistics.median(speedups), paired["median_speedup"]),
        "median speedup differs",
    )
    interval = paired_bootstrap_interval(
        source_medians,
        native_medians,
        resamples=configuration["bootstrap_resamples"],
    )
    _require_numbers(list(interval), paired["bootstrap_95"], "bootstrap interval differs")


def verify_report(report_path: Path, repository_root: Path) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    try:
        require_portable(report, repository_root)
    except ValueError as error:
        raise GateError(str(error)) from error
    schema_path = repository_root / "schema" / "benchmark-report-v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(report)
    canonical_bundle = _load_canonical_bundle(report, report_path, repository_root)
    known = {case.benchmark_id: case for case in load_cases(repository_root)}
    identifiers = [case["id"] for case in report["cases"]]
    _require(len(identifiers) == len(set(identifiers)), "case ids are not unique")
    _require(set(identifiers) == set(known), "report case set differs from manifests")
    for case_report in report["cases"]:
        case = known[case_report["id"]]
        if not case_report["eligible"]:
            _require(case_report["blockers"], f"{case.benchmark_id} blocked without reason")
            continue
        _require(not case_report["blockers"], f"{case.benchmark_id} eligible with blockers")
        gate = case_report["gate"]
        _require(gate["route"] == case.expected_route, f"{case.benchmark_id} route mismatch")
        _require(gate["native_status"] == "accepted", f"{case.benchmark_id} not accepted")
        _require(gate["native_build_status"] == "built", f"{case.benchmark_id} not built")
        _verify_evidence(
            gate,
            repository_root,
            report["repository"]["commit"],
            bundle_evidence=(
                canonical_bundle[case.benchmark_id]
                if canonical_bundle is not None
                else None
            ),
        )
        _verify_case_measurements(
            case,
            case_report,
            report["configuration"],
            repository_root,
        )
        if report["mode"] == "publish":
            _require(len(case_report["paired"]["orders"]) >= 10, "too few publish pairs")
    current = _current_commit(repository_root)
    run_commit = report["repository"]["commit"]
    commit_available = _run_commit_available(repository_root, run_commit, current)
    all_cases_eligible = all(
        case["eligible"] and not case["blockers"] for case in report["cases"]
    )
    recomputed_publishable = (
        report["mode"] == "publish"
        and run_commit is not None
        and not report["repository"]["dirty"]
        and commit_available
        and _worktree_clean(repository_root)
        and report["eligibility"]["status"] == "eligible"
        and not report["eligibility"]["blockers"]
        and all_cases_eligible
    )
    _require(report["publishable"] == recomputed_publishable, "publishability differs")
    _require(
        report["eligibility"]["status"]
        == ("eligible" if report["publishable"] else "blocked"),
        "global eligibility status differs",
    )
    return report
