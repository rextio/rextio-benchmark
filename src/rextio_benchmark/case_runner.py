from __future__ import annotations

import statistics
import sys
from pathlib import Path
from typing import Any

from .models import BenchmarkCase, paired_orders
from .output_table import OutputTable
from .processes import (
    THREAD_ENVIRONMENT,
    invoke_command,
    invoke_worker,
    measure_command_samples,
    sanitized_environment,
)
from .statistics import paired_bootstrap_interval, paired_speedups, summarize
from .verification import (
    GateError,
    gate_build,
    logical_path,
    outputs_close,
    require_import_under,
)
from .worker import _module_provenance, package_vcs_provenance, package_versions

MODE_SETTINGS = {
    "quick": {
        "warmups": 1,
        "samples": 3,
        "minimum_sample_ns": 10_000_000,
        "pairs": 2,
        "bootstrap_resamples": 1_000,
    },
    "publish": {
        "warmups": 5,
        "samples": 11,
        "minimum_sample_ns": 200_000_000,
        "pairs": 12,
        "bootstrap_resamples": 10_000,
    },
}


def _lane_summary(invocations: list[dict[str, Any]]) -> dict[str, Any]:
    samples = [sample for invocation in invocations for sample in invocation["samples_ns"]]
    return {
        "steady_state": summarize(samples),
        "raw_samples_ns": samples,
        "import_ns": [
            invocation["import_ns"]
            for invocation in invocations
            if invocation["import_ns"] is not None
        ],
        "first_call_ns": [
            invocation["first_call_ns"]
            for invocation in invocations
            if invocation["first_call_ns"] is not None
        ],
        "batch_sizes": [
            size for invocation in invocations for size in invocation["batch_sizes"]
        ],
        "batch_elapsed_ns": [
            elapsed
            for invocation in invocations
            for elapsed in invocation["batch_elapsed_ns"]
        ],
        "module_files": [invocation["module_path"] for invocation in invocations],
        "pids": [invocation["pid"] for invocation in invocations if invocation["pid"]],
        "observations": invocations,
    }


def _worker_observation(
    result: dict[str, Any],
    *,
    pair_index: int | None,
    repository_root: Path,
    output_table: OutputTable,
) -> dict[str, Any]:
    return {
        "pair_index": pair_index,
        "samples_ns": result["samples_ns"],
        "normalized_output_ref": output_table.intern(result["output"]),
        "import_ns": result["import_ns"],
        "first_call_ns": result["first_call_ns"],
        "batch_sizes": result["batch_sizes"],
        "batch_elapsed_ns": result["batch_elapsed_ns"],
        "module_path": logical_path(Path(result["module_file"]), repository_root),
        "pid": result["pid"],
    }


def _correct(case: BenchmarkCase, left: object, right: object) -> bool:
    return outputs_close(
        left,
        right,
        absolute=case.tolerance["absolute"],
        relative=case.tolerance["relative"],
    )


def _portable_environment(
    environment: dict[str, Any],
    repository_root: Path,
) -> dict[str, Any]:
    portable = dict(environment)
    portable["profile_prefix"] = logical_path(
        Path(environment["profile_prefix"]),
        repository_root,
    )
    portable["module_provenance"] = {
        name: {
            "file": logical_path(Path(record["file"]), repository_root),
            "site_packages": logical_path(
                Path(record["site_packages"]),
                repository_root,
            ),
        }
        for name, record in environment["module_provenance"].items()
    }
    portable["active_module_provenance"] = {
        lane: {
            name: {
                "file": logical_path(Path(record["file"]), repository_root),
                "root": logical_path(Path(record["root"]), repository_root),
                "kind": record["kind"],
            }
            for name, record in provenance.items()
        }
        for lane, provenance in environment["active_module_provenance"].items()
    }
    return portable


