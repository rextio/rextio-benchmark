from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .cohort import cohort_id, validate_cohort
from .verification import GateError, logical_path, resolve_logical_path, sha256_file
from .verifier import verify_report

MAX_CANONICAL_OBJECT_BYTES = 256 * 1024 * 1024
MAX_CANONICAL_BUNDLE_BYTES = 512 * 1024 * 1024
_BUNDLE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _current_commit(repository_root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository_root,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def _default_name(report: dict[str, Any]) -> str:
    generated = re.sub(r"[^0-9A-Za-z]+", "-", report["generated_at"]).strip("-")
    return f"{generated}-{report['repository']['commit'][:12]}"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bundle_report(
    report_path: Path,
    repository_root: Path,
    *,
    name: str | None = None,
) -> tuple[Path, Path, dict[str, int]]:
    repository_root = repository_root.resolve()
    report_path = report_path.resolve()
    report = verify_report(report_path, repository_root)
    if not report["publishable"]:
        raise GateError("only a verified publishable report can become canonical")
    if report.get("canonical_bundle") is not None:
        raise GateError("report is already canonical")
    run_commit = report["repository"]["commit"]
    if _current_commit(repository_root) != run_commit:
        raise GateError("canonical bundle must be created at the recorded run commit")

    bundle_name = name or _default_name(report)
    if (
        not _BUNDLE_NAME.fullmatch(bundle_name)
        or bundle_name in {".", ".."}
        or Path(bundle_name).name != bundle_name
    ):
        raise GateError(f"invalid canonical bundle name: {bundle_name!r}")

    canonical_root = repository_root / "results" / "canonical"
    destination = canonical_root / bundle_name
    if destination.exists():
        raise GateError(f"canonical bundle already exists: {destination}")
    canonical_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{bundle_name}-", dir=canonical_root))
    final_prefix = Path("results") / "canonical" / bundle_name
    manifest_path = final_prefix / "manifest.json"
    canonical_report_path = final_prefix / "report.json"
    source_report_path = logical_path(report_path, repository_root)

    logical_bytes = 0
    stored_bytes = 0
    file_count = 0
    object_sizes: dict[str, int] = {}
    manifest_cases: dict[str, Any] = {}
    try:
        for case in report["cases"]:
            if not case["eligible"]:
                continue
            roles: dict[str, Any] = {}
            for role, record in sorted(case["gate"]["evidence"].items()):
                if record["kind"] != "run-output":
                    continue
                source = resolve_logical_path(record["path"], repository_root)
                if not source.is_file():
                    raise GateError(f"run output is missing before bundling: {record['path']}")
                size = source.stat().st_size
                if size > MAX_CANONICAL_OBJECT_BYTES:
                    raise GateError(
                        f"canonical object exceeds {MAX_CANONICAL_OBJECT_BYTES} bytes: "
                        f"{case['id']}/{role} ({size} bytes); use a byte-verifiable archive "
                        "manifest rather than omitting the artifact"
                    )
                if sha256_file(source) != record["sha256"]:
                    raise GateError(
                        f"run output digest changed before bundling: {case['id']}/{role}"
                    )
                logical_bytes += size
                file_count += 1
                digest = record["sha256"]
                object_relative = final_prefix / "objects" / "sha256" / digest
                if digest not in object_sizes:
                    if stored_bytes + size > MAX_CANONICAL_BUNDLE_BYTES:
                        raise GateError(
                            f"canonical bundle exceeds {MAX_CANONICAL_BUNDLE_BYTES} bytes; "
                            "use a byte-verifiable archive manifest rather than omitting artifacts"
                        )
                    staged_object = staging / "objects" / "sha256" / digest
                    staged_object.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, staged_object)
                    if sha256_file(staged_object) != digest:
                        raise GateError(f"copied bundle digest changed: {case['id']}/{role}")
                    object_sizes[digest] = size
                    stored_bytes += size
                elif object_sizes[digest] != size:
                    raise GateError(f"digest collision has inconsistent size: {digest}")
                roles[role] = {
                    "kind": "run-output",
                    "logical_path": record["path"],
                    "bundle_path": object_relative.as_posix(),
                    "sha256": digest,
                    "size_bytes": size,
                }
            manifest_cases[case["id"]] = {"roles": roles}

        manifest = {
            "schema_version": 1,
            "run_commit": run_commit,
            "source_report_path": source_report_path,
            "canonical_report_path": canonical_report_path.as_posix(),
            "file_count": file_count,
            "object_count": len(object_sizes),
            "logical_bytes": logical_bytes,
            "stored_bytes": stored_bytes,
            "cases": manifest_cases,
        }
        staged_manifest = staging / "manifest.json"
        _write_json(staged_manifest, manifest)
        manifest_sha256 = sha256_file(staged_manifest)
        canonical_report = json.loads(json.dumps(report))
        canonical_report["canonical_bundle"] = {
            "manifest_path": manifest_path.as_posix(),
            "manifest_sha256": manifest_sha256,
            "file_count": file_count,
            "object_count": len(object_sizes),
            "logical_bytes": logical_bytes,
            "stored_bytes": stored_bytes,
        }
        _write_json(staging / "report.json", canonical_report)
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    summary = {
        "file_count": file_count,
        "object_count": len(object_sizes),
        "logical_bytes": logical_bytes,
        "stored_bytes": stored_bytes,
    }
    return (
        repository_root / canonical_report_path,
        repository_root / manifest_path,
        summary,
    )


