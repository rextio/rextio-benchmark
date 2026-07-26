from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from rextio_benchmark.build_runner import _profile_environment
from rextio_benchmark.case_runner import _portable_environment
from rextio_benchmark.models import load_cases
from rextio_benchmark.processes import THREAD_ENVIRONMENT, worker_environment
from rextio_benchmark.verification import GateError
from rextio_benchmark.verifier import _verify_environment
from rextio_benchmark.worker import execute

ROOT = Path(__file__).resolve().parents[1]


def _load_case_adapter(path: Path, name: str) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _worker_arguments(tmp_path: Path, *, module: str, samples: int = 1) -> argparse.Namespace:
    return argparse.Namespace(
        import_root=str(tmp_path),
        adapter=str(tmp_path / "adapter.py"),
        benchmark_id="fixture",
        module=module,
        function="run",
        lane="python-source",
        warmups=0,
        samples=samples,
        minimum_sample_ns=0,
        maximum_batch=1,
        required_module=[],
    )


def test_python_environments_discard_inherited_import_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PYTHONPATH", "/workspace/rextio:/tmp/unreleased-plugin")
    monkeypatch.setenv("PYTHONHOME", "/tmp/foreign-python")

    worker = worker_environment(tmp_path, "python-source")
    build = _profile_environment(tmp_path, "base")

    assert worker["PYTHONPATH"] == str(tmp_path / "src")
    assert "PYTHONHOME" not in worker
    assert "PYTHONPATH" not in build
    assert "PYTHONHOME" not in build
    assert {name: worker[name] for name in THREAD_ENVIRONMENT} == THREAD_ENVIRONMENT


def test_shell_entrypoints_do_not_append_inherited_pythonpath() -> None:
    for name in ("bootstrap.sh", "build.sh", "benchmark.sh", "verify.sh"):
        source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "${PYTHONPATH" not in source
        assert "unset PYTHONHOME" in source
    for name in ("build.sh", "benchmark.sh", "verify.sh"):
        source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert 'export PYTHONPATH="$ROOT/src"' in source


def test_readme_documents_environment_and_full_output_gates() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "sanitized environment" in readme
    assert "profile's site-packages" in readme
    assert "exact case build root" in readme
    assert "full-output" in readme
    assert "effective framework thread counts" in readme


def test_cases_require_core_and_enabled_plugin_modules() -> None:
    cases = {case.benchmark_id: case for case in load_cases(ROOT)}
    assert cases["core-hybrid"].required_modules == ("rextio",)
    assert cases["numpy-mixed-fusion"].required_modules == ("rextio", "rextio_numpy")
    assert cases["networkx-dijkstra"].required_modules == ("rextio", "rextio_networkx")
    assert cases["pandas-series-map"].required_modules == ("rextio", "rextio_pandas")
    assert cases["torch-cpu-deep-mlp"].required_modules == ("rextio", "rextio_torch")
    assert cases["tensorflow-cpu-eager-chain"].required_modules == (
        "rextio",
        "rextio_tensorflow",
    )


def test_installed_module_provenance_does_not_import_or_pin_module(
    tmp_path: Path,
) -> None:
    worker = importlib.import_module("rextio_benchmark.worker")
    site_packages = tmp_path / "venv" / "lib" / "python3.11" / "site-packages"
    installed = site_packages / "rextio" / "__init__.py"
    installed.parent.mkdir(parents=True)
    installed.write_text("", encoding="utf-8")
    sys.modules.pop("rextio", None)

    assert worker._module_provenance(("rextio",), site_roots=(site_packages,))[
        "rextio"
    ]["file"] == str(installed.resolve())
    assert "rextio" not in sys.modules