def run_module_case(
    repository_root: Path,
    python: Path,
    case: BenchmarkCase,
    mode: str,
) -> dict[str, Any]:
    settings = MODE_SETTINGS[mode]
    gate = gate_build(case, repository_root)
    output_table = OutputTable()
    invocations: dict[str, list[dict[str, Any]]] = {
        "python-source": [],
        "rextio-fallback": [],
        "rextio-native": [],
    }
    fallback = invoke_worker(
        repository_root,
        python,
        case,
        "rextio-fallback",
        warmups=settings["warmups"],
        samples=settings["samples"],
        minimum_sample_ns=settings["minimum_sample_ns"],
    )
    require_import_under(fallback["module_file"], case.generated_python_root)
    fallback_observation = _worker_observation(
        fallback,
        pair_index=None,
        repository_root=repository_root,
        output_table=output_table,
    )
    invocations["rextio-fallback"].append(fallback_observation)
    installed_provenance = fallback["environment"]["module_provenance"]
    active_module_provenance = {
        "rextio-fallback": fallback["environment"]["active_module_provenance"]
    }

    paired_source: list[float] = []
    paired_native: list[float] = []
    pair_evidence: list[dict[str, Any]] = []
    reference_output_ref: str | None = None
    native_metadata: dict[str, Any] | None = None
    for pair_index, order in enumerate(paired_orders(settings["pairs"])):
        pair_results: dict[str, dict[str, Any]] = {}
        for lane in order:
            result = invoke_worker(
                repository_root,
                python,
                case,
                lane,
                warmups=settings["warmups"],
                samples=settings["samples"],
                minimum_sample_ns=settings["minimum_sample_ns"],
            )
            expected = case.source_root if lane == "python-source" else case.generated_python_root
            require_import_under(result["module_file"], expected)
            observation = _worker_observation(
                result,
                pair_index=pair_index,
                repository_root=repository_root,
                output_table=output_table,
            )
            invocations[lane].append(observation)
            pair_results[lane] = observation
            if lane == "python-source" and reference_output_ref is None:
                reference_output_ref = observation["normalized_output_ref"]
            if lane == "rextio-native" and native_metadata is None:
                native_metadata = result
            if result["environment"]["module_provenance"] != installed_provenance:
                raise GateError("installed module provenance differs between lanes")
            active = result["environment"]["active_module_provenance"]
            if lane in active_module_provenance:
                if active_module_provenance[lane] != active:
                    raise GateError(f"{lane} active module provenance differs")
            else:
                active_module_provenance[lane] = active
        source = pair_results["python-source"]
        native = pair_results["rextio-native"]
        if not _correct(
            case,
            output_table.resolve(source["normalized_output_ref"]),
            output_table.resolve(native["normalized_output_ref"]),
        ):
            raise GateError("source/native output mismatch")
        paired_source.append(statistics.median(source["samples_ns"]))
        paired_native.append(statistics.median(native["samples_ns"]))
        pair_evidence.append(
            {
                "index": pair_index,
                "order": list(order),
                "source_observation": len(invocations["python-source"]) - 1,
                "native_observation": len(invocations["rextio-native"]) - 1,
            }
        )

    if reference_output_ref is None or not _correct(
        case,
        output_table.resolve(reference_output_ref),
        output_table.resolve(fallback_observation["normalized_output_ref"]),
    ):
        raise GateError("source/fallback output mismatch")
    interval = paired_bootstrap_interval(
        paired_source,
        paired_native,
        resamples=settings["bootstrap_resamples"],
    )
    ratios = paired_speedups(paired_source, paired_native)
    return {
        "id": case.benchmark_id,
        "project": case.project,
        "description": case.raw["description"],
        "context": case.raw.get("context"),
        "negative_control": bool(case.raw.get("negative_control", False)),
        "kind": case.kind,
        "output_table": output_table.values(),
        "timing_contract": {
            "unit": "function-call",
            "process_model": "fresh-persistent-worker-per-observation",
            "minimum_sample_ns": settings["minimum_sample_ns"],
            "includes_process_startup": False,
        },
        "gate": gate,
        "correctness": {
            "status": "passed",
            "tolerance": case.tolerance,
            "evidence": {
                "reference_output_ref": reference_output_ref,
                "fallback_output_ref": fallback_observation["normalized_output_ref"],
            },
        },
        "lanes": {lane: _lane_summary(values) for lane, values in invocations.items()},
        "paired": {
            "orders": [list(order) for order in paired_orders(settings["pairs"])],
            "source_medians_ns": paired_source,
            "native_medians_ns": paired_native,
            "speedups": ratios,
            "median_speedup": statistics.median(ratios),
            "bootstrap_95": list(interval),
            "observations": pair_evidence,
        },
        "eligible": True,
        "blockers": [],
        "packages": (native_metadata or {})["packages"],
        "package_provenance": (native_metadata or {}).get("package_provenance") or {},
        "python": (native_metadata or {})["python"],
        "environment": _portable_environment(
            {
                **(native_metadata or {})["environment"],
                "active_module_provenance": active_module_provenance,
            },
            repository_root,
        ),
    }


