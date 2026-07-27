from __future__ import annotations

import argparse
import gc
import importlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import sys
import sysconfig
import time
from importlib.machinery import PathFinder
from pathlib import Path
from types import ModuleType
from typing import Any

from .processes import THREAD_ENVIRONMENT

PACKAGES = (
    "rextio",
    "rextio-numpy",
    "rextio-networkx",
    "rextio-pandas",
    "rextio-torch",
    "rextio-tensorflow",
    "numpy",
    "networkx",
    "pandas",
    "torch",
    "tensorflow",
)


def _load_adapter(path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location("_rextio_benchmark_case", path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load benchmark adapter {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def package_versions() -> dict[str, str]:
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return versions


def package_vcs_provenance() -> dict[str, dict[str, str]]:
    """Capture PEP 610 Git direct_url provenance for candidate-relevant packages."""
    from .provenance import package_vcs_provenance as _capture

    return _capture()


def _time_batch(function: Any, arguments: tuple[object, ...], batch_size: int) -> tuple[int, Any]:
    result: Any = None
    started = time.perf_counter_ns()
    for _ in range(batch_size):
        result = function(*arguments)
    return time.perf_counter_ns() - started, result


def _require_deterministic(
    adapter: ModuleType,
    benchmark_id: str,
    reference: object,
    value: object,
    stage: str,
) -> object:
    normalized = adapter.normalize(benchmark_id, value)
    if normalized != reference:
        raise RuntimeError(f"non-deterministic output at {stage}")
    return normalized


def _configure_framework_threads() -> dict[str, dict[str, int]]:
    effective: dict[str, dict[str, int]] = {}
    torch = sys.modules.get("torch")
    if torch is not None:
        torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "1")))
        torch.set_num_interop_threads(1)
        effective["torch"] = {
            "intraop_threads": int(torch.get_num_threads()),
            "interop_threads": int(torch.get_num_interop_threads()),
        }
    tensorflow = sys.modules.get("tensorflow")
    if tensorflow is not None:
        threading = tensorflow.config.threading
        threading.set_intra_op_parallelism_threads(
            int(os.environ.get("TF_NUM_INTRAOP_THREADS", "1"))
        )
        threading.set_inter_op_parallelism_threads(
            int(os.environ.get("TF_NUM_INTEROP_THREADS", "1"))
        )
        effective["tensorflow"] = {
            "intraop_threads": int(threading.get_intra_op_parallelism_threads()),
            "interop_threads": int(threading.get_inter_op_parallelism_threads()),
        }
    return effective


def _profile_site_roots() -> tuple[Path, ...]:
    prefix = Path(sys.prefix).resolve()
    roots = {
        Path(path).resolve()
        for key in ("purelib", "platlib")
        if (path := sysconfig.get_path(key)) is not None
    }
    invalid = [root for root in roots if not root.is_relative_to(prefix)]
    if invalid:
        raise RuntimeError(f"profile site-packages escaped interpreter prefix: {invalid}")
    return tuple(sorted(roots))


def _module_provenance(
    required_modules: tuple[str, ...] | list[str],
    *,
    site_roots: tuple[Path, ...] | None = None,
) -> dict[str, dict[str, str]]:
    roots = _profile_site_roots() if site_roots is None else tuple(
        root.resolve() for root in site_roots
    )
    provenance: dict[str, dict[str, str]] = {}
    for name in required_modules:
        specification = PathFinder.find_spec(name, [str(root) for root in roots])
        module_path_text = specification.origin if specification is not None else None
        if not module_path_text:
            raise RuntimeError(f"required module {name!r} is absent from profile site-packages")
        module_path = Path(module_path_text).resolve()
        matching_root = next((root for root in roots if module_path.is_relative_to(root)), None)
        if matching_root is None:
            raise RuntimeError(
                f"required module {name!r} imported outside profile site-packages: {module_path}"
            )
        provenance[name] = {
            "file": str(module_path),
            "site_packages": str(matching_root),
        }
    return provenance


