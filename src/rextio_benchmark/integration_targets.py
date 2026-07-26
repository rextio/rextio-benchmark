"""Fail-closed activation surface for the next candidate diagnostic cohort."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .verification import GateError

TARGET_CONFIG_PATH = Path("profiles/next-candidate.toml")
TARGET_POLICY_ID = "candidate-boundary-prepost-0.1.1"
TARGET_PACKAGE_VERSIONS = {
    "rextio": "0.1.7",
    "rextio-numpy": "0.1.3",
    "rextio-tensorflow": "0.1.3",
    "rextio-torch": "0.1.3",
}
NEXT_DIAGNOSTIC_CASE_IDS = frozenset(
    {
        "numpy-f64-1d-boundary-direct-sink",
        "tensorflow-cpu-small-batch-prepost",
        "torch-cpu-small-batch-prepost",
    }
)

_FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class IntegrationTarget:
    name: str
    version: str
    git_url: str
    rev: str
    profiles: tuple[str, ...]

    def pin(self) -> dict[str, str]:
        return {
            "version": self.version,
            "git_url": self.git_url,
            "rev": self.rev,
        }


def load_integration_targets(repository_root: Path) -> tuple[IntegrationTarget, ...]:
    path = repository_root / TARGET_CONFIG_PATH
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise GateError(f"next candidate target config is unavailable: {error}") from error
    if document.get("schema_version") != 1:
        raise GateError("next candidate target schema_version must be 1")
    if document.get("policy_id") != TARGET_POLICY_ID:
        raise GateError("next candidate target policy_id differs")
    case_ids = document.get("diagnostic_case_ids")
    if not isinstance(case_ids, list) or set(case_ids) != NEXT_DIAGNOSTIC_CASE_IDS:
        raise GateError("next candidate diagnostic_case_ids differ")
    packages = document.get("packages")
    if not isinstance(packages, list):
        raise GateError("next candidate packages must be an array")
    targets: list[IntegrationTarget] = []
    for record in packages:
        if not isinstance(record, Mapping):
            raise GateError("next candidate package entries must be tables")
        name = record.get("name")
        version = record.get("version")
        git_url = record.get("git_url")
        rev = record.get("rev")
        profiles = record.get("profiles")
        if (
            not isinstance(name, str)
            or not isinstance(version, str)
            or not isinstance(git_url, str)
            or not isinstance(rev, str)
            or not isinstance(profiles, list)
            or not profiles
            or any(not isinstance(profile, str) or not profile for profile in profiles)
        ):
            raise GateError("next candidate package entry has invalid fields")
        targets.append(
            IntegrationTarget(
                name=name,
                version=version,
                git_url=git_url.rstrip("/"),
                rev=rev,
                profiles=tuple(profiles),
            )
        )
    by_name = {target.name: target for target in targets}
    if len(by_name) != len(targets) or set(by_name) != set(TARGET_PACKAGE_VERSIONS):
        raise GateError("next candidate package set differs")
    for name, expected_version in TARGET_PACKAGE_VERSIONS.items():
        if by_name[name].version != expected_version:
            raise GateError(f"next candidate version for {name} differs")
    return tuple(sorted(targets, key=lambda target: target.name))


def _profile_binding_blockers(
    repository_root: Path,
    target: IntegrationTarget,
) -> list[str]:
    blockers: list[str] = []
    for profile in target.profiles:
        path = repository_root / "profiles" / profile / "pyproject.toml"
        try:
            document = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            blockers.append(f"{target.name}: invalid profile manifest {profile}")
            continue
        dependencies = document.get("project", {}).get("dependencies", [])
        if f"{target.name}=={target.version}" not in dependencies:
            blockers.append(
                f"{target.name}: profile {profile} does not select {target.version}"
            )
        sources = document.get("tool", {}).get("uv", {}).get("sources", {})
        source = sources.get(target.name) if isinstance(sources, Mapping) else None
        if not isinstance(source, Mapping):
            blockers.append(f"{target.name}: profile {profile} lacks exact Git source")
            continue
        if source.get("git", "").rstrip("/") != target.git_url or source.get("rev") != target.rev:
            blockers.append(f"{target.name}: profile {profile} Git source differs")
    return blockers


def integration_target_blockers(repository_root: Path) -> list[str]:
    """Return every reason the new diagnostic cohort cannot run or publish."""
    try:
        targets = load_integration_targets(repository_root)
    except GateError as error:
        return [str(error)]
    blockers: list[str] = []
    for target in targets:
        if not _FULL_COMMIT.fullmatch(target.rev):
            blockers.append(f"{target.name}: pending full integration SHA")
            continue
        blockers.extend(_profile_binding_blockers(repository_root, target))
    return blockers


def require_integration_targets_ready(repository_root: Path) -> tuple[IntegrationTarget, ...]:
    blockers = integration_target_blockers(repository_root)
    if blockers:
        raise GateError("next candidate diagnostics are blocked: " + "; ".join(blockers))
    return load_integration_targets(repository_root)


def integration_policy_binding(repository_root: Path) -> dict[str, Any]:
    """Return a runnable policy only after every target and profile is exact-bound."""
    targets = require_integration_targets_ready(repository_root)
    return {
        "policy_id": TARGET_POLICY_ID,
        "policy_version": 1,
        "status": "pre-measurement",
        "candidate_packages": {target.name: target.pin() for target in targets},
    }


def validate_integration_provenance(
    repository_root: Path,
    provenance: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, str]]:
    """Validate exact installed VCS provenance for every runnable target."""
    targets = require_integration_targets_ready(repository_root)
    bound: dict[str, dict[str, str]] = {}
    for target in targets:
        record = provenance.get(target.name)
        if not isinstance(record, Mapping):
            raise GateError(f"{target.name}: installed VCS provenance is missing")
        if (
            record.get("version") != target.version
            or record.get("vcs") != "git"
            or record.get("url", "").rstrip("/") != target.git_url
            or record.get("commit_id") != target.rev
        ):
            raise GateError(f"{target.name}: installed VCS provenance differs")
        bound[target.name] = {str(key): str(value) for key, value in record.items()}
    return bound


def cases_require_integration_targets(case_ids: set[str] | frozenset[str]) -> bool:
    return bool(NEXT_DIAGNOSTIC_CASE_IDS & case_ids)
