from __future__ import annotations

import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .case_runner import MODE_SETTINGS, run_executable_case, run_module_case
from .models import load_cases, profile_python
from .portability import portable_value, require_portable


def _command_text(command: list[str], cwd: Path) -> str | None:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return completed.stdout.strip() if completed.returncode == 0 else None


def _repository_state(repository_root: Path) -> dict[str, Any]:
    commit = _command_text(["git", "rev-parse", "HEAD"], repository_root)
    status = _command_text(["git", "status", "--porcelain"], repository_root)
    return {
        "commit": commit,
        "dirty": bool(status) if status is not None else True,
    }


def _toolchain() -> dict[str, str | None]:
    cwd = Path.cwd()
    return {
        "rustc": _command_text(["rustc", "--version"], cwd),
        "cargo": _command_text(["cargo", "--version"], cwd),
    }


def _host_identity() -> dict[str, str]:
    model = None
    cpu_brand = None
    if platform.system() == "Darwin":
        cwd = Path.cwd()
        model = _command_text(["sysctl", "-n", "hw.model"], cwd)
        cpu_brand = _command_text(["sysctl", "-n", "machdep.cpu.brand_string"], cwd)
    return {
        "model": model or platform.machine() or "unknown",
        "cpu_brand": cpu_brand or platform.processor() or platform.machine() or "unknown",
    }


def _build_receipt(repository_root: Path) -> dict[str, Any] | None:
    path = repository_root / "results" / "local" / "build-cpu.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def run_suite(repository_root: Path, mode: str) -> tuple[dict[str, Any], Path]:
    if mode not in MODE_SETTINGS:
        raise ValueError(f"unknown mode {mode!r}")
    repository = _repository_state(repository_root)
    cases = []
    for case in load_cases(repository_root):
        python = profile_python(repository_root, case.profile)
        try:
            if not python.is_file():
                raise RuntimeError(f"missing profile interpreter {python}")
            if case.kind == "executable":
                result = run_executable_case(repository_root, python, case, mode)
            else:
                result = run_module_case(repository_root, python, case, mode)
        except Exception as error:
            result = {
                "id": case.benchmark_id,
                "project": case.project,
                "description": case.raw["description"],
                "context": case.raw.get("context"),
                "negative_control": bool(case.raw.get("negative_control", False)),
                "kind": case.kind,
                "output_table": {},
                "timing_contract": None,
                "gate": None,
                "correctness": {"status": "blocked"},
                "lanes": {},
                "paired": None,
                "eligible": False,
                "blockers": [
                    str(
                        portable_value(
                            f"{type(error).__name__}: {error}",
                            repository_root,
                        )
                    )
                ],
                "packages": {},
                "python": None,
                "environment": {},
            }
        cases.append(result)

    blockers = []
    if mode == "quick":
        blockers.append("quick-mode-is-never-publishable")
    if repository["commit"] is None:
        blockers.append("repository-commit-unavailable")
    if repository["dirty"]:
        blockers.append("repository-worktree-is-dirty")
    blockers.extend(
        f"{case['id']}: {blocker}"
        for case in cases
        for blocker in case.get("blockers", [])
    )
    publishable = mode == "publish" and not blockers and all(case["eligible"] for case in cases)
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "publishable": publishable,
        "eligibility": {
            "status": "eligible" if publishable else "blocked",
            "blockers": blockers,
        },
        "repository": repository,
        "system": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_controller": platform.python_version(),
            "toolchain": _toolchain(),
            "host": _host_identity(),
        },
        "configuration": MODE_SETTINGS[mode],
        "build": _build_receipt(repository_root),
        "cases": cases,
    }
    require_portable(report, repository_root)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = repository_root / "results" / "local" / f"benchmark-{mode}-{timestamp}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    return report, path


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Rextio benchmark report",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Generated: `{report['generated_at']}`",
        f"- Publishable: `{str(report['publishable']).lower()}`",
        f"- Host: `{report['system']['platform']}`",
        "",
        "| Case | Source median | Native median | Median speedup | Status |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for case in report["cases"]:
        if case["paired"] is None:
            lines.append(f"| {case['id']} | — | — | — | blocked |")
            continue
        source = case["lanes"]["python-source"]["steady_state"]["median_ns"] / 1_000_000
        native = case["lanes"]["rextio-native"]["steady_state"]["median_ns"] / 1_000_000
        speedup = case["paired"]["median_speedup"]
        lines.append(
            f"| {case['id']} | {source:.6f} ms | {native:.6f} ms | {speedup:.3f}× | passed |"
        )
    if report["eligibility"]["blockers"]:
        lines.extend(["", "## Publication blockers", ""])
        lines.extend(f"- {blocker}" for blocker in report["eligibility"]["blockers"])
    lines.extend(
        [
            "",
            "Build, import, and first-call timings are separate from steady-state samples.",
            "The Core executable row includes process startup in every retained observation.",
            "Slower and negative-control results are intentionally preserved.",
            "",
        ]
    )
    return "\n".join(lines)