def test_active_module_provenance_allows_only_lane_specific_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    worker = importlib.import_module("rextio_benchmark.worker")
    site_packages = tmp_path / "venv" / "lib" / "python3.11" / "site-packages"
    installed_file = site_packages / "rextio" / "__init__.py"
    installed_file.parent.mkdir(parents=True)
    installed_file.write_text("", encoding="utf-8")
    installed = {
        "rextio": {
            "file": str(installed_file.resolve()),
            "site_packages": str(site_packages.resolve()),
        }
    }
    generated_root = tmp_path / "case" / ".rextio" / "build" / "python"
    generated_file = generated_root / "rextio" / "__init__.py"
    generated_file.parent.mkdir(parents=True)
    generated_file.write_text("", encoding="utf-8")
    module = ModuleType("rextio")
    module.__file__ = str(installed_file)
    monkeypatch.setitem(sys.modules, "rextio", module)

    source = worker._active_module_provenance(
        ("rextio",),
        lane="python-source",
        import_root=tmp_path / "case" / "src",
        installed=installed,
    )
    assert source["rextio"]["kind"] == "installed"
    assert source["rextio"]["root"] == str(site_packages.resolve())

    module.__file__ = str(generated_file)
    generated = worker._active_module_provenance(
        ("rextio",),
        lane="rextio-native",
        import_root=generated_root,
        installed=installed,
    )
    assert generated["rextio"]["kind"] == "generated-runtime"
    assert generated["rextio"]["root"] == str(generated_root.resolve())

    module.__file__ = str(tmp_path / "workspace" / "rextio" / "__init__.py")
    with pytest.raises(RuntimeError, match="outside profile site-packages"):
        worker._active_module_provenance(
            ("rextio",),
            lane="python-source",
            import_root=tmp_path / "case" / "src",
            installed=installed,
        )
    with pytest.raises(RuntimeError, match="outside exact generated root"):
        worker._active_module_provenance(
            ("rextio",),
            lane="rextio-fallback",
            import_root=generated_root,
            installed=installed,
        )