def _active_module_provenance(
    required_modules: tuple[str, ...] | list[str],
    *,
    lane: str,
    import_root: Path,
    installed: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    active: dict[str, dict[str, str]] = {}
    resolved_import_root = import_root.resolve()
    for name in required_modules:
        module = sys.modules.get(name)
        if module is None:
            if name == "rextio" and lane in {"rextio-fallback", "rextio-native"}:
                raise RuntimeError(
                    "generated rextio runtime was not imported by workload"
                )
            continue
        module_path_text = getattr(module, "__file__", None)
        if not module_path_text:
            raise RuntimeError(f"required module {name!r} was not imported by workload")
        module_path = Path(module_path_text).resolve()
        installed_record = installed[name]
        installed_root = Path(installed_record["site_packages"]).resolve()
        if name != "rextio" or lane == "python-source":
            if not module_path.is_relative_to(installed_root):
                raise RuntimeError(
                    f"required module {name!r} imported outside profile site-packages: "
                    f"{module_path}"
                )
            active[name] = {
                "file": str(module_path),
                "root": str(installed_root),
                "kind": "installed",
            }
            continue
        generated_package_root = resolved_import_root / "rextio"
        if not module_path.is_relative_to(generated_package_root):
            raise RuntimeError(
                f"generated rextio runtime imported outside exact generated root: {module_path}"
            )
        active[name] = {
            "file": str(module_path),
            "root": str(resolved_import_root),
            "kind": "generated-runtime",
        }
    return active


def execute(arguments: argparse.Namespace) -> dict[str, Any]:
    import_root = Path(arguments.import_root).resolve()
    required_modules = tuple(arguments.required_module)
    module_provenance = _module_provenance(required_modules)
    sys.path.insert(0, str(import_root))
    adapter = _load_adapter(Path(arguments.adapter).resolve())
    effective_threads = _configure_framework_threads()
    inputs = adapter.make_arguments(arguments.benchmark_id)
    if not isinstance(inputs, tuple):
        raise TypeError("make_arguments must return a tuple")

    import_started = time.perf_counter_ns()
    module = importlib.import_module(arguments.module)
    import_ns = time.perf_counter_ns() - import_started
    active_module_provenance = _active_module_provenance(
        required_modules,
        lane=arguments.lane,
        import_root=import_root,
        installed=module_provenance,
    )
    function = getattr(module, arguments.function)

    first_started = time.perf_counter_ns()
    first_output = function(*inputs)
    first_call_ns = time.perf_counter_ns() - first_started
    normalized = adapter.normalize(arguments.benchmark_id, first_output)

    for index in range(arguments.warmups):
        warmup_output = function(*inputs)
        _require_deterministic(
            adapter,
            arguments.benchmark_id,
            normalized,
            warmup_output,
            f"warmup {index + 1}",
        )

    batch_size = 1
    while True:
        elapsed, calibration_output = _time_batch(function, inputs, batch_size)
        _require_deterministic(
            adapter,
            arguments.benchmark_id,
            normalized,
            calibration_output,
            f"calibration batch {batch_size}",
        )
        if elapsed >= arguments.minimum_sample_ns or batch_size >= arguments.maximum_batch:
            break
        batch_size *= 2

    samples_ns: list[float] = []
    batch_sizes: list[int] = []
    batch_elapsed_ns: list[int] = []
    gc_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(arguments.samples):
            while True:
                elapsed, last_output = _time_batch(function, inputs, batch_size)
                if elapsed >= arguments.minimum_sample_ns:
                    break
                if batch_size >= arguments.maximum_batch:
                    raise RuntimeError("maximum batch cannot satisfy minimum sample duration")
                batch_size = min(batch_size * 2, arguments.maximum_batch)
            samples_ns.append(elapsed / batch_size)
            batch_sizes.append(batch_size)
            batch_elapsed_ns.append(elapsed)
            _require_deterministic(
                adapter,
                arguments.benchmark_id,
                normalized,
                last_output,
                f"retained sample {len(samples_ns)}",
            )
    finally:
        if gc_enabled:
            gc.enable()

    module_file = str(Path(module.__file__ or "").resolve())
    return {
        "lane": arguments.lane,
        "pid": os.getpid(),
        "module_file": module_file,
        "import_root": str(import_root),
        "import_ns": import_ns,
        "first_call_ns": first_call_ns,
        "batch_size": batch_size,
        "batch_sizes": batch_sizes,
        "batch_elapsed_ns": batch_elapsed_ns,
        "samples_ns": samples_ns,
        "output": normalized,
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "packages": package_versions(),
        "package_provenance": package_vcs_provenance(),
        "environment": {
            **{
                name: os.environ.get(name)
                for name in (
                    "REXTIO_NATIVE_MODE",
                    "REXTIO_DISABLE_BOUNDARY_FALLBACK",
                    *THREAD_ENVIRONMENT,
                )
            },
            "effective_threads": effective_threads,
            "module_provenance": module_provenance,
            "active_module_provenance": active_module_provenance,
            "profile_prefix": sys.prefix,
        },
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--lane", required=True)
    result.add_argument("--benchmark-id", required=True)
    result.add_argument("--adapter", required=True)
    result.add_argument("--import-root", required=True)
    result.add_argument("--module", required=True)
    result.add_argument("--function", required=True)
    result.add_argument("--warmups", type=int, required=True)
    result.add_argument("--samples", type=int, required=True)
    result.add_argument("--minimum-sample-ns", type=int, required=True)
    result.add_argument("--maximum-batch", type=int, default=1_048_576)
    result.add_argument("--required-module", action="append", default=[])
    return result


def main() -> int:
    try:
        result = execute(parser().parse_args())
    except Exception as error:
        print(json.dumps({"error": f"{type(error).__name__}: {error}"}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
