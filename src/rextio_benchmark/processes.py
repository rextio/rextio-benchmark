from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from .models import BenchmarkCase

THREAD_ENVIRONMENT = {
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "TF_NUM_INTRAOP_THREADS": "1",
    "TF_NUM_INTEROP_THREADS": "1",
}


def sanitized_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    return environment


def worker_environment(repository_root: Path, lane: str) -> dict[str, str]:
    environment = sanitized_environment()
    environment.update(THREAD_ENVIRONMENT)
    environment["PYTHONPATH"] = str(repository_root / "src")
    environment.pop("REXTIO_NATIVE_MODE", None)
    environment.pop("REXTIO_DISABLE_BOUNDARY_FALLBACK", None)
    if lane == "rextio-fallback":
        environment["REXTIO_NATIVE_MODE"] = "fallback"
    elif lane == "rextio-native":
        environment["REXTIO_NATIVE_MODE"] = "native"
        environment["REXTIO_DISABLE_BOUNDARY_FALLBACK"] = "1"
    return environment


def invoke_worker(
    repository_root: Path,
    python: Path,
    case: BenchmarkCase,
    lane: str,
    *,
    warmups: int,
    samples: int,
    minimum_sample_ns: int,
) -> dict[str, Any]:
    import_root = (
        case.source_root if lane == "python-source" else case.generated_python_root
    )
    command = [
        str(python),
        "-m",
        "rextio_benchmark.worker",
        "--lane",
        lane,
        "--benchmark-id",
        case.benchmark_id,
        "--adapter",
        str(case.adapter_path),
        "--import-root",
        str(import_root),
        "--module",
        case.module,
        "--function",
        case.function,
        "--warmups",
        str(warmups),
        "--samples",
        str(samples),
        "--minimum-sample-ns",
        str(minimum_sample_ns),
    ]
    for module_name in case.required_modules:
        command.extend(("--required-module", module_name))
    completed = subprocess.run(
        command,
        cwd=repository_root,
        env=worker_environment(repository_root, lane),
        capture_output=True,
        text=True,
        timeout=1800,
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(
            f"{case.benchmark_id}/{lane} returned no JSON; stderr={completed.stderr[-2000:]}"
        )
    result = json.loads(lines[-1])
    if completed.returncode or "error" in result:
        raise RuntimeError(
            f"{case.benchmark_id}/{lane} failed: {result.get('error')}; "
            f"stderr={completed.stderr[-2000:]}"
        )
    result["stderr_tail"] = completed.stderr[-2000:]
    return result


def invoke_command(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
) -> dict[str, Any]:
    started = time.perf_counter_ns()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    elapsed = time.perf_counter_ns() - started
    if completed.returncode:
        raise RuntimeError(
            f"command {command!r} exited {completed.returncode}: {completed.stderr[-2000:]}"
        )
    return {
        "elapsed_ns": float(elapsed),
        "stdout": completed.stdout,
        "stderr_tail": completed.stderr[-2000:],
        "command": command,
    }


def invoke_command_batch(
    command: list[str],
    *,
    batch_size: int,
    cwd: Path,
    environment: dict[str, str],
) -> dict[str, Any]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    elapsed_ns = 0.0
    output: str | None = None
    for _ in range(batch_size):
        result = invoke_command(command, cwd=cwd, environment=environment)
        elapsed_ns += result["elapsed_ns"]
        if output is None:
            output = result["stdout"]
        elif output != result["stdout"]:
            raise RuntimeError("executable produced non-deterministic output within a batch")
    return {
        "batch_elapsed_ns": elapsed_ns,
        "sample_ns": elapsed_ns / batch_size,
        "batch_size": batch_size,
        "stdout": output or "",
    }


def measure_command_samples(
    command: list[str],
    *,
    samples: int,
    minimum_sample_ns: int,
    initial_batch_size: int,
    cwd: Path,
    environment: dict[str, str],
    maximum_batch: int = 1_048_576,
) -> dict[str, Any]:
    batch_size = initial_batch_size
    retained: list[float] = []
    batch_sizes: list[int] = []
    batch_elapsed_ns: list[float] = []
    output: str | None = None
    for _ in range(samples):
        while True:
            result = invoke_command_batch(
                command,
                batch_size=batch_size,
                cwd=cwd,
                environment=environment,
            )
            if result["batch_elapsed_ns"] >= minimum_sample_ns:
                break
            if batch_size >= maximum_batch:
                raise RuntimeError("maximum executable batch cannot satisfy sample duration")
            batch_size = min(batch_size * 2, maximum_batch)
        if output is None:
            output = result["stdout"]
        elif output != result["stdout"]:
            raise RuntimeError("executable produced non-deterministic retained output")
        retained.append(result["sample_ns"])
        batch_sizes.append(result["batch_size"])
        batch_elapsed_ns.append(result["batch_elapsed_ns"])
    return {
        "samples_ns": retained,
        "batch_sizes": batch_sizes,
        "batch_elapsed_ns": batch_elapsed_ns,
        "next_batch_size": batch_size,
        "output": output or "",
    }