def test_declared_modules_may_be_inactive_but_generated_core_is_required(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    worker = importlib.import_module("rextio_benchmark.worker")
    site_packages = tmp_path / "venv" / "lib" / "python3.11" / "site-packages"
    installed: dict[str, dict[str, str]] = {}
    for name in ("rextio", "rextio_numpy"):
        module_file = site_packages / name / "__init__.py"
        module_file.parent.mkdir(parents=True, exist_ok=True)
        module_file.write_text("", encoding="utf-8")
        installed[name] = {
            "file": str(module_file.resolve()),
            "site_packages": str(site_packages.resolve()),
        }
        monkeypatch.delitem(sys.modules, name, raising=False)
    generated_root = tmp_path / "case" / ".rextio" / "build" / "python"

    assert worker._active_module_provenance(
        ("rextio", "rextio_numpy"),
        lane="python-source",
        import_root=tmp_path / "case" / "src",
        installed=installed,
    ) == {}

    generated_file = generated_root / "rextio" / "__init__.py"
    generated_file.parent.mkdir(parents=True)
    generated_file.write_text("", encoding="utf-8")
    generated_module = ModuleType("rextio")
    generated_module.__file__ = str(generated_file)
    monkeypatch.setitem(sys.modules, "rextio", generated_module)
    assert set(
        worker._active_module_provenance(
            ("rextio", "rextio_numpy"),
            lane="rextio-native",
            import_root=generated_root,
            installed=installed,
        )
    ) == {"rextio"}

    monkeypatch.delitem(sys.modules, "rextio")
    with pytest.raises(RuntimeError, match="generated rextio runtime was not imported"):
        worker._active_module_provenance(
            ("rextio", "rextio_numpy"),
            lane="rextio-native",
            import_root=generated_root,
            installed=installed,
        )


def test_generated_worker_uses_bundled_runtime_without_pinning_installed_core(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    worker = importlib.import_module("rextio_benchmark.worker")
    site_packages = tmp_path / "profile" / "lib" / "python3.11" / "site-packages"
    installed_file = site_packages / "rextio" / "__init__.py"
    installed_file.parent.mkdir(parents=True)
    installed_file.write_text("ORIGIN = 'installed'\n", encoding="utf-8")
    import_root = tmp_path / "case" / ".rextio" / "build" / "python"
    generated_package = import_root / "rextio"
    generated_package.mkdir(parents=True)
    (generated_package / "__init__.py").write_text(
        "ORIGIN = 'generated'\n",
        encoding="utf-8",
    )
    (import_root / "generated_workload.py").write_text(
        "import rextio\n\n"
        "def run():\n"
        "    return rextio.ORIGIN\n",
        encoding="utf-8",
    )
    adapter = tmp_path / "adapter.py"
    adapter.write_text(
        "def make_arguments(_benchmark_id):\n"
        "    return ()\n\n"
        "def normalize(_benchmark_id, value):\n"
        "    return value\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(worker, "_profile_site_roots", lambda: (site_packages,))
    monkeypatch.syspath_prepend(str(site_packages))
    for name in tuple(sys.modules):
        if name == "rextio" or name.startswith("rextio."):
            monkeypatch.delitem(sys.modules, name)
    arguments = _worker_arguments(tmp_path, module="generated_workload")
    arguments.import_root = str(import_root)
    arguments.adapter = str(adapter)
    arguments.lane = "rextio-native"
    arguments.required_module = ["rextio"]

    result = execute(arguments)

    assert result["output"] == "generated"
    assert result["environment"]["module_provenance"]["rextio"]["file"] == str(
        installed_file.resolve()
    )
    assert result["environment"]["active_module_provenance"]["rextio"] == {
        "file": str((generated_package / "__init__.py").resolve()),
        "root": str(import_root.resolve()),
        "kind": "generated-runtime",
    }
    assert sys.modules["rextio"].ORIGIN == "generated"


def test_portable_and_verified_active_provenance_is_lane_specific(
    tmp_path: Path,
) -> None:
    repository_root = tmp_path
    profile = repository_root / "profiles" / "base" / ".venv"
    site_packages = profile / "lib" / "python3.11" / "site-packages"
    installed_file = site_packages / "rextio" / "__init__.py"
    installed_plugin_file = site_packages / "rextio_numpy" / "__init__.py"
    generated_root = (
        repository_root / "cases" / "fixture" / ".rextio" / "build" / "python"
    )
    generated_file = generated_root / "rextio" / "__init__.py"
    for path in (installed_file, installed_plugin_file, generated_file):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    fixture_root = repository_root / "cases" / "fixture"
    (fixture_root / "rextio.toml").write_text(
        '[plugins]\nenabled = ["rextio-numpy"]\n',
        encoding="utf-8",
    )
    raw = {
        **THREAD_ENVIRONMENT,
        "effective_threads": {},
        "module_provenance": {
            "rextio": {
                "file": str(installed_file),
                "site_packages": str(site_packages),
            },
            "rextio_numpy": {
                "file": str(installed_plugin_file),
                "site_packages": str(site_packages),
            },
        },
        "active_module_provenance": {
            "python-source": {},
            "rextio-fallback": {
                "rextio": {
                    "file": str(generated_file),
                    "root": str(generated_root),
                    "kind": "generated-runtime",
                }
            },
            "rextio-native": {
                "rextio": {
                    "file": str(generated_file),
                    "root": str(generated_root),
                    "kind": "generated-runtime",
                }
            },
        },
        "profile_prefix": str(profile),
    }
    portable = _portable_environment(raw, repository_root)
    case = next(
        case
        for case in load_cases(ROOT)
        if case.benchmark_id == "core-hybrid"
    )
    fixture_case = type(case)(
        **{
            **case.__dict__,
            "project": "fixture",
            "project_root": fixture_root,
        }
    )

    _verify_environment(fixture_case, portable, repository_root)

    portable["active_module_provenance"]["rextio-native"]["rextio"]["root"] = (
        "cases/other/.rextio/build/python"
    )
    with pytest.raises(GateError, match="generated runtime root differs"):
        _verify_environment(fixture_case, portable, repository_root)


def test_schema_requires_well_formed_active_module_provenance() -> None:
    schema = json.loads(
        (ROOT / "schema" / "benchmark-report-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    environment_schema = schema["$defs"]["case"]["properties"]["environment"]
    required = environment_schema["anyOf"][1]["required"]
    assert "active_module_provenance" in required
    validator = Draft202012Validator(schema["$defs"]["activeModuleProvenance"])
    validator.validate(
        {
            "rextio": {
                "file": "cases/core/.rextio/build/python/rextio/__init__.py",
                "root": "cases/core/.rextio/build/python",
                "kind": "generated-runtime",
            }
        }
    )
    with pytest.raises(ValidationError):
        validator.validate(
            {
                "rextio": {
                    "file": "rextio/__init__.py",
                    "root": "profiles/base/.venv",
                    "kind": "workspace",
                }
            }
        )


def test_worker_rejects_changing_output(tmp_path: Path) -> None:
    (tmp_path / "adapter.py").write_text(
        "def make_arguments(_benchmark_id):\n"
        "    return ()\n\n"
        "def normalize(_benchmark_id, value):\n"
        "    return value\n",
        encoding="utf-8",
    )
    (tmp_path / "changing_workload.py").write_text(
        "_value = 0\n\n"
        "def run():\n"
        "    global _value\n"
        "    _value += 1\n"
        "    return _value\n",
        encoding="utf-8",
    )
    try:
        with pytest.raises(RuntimeError, match="non-deterministic output"):
            execute(_worker_arguments(tmp_path, module="changing_workload"))
    finally:
        sys.modules.pop("changing_workload", None)


def test_canonical_outputs_cover_all_values() -> None:
    canonical = importlib.import_module("rextio_benchmark.canonical")
    floats = canonical.sequence(
        kind="tensor",
        shape=(2, 2),
        dtype="float32",
        values=[1.0, 2.0, 3.0, 4.0],
    )
    assert floats["values"] == [1.0, 2.0, 3.0, 4.0]

    first = canonical.exact_sequence(
        kind="series",
        shape=(3,),
        dtype="bool",
        values=[True, False, True],
    )
    changed = canonical.exact_sequence(
        kind="series",
        shape=(3,),
        dtype="bool",
        values=[True, True, False],
    )
    assert first["count"] == 3
    assert first["sha256"] != changed["sha256"]
    assert canonical.node_float_mapping({2: 9.0, 0: 0.0, 1: 1.5})["items"] == [
        [0, 0.0],
        [1, 1.5],
        [2, 9.0],
    ]


def test_base_case_adapters_use_complete_canonical_outputs() -> None:
    import numpy as np
    import pandas as pd

    numpy_adapter = _load_case_adapter(
        ROOT / "cases" / "numpy" / "benchmark_case.py", "_case_numpy_adapter"
    )
    assert numpy_adapter.normalize(
        "numpy-mixed-fusion", np.array([1.0, 9.0, 2.0])
    )["values"] == [1.0, 9.0, 2.0]

    pandas_adapter = _load_case_adapter(
        ROOT / "cases" / "pandas" / "benchmark_case.py", "_case_pandas_adapter"
    )
    original = pandas_adapter.normalize(
        "pandas-series-map", pd.Series([True, False, True], dtype="bool")
    )
    changed = pandas_adapter.normalize(
        "pandas-series-map", pd.Series([True, True, False], dtype="bool")
    )
    assert original["sha256"] != changed["sha256"]

    networkx_adapter = _load_case_adapter(
        ROOT / "cases" / "networkx" / "benchmark_case.py", "_case_networkx_adapter"
    )
    assert networkx_adapter.normalize("networkx-dijkstra", {1: 1.5, 0: 0.0})[
        "items"
    ] == [[0, 0.0], [1, 1.5]]


def test_framework_case_adapters_use_complete_canonical_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeTorchTensor:
        shape = (3,)
        dtype = "float32"

        def detach(self) -> FakeTorchTensor:
            return self

        def cpu(self) -> FakeTorchTensor:
            return self

        def reshape(self, _size: int) -> FakeTorchTensor:
            return self

        def tolist(self) -> list[float]:
            return [1.0, 9.0, 2.0]

    fake_torch = ModuleType("torch")
    fake_torch.Tensor = FakeTorchTensor
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    torch_adapter = _load_case_adapter(
        ROOT / "cases" / "torch-cpu" / "benchmark_case.py", "_case_torch_adapter"
    )
    assert torch_adapter.normalize("torch-cpu-deep-mlp", FakeTorchTensor())[
        "values"
    ] == [1.0, 9.0, 2.0]

    class FakeArray:
        shape = (3,)
        dtype = "int64"

        def reshape(self, _size: int) -> FakeArray:
            return self

        def tolist(self) -> list[int]:
            return [1, 9, 2]

    class FakeTensorflowTensor:
        def numpy(self) -> FakeArray:
            return FakeArray()

    fake_tensorflow = ModuleType("tensorflow")
    fake_tensorflow.Tensor = FakeTensorflowTensor
    monkeypatch.setitem(sys.modules, "tensorflow", fake_tensorflow)
    tensorflow_adapter = _load_case_adapter(
        ROOT / "cases" / "tensorflow-cpu" / "benchmark_case.py",
        "_case_tensorflow_adapter",
    )
    result = tensorflow_adapter.normalize(
        "tensorflow-cpu-eager-chain", FakeTensorflowTensor()
    )
    assert result["count"] == 3


def test_framework_threads_are_configured_and_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = importlib.import_module("rextio_benchmark.worker")
    torch_state = {"intra": 0, "interop": 0}
    fake_torch = SimpleNamespace(
        set_num_threads=lambda value: torch_state.__setitem__("intra", value),
        set_num_interop_threads=lambda value: torch_state.__setitem__("interop", value),
        get_num_threads=lambda: torch_state["intra"],
        get_num_interop_threads=lambda: torch_state["interop"],
    )
    tensorflow_state = {"intra": 0, "interop": 0}
    tensorflow_threading = SimpleNamespace(
        set_intra_op_parallelism_threads=lambda value: tensorflow_state.__setitem__(
            "intra", value
        ),
        set_inter_op_parallelism_threads=lambda value: tensorflow_state.__setitem__(
            "interop", value
        ),
        get_intra_op_parallelism_threads=lambda: tensorflow_state["intra"],
        get_inter_op_parallelism_threads=lambda: tensorflow_state["interop"],
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(
        sys.modules,
        "tensorflow",
        SimpleNamespace(config=SimpleNamespace(threading=tensorflow_threading)),
    )

    assert worker._configure_framework_threads() == {
        "torch": {"intraop_threads": 1, "interop_threads": 1},
        "tensorflow": {"intraop_threads": 1, "interop_threads": 1},
    }


def test_worker_records_every_thread_environment_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "adapter.py").write_text(
        "def make_arguments(_benchmark_id):\n"
        "    return ()\n\n"
        "def normalize(_benchmark_id, value):\n"
        "    return value\n",
        encoding="utf-8",
    )
    (tmp_path / "stable_workload.py").write_text(
        "def run():\n"
        "    return 7\n",
        encoding="utf-8",
    )
    for name, value in THREAD_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    try:
        result = execute(
            _worker_arguments(tmp_path, module="stable_workload", samples=2)
        )
    finally:
        sys.modules.pop("stable_workload", None)

    assert {
        name: result["environment"][name] for name in THREAD_ENVIRONMENT
    } == THREAD_ENVIRONMENT
    assert result["environment"]["module_provenance"] == {}
    assert result["environment"]["active_module_provenance"] == {}