def run_executable_case(
    repository_root: Path,
    python: Path,
    case: BenchmarkCase,
    mode: str,
) -> dict[str, Any]:
    settings = MODE_SETTINGS[mode]
    gate = gate_build(case, repository_root)
    output_table = OutputTable()
    artifact = repository_root / gate["artifact"]
    extra_arguments = [str(value) for value in case.raw.get("arguments", [])]
    source_argv = [case.module, *extra_arguments]
    source_code = (
        f"from {case.module} import {case.function}; "
        f"raise SystemExit({case.function}({source_argv!r}))"
    )
    commands = {
        "python-source": [str(python), "-c", source_code],
        "rextio-native": [str(artifact), *extra_arguments],
    }
    if Path(sys.executable).resolve() != python.resolve():
        raise GateError(
            f"controller interpreter {sys.executable} is not selected profile {python}"
        )
    environment = sanitized_environment()
    environment.update(THREAD_ENVIRONMENT)
    environment["PYTHONPATH"] = str(case.source_root)
    environment.pop("REXTIO_NATIVE_MODE", None)
    environment.pop("REXTIO_DISABLE_BOUNDARY_FALLBACK", None)

    first_calls = {
        lane: invoke_command(command, cwd=repository_root, environment=environment)
        for lane, command in commands.items()
    }
    if first_calls["python-source"]["stdout"] != first_calls["rextio-native"]["stdout"]:
        raise GateError("source/native executable output mismatch")
    for _ in range(settings["warmups"]):
        for command in commands.values():
            invoke_command(command, cwd=repository_root, environment=environment)

    invocations: dict[str, list[dict[str, Any]]] = {
        "python-source": [],
        "rextio-native": [],
    }
    batch_sizes = {"python-source": 1, "rextio-native": 1}
    pair_evidence: list[dict[str, Any]] = []
    paired_source: list[float] = []
    paired_native: list[float] = []
    orders = paired_orders(settings["pairs"])
    module_paths = {
        "python-source": logical_path(
            case.project_root
            / "src"
            / Path(*case.module.split(".")).with_suffix(".py"),
            repository_root,
        ),
        "rextio-native": gate["artifact"],
    }
    for pair_index, order in enumerate(orders):
        pair_results: dict[str, dict[str, Any]] = {}
        for lane in order:
            result = measure_command_samples(
                commands[lane],
                samples=settings["samples"],
                minimum_sample_ns=settings["minimum_sample_ns"],
                initial_batch_size=batch_sizes[lane],
                cwd=repository_root,
                environment=environment,
            )
            batch_sizes[lane] = result["next_batch_size"]
            observation = {
                "pair_index": pair_index,
                "samples_ns": result["samples_ns"],
                "normalized_output_ref": output_table.intern(result["output"].strip()),
                "import_ns": None,
                "first_call_ns": None,
                "batch_sizes": result["batch_sizes"],
                "batch_elapsed_ns": result["batch_elapsed_ns"],
                "module_path": module_paths[lane],
                "pid": None,
            }
            invocations[lane].append(observation)
            pair_results[lane] = observation
        source = pair_results["python-source"]
        native = pair_results["rextio-native"]
        if output_table.resolve(source["normalized_output_ref"]) != output_table.resolve(
            native["normalized_output_ref"]
        ):
            raise GateError("paired executable output mismatch")
        paired_source.append(statistics.median(source["samples_ns"]))
        paired_native.append(statistics.median(native["samples_ns"]))
        pair_evidence.append(
            {
                "index": pair_index,
                "order": list(order),
                "source_observation": len(invocations["python-source"]) - 1,
                "native_observation": len(invocations["rextio-native"]) - 1,
            }
        )

    ratios = paired_speedups(paired_source, paired_native)
    interval = paired_bootstrap_interval(
        paired_source,
        paired_native,
        resamples=settings["bootstrap_resamples"],
    )
    lanes = {lane: _lane_summary(values) for lane, values in invocations.items()}
    for lane in lanes:
        lanes[lane]["first_call_ns"] = [first_calls[lane]["elapsed_ns"]]
    reference_output_ref = output_table.intern(
        first_calls["python-source"]["stdout"].strip()
    )
    return {
        "id": case.benchmark_id,
        "project": case.project,
        "description": case.raw["description"],
        "context": case.raw.get("context"),
        "negative_control": False,
        "kind": case.kind,
        "output_table": output_table.values(),
        "timing_contract": {
            "unit": "fresh-process",
            "process_model": "sequential-fresh-process-calibrated-batch",
            "minimum_sample_ns": settings["minimum_sample_ns"],
            "includes_process_startup": True,
        },
        "gate": gate,
        "correctness": {
            "status": "passed",
            "tolerance": case.tolerance,
            "evidence": {
                "reference_output_ref": reference_output_ref,
                "fallback_output_ref": None,
            },
        },
        "lanes": lanes,
        "paired": {
            "orders": [list(order) for order in orders],
            "source_medians_ns": paired_source,
            "native_medians_ns": paired_native,
            "speedups": ratios,
            "median_speedup": statistics.median(ratios),
            "bootstrap_95": list(interval),
            "observations": pair_evidence,
        },
        "eligible": True,
        "blockers": [],
        "packages": package_versions(),
        "package_provenance": package_vcs_provenance(),
        "python": sys.version,
        "environment": _portable_environment(
            {
                **{key: environment.get(key) for key in THREAD_ENVIRONMENT},
                "effective_threads": {},
                "module_provenance": _module_provenance(case.required_modules),
                "active_module_provenance": {},
                "profile_prefix": sys.prefix,
            },
            repository_root,
        ),
    }