def bundle_cohort(
    report_paths: list[Path],
    repository_root: Path,
) -> tuple[Path, Path, Path, dict[str, int]]:
    if len(report_paths) != 3:
        raise GateError("canonical cohort requires exactly three report paths")
    repository_root = repository_root.resolve()
    resolved = [path.resolve() for path in report_paths]
    reports = [verify_report(path, repository_root) for path in resolved]
    stability = validate_cohort(reports)
    run_commit = reports[0]["repository"]["commit"]
    if _current_commit(repository_root) != run_commit:
        raise GateError("cohort must be bundled at its clean measurement commit")
    digests = [sha256_file(path) for path in resolved]
    identifier = cohort_id(digests)
    name = f"cohort-{identifier}"
    canonical_report_path, manifest_path, summary = bundle_report(
        resolved[0],
        repository_root,
        name=name,
    )
    destination = canonical_report_path.parent
    try:
        bundled_reports = []
        reports_root = destination / "reports"
        reports_root.mkdir()
        for index, (path, report, digest) in enumerate(
            zip(resolved, reports, digests, strict=True),
            start=1,
        ):
            relative = Path("reports") / f"{index:02d}-{digest}.json"
            target = destination / relative
            shutil.copyfile(path, target)
            if sha256_file(target) != digest:
                raise GateError(f"cohort report copy changed: {index}")
            bundled_reports.append(
                {
                    "index": index - 1,
                    "generated_at": report["generated_at"],
                    "source_path": logical_path(path, repository_root),
                    "bundle_path": (
                        target.relative_to(repository_root).as_posix()
                    ),
                    "sha256": digest,
                    "selected": index == 1,
                }
            )
        stability["cohort_id"] = identifier
        stability["reports"] = bundled_reports
        stability_path = destination / "stability.json"
        _write_json(stability_path, stability)
        stability_sha256 = sha256_file(stability_path)

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["schema_version"] = 2
        manifest["cohort"] = {
            "cohort_id": identifier,
            "selection": "chronological-first",
            "selected_report_index": 0,
            "report_count": 3,
            "stability_summary_path": stability_path.relative_to(
                repository_root
            ).as_posix(),
            "stability_summary_sha256": stability_sha256,
            "reports": bundled_reports,
        }
        _write_json(manifest_path, manifest)
        manifest_sha256 = sha256_file(manifest_path)
        canonical = json.loads(canonical_report_path.read_text(encoding="utf-8"))
        canonical["canonical_bundle"]["manifest_sha256"] = manifest_sha256
        canonical["canonical_bundle"].update(
            {
                "cohort_id": identifier,
                "report_count": 3,
                "stability_summary_path": stability_path.relative_to(
                    repository_root
                ).as_posix(),
                "stability_summary_sha256": stability_sha256,
            }
        )
        _write_json(canonical_report_path, canonical)
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return canonical_report_path, manifest_path, stability_path, summary
