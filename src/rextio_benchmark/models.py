from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BenchmarkCase:
    benchmark_id: str
    project: str
    profile: str
    project_root: Path
    adapter_path: Path
    kind: str
    module: str
    function: str
    qualname: str
    expected_route: str
    tolerance: dict[str, float]
    raw: dict[str, Any]

    @property
    def source_root(self) -> Path:
        return self.project_root / "src"

    @property
    def build_root(self) -> Path:
        return self.project_root / ".rextio" / "build"

    @property
    def generated_python_root(self) -> Path:
        return self.build_root / "python"

    @property
    def required_modules(self) -> tuple[str, ...]:
        config_path = self.project_root / "rextio.toml"
        config = (
            tomllib.loads(config_path.read_text(encoding="utf-8"))
            if config_path.is_file()
            else {}
        )
        enabled = config.get("plugins", {}).get("enabled", [])
        modules = ["rextio", *(str(name).replace("-", "_") for name in enabled)]
        return tuple(dict.fromkeys(modules))


def load_cases(repository_root: Path) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []
    for manifest_path in sorted((repository_root / "cases").glob("*/benchmark.json")):
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
        project_root = manifest_path.parent.resolve()
        for raw in document["benchmarks"]:
            cases.append(
                BenchmarkCase(
                    benchmark_id=raw["id"],
                    project=document["project"],
                    profile=document["profile"],
                    project_root=project_root,
                    adapter_path=project_root / "benchmark_case.py",
                    kind=raw["kind"],
                    module=raw["module"],
                    function=raw["function"],
                    qualname=raw["qualname"],
                    expected_route=raw["expected_route"],
                    tolerance=raw["tolerance"],
                    raw=raw,
                )
            )
    identifiers = [case.benchmark_id for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("benchmark ids must be unique")
    return cases


def profile_python(repository_root: Path, profile: str) -> Path:
    return repository_root / "profiles" / profile / ".venv" / "bin" / "python"


def paired_orders(pair_count: int) -> list[tuple[str, str]]:
    if pair_count < 1:
        raise ValueError("pair_count must be positive")
    return [
        ("python-source", "rextio-native")
        if index % 2 == 0
        else ("rextio-native", "python-source")
        for index in range(pair_count)
    ]
