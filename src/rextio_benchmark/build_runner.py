from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .integration_targets import (
    cases_require_integration_targets,
    require_integration_targets_ready,
)
from .models import load_cases, profile_python
from .portability import portable_value, require_portable
from .processes import sanitized_environment
from .verification import gate_build


def _profile_environment(repository_root: Path, profile: str) -> dict[str, str]:
    environment = sanitized_environment()
    profile_root = repository_root / "profiles" / profile
    python = profile_python(repository_root, profile)
    environment["VIRTUAL_ENV"] = str(profile_root / ".venv")
    environment["PATH"] = f"{profile_root / '.venv' / 'bin'}{os.pathsep}{environment['PATH']}"
    environment["PYO3_PYTHON"] = str(python)
    if profile == "torch-cpu":
        environment["LIBTORCH_USE_PYTORCH"] = "1"
        environment.pop("LIBTORCH_BYPASS_VERSION_CHECK", None)
    if profile == "tensorflow-cpu":
        environment["REXTIO_TF_E2E_PYTHON"] = str(python)
    return environment


def _run(command: list[str], environment: dict[str, str], cwd: Path) -> dict[str, Any]:
    started = time.perf_counter_ns()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=3600,
    )
    record = {
        "command": portable_value(command, cwd),
        "elapsed_ns": time.perf_counter_ns() - started,
        "returncode": completed.returncode,
        "stdout_tail": portable_value(completed.stdout[-4000:], cwd),
        "stderr_tail": portable_value(completed.stderr[-4000:], cwd),
    }
    require_portable(record, cwd)
    return record


def build_cpu(repository_root: Path) -> tuple[dict[str, Any], bool]:
    loaded_cases = load_cases(repository_root)
    if cases_require_integration_targets(
        frozenset(case.benchmark_id for case in loaded_cases)
    ):
        require_integration_targets_ready(repository_root)
    projects: dict[str, list[Any]] = {}
    for case in loaded_cases:
        projects.setdefault(case.project, []).append(case)
    records = []
    success = True
    for project_cases in projects.values():
        case = project_cases[0]
        profile_root = repository_root / "profiles" / case.profile
        executable = profile_root / ".venv" / "bin" / "rextio"
        if not executable.is_file():
            records.append(
                {
                    "project": case.project,
                    "profile": case.profile,
                    "status": "blocked",
                    "blocker": (
                        f"missing {executable.relative_to(repository_root)}; "
                        "run scripts/bootstrap.sh cpu"
                    ),
                }
            )
            success = False
            continue
        environment = _profile_environment(repository_root, case.profile)
        check = _run(
            [str(executable), "check", str(case.project_root)],
            environment,
            repository_root,
        )
        build = _run(
            [str(executable), "build", str(case.project_root), "--fallback=cpython"],
            environment,
            repository_root,
        )
        gate_error = None
        if check["returncode"] == 0 and build["returncode"] == 0:
            try:
                for project_case in project_cases:
                    gate_build(project_case, repository_root)
            except Exception as error:
                gate_error = str(
                    portable_value(f"{type(error).__name__}: {error}", repository_root)
                )
        status = (
            "built"
            if check["returncode"] == 0
            and build["returncode"] == 0
            and gate_error is None
            else "failed"
        )
        success = success and status == "built"
        records.append(
            {
                "project": case.project,
                "profile": case.profile,
                "status": status,
                "gate_error": gate_error,
                "check": check,
                "build": build,
            }
        )
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "platform": "cpu",
        "projects": records,
    }
    output = repository_root / "results" / "local" / "build-cpu.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report, success
