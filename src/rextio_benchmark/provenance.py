"""Installed package VCS provenance (PEP 610) and candidate policy binding."""

from __future__ import annotations

import importlib.metadata
import json
import re
import tomllib
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import parse_qs, urlparse

from .cohort import (
    CANDIDATE_COHORT_POLICY,
    CANDIDATE_PLUGIN_PINS,
    FROZEN_CANONICAL_COHORTS,
    RELEASED_CPU_0_1_0_CASE_PACKAGES,
)
from .integration_targets import (
    TARGET_PACKAGE_GIT_URLS,
    TARGET_PACKAGE_VERSIONS,
    TARGET_POLICY_ID,
)
from .verification import GateError

_FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def package_vcs_provenance(
    names: Sequence[str] | None = None,
) -> dict[str, dict[str, str]]:
    """Return portable PEP 610 VCS provenance for installed packages.

    Only packages with a ``direct_url.json`` that declares Git VCS info are
    included. Absolute local paths are never stored — only the URL, VCS kind,
    commit id, and optional requested revision.
    """
    selected = (
        tuple(names)
        if names is not None
        else tuple(sorted(set(CANDIDATE_PLUGIN_PINS) | set(TARGET_PACKAGE_VERSIONS)))
    )
    result: dict[str, dict[str, str]] = {}
    for name in selected:
        try:
            dist = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        version = dist.version
        raw = dist.read_text("direct_url.json")
        if not raw:
            continue
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as error:
            raise GateError(f"{name}: direct_url.json is not valid JSON") from error
        if not isinstance(document, dict):
            raise GateError(f"{name}: direct_url.json must be an object")
        url = document.get("url")
        vcs_info = document.get("vcs_info")
        if not isinstance(url, str) or not url:
            continue
        if not isinstance(vcs_info, dict):
            continue
        vcs = vcs_info.get("vcs")
        commit_id = vcs_info.get("commit_id")
        if vcs != "git" or not isinstance(commit_id, str) or not _FULL_COMMIT.fullmatch(commit_id):
            continue
        if url.startswith("file:") or url.startswith("/") or "://" not in url:
            raise GateError(f"{name}: direct_url must be a portable remote VCS URL")
        record = {
            "version": version,
            "url": url.rstrip("/"),
            "vcs": "git",
            "commit_id": commit_id,
        }
        requested = vcs_info.get("requested_revision")
        if isinstance(requested, str) and requested:
            record["requested_revision"] = requested
        result[name] = record
    return result


def report_package_versions(report: Mapping[str, Any]) -> dict[str, str]:
    """Return versions of frozen candidate plugin distributions across cases.

    Only names in ``CANDIDATE_PLUGIN_PINS`` (``rextio-numpy``,
    ``rextio-tensorflow``) are collected and conflict-checked. Unrelated
    profile-isolated dependencies such as ``numpy`` or ``networkx`` may
    legitimately differ across cases and are ignored here.
    """
    versions: dict[str, str] = {}
    for case in report.get("cases") or []:
        if not isinstance(case, Mapping):
            continue
        packages = case.get("packages") or {}
        if not isinstance(packages, Mapping):
            continue
        for name, version in packages.items():
            if not isinstance(name, str) or not isinstance(version, str):
                continue
            if name not in CANDIDATE_PLUGIN_PINS:
                continue
            prior = versions.get(name)
            if prior is not None and prior != version:
                raise GateError(f"package version conflict for {name}: {prior} vs {version}")
            versions[name] = version
    return versions


def report_named_package_versions(
    report: Mapping[str, Any],
    names: set[str] | frozenset[str],
) -> dict[str, str]:
    """Return conflict-checked versions for an explicit package-name set."""
    versions: dict[str, str] = {}
    for case in report.get("cases") or []:
        if not isinstance(case, Mapping):
            continue
        packages = case.get("packages") or {}
        if not isinstance(packages, Mapping):
            continue
        for name in names:
            version = packages.get(name)
            if not isinstance(version, str):
                continue
            prior = versions.get(name)
            if prior is not None and prior != version:
                raise GateError(f"package version conflict for {name}: {prior} vs {version}")
            versions[name] = version
    return versions


def candidate_plugins_in_versions(versions: Mapping[str, str]) -> dict[str, dict[str, str]]:
    """Return the exact candidate pins that appear by package version in *versions*."""
    present: dict[str, dict[str, str]] = {}
    for name, pin in CANDIDATE_PLUGIN_PINS.items():
        if versions.get(name) == pin["version"]:
            present[name] = {
                "version": pin["version"],
                "git_url": pin["git_url"],
                "rev": pin["rev"],
            }
    return present


def full_candidate_plugin_pins() -> dict[str, dict[str, str]]:
    """Return the complete frozen candidate pin set (numpy + tensorflow 0.1.3)."""
    return {
        name: {
            "version": pin["version"],
            "git_url": pin["git_url"],
            "rev": pin["rev"],
        }
        for name, pin in CANDIDATE_PLUGIN_PINS.items()
    }


def requires_full_candidate_binding(report: Mapping[str, Any]) -> bool:
    """True when a non-released report must carry the full candidate binding.

    Publish-mode, publishable, or canonical-bundle reports on the 0.1.1 line must
    not silently downgrade or omit either candidate plugin. Authentic released
    frozen reports are exempted by the caller via ``is_released_frozen_report``.
    Quick non-publishable non-canonical diagnostics may omit binding.
    """
    if report.get("mode") == "publish":
        return True
    if report.get("publishable") is True:
        return True
    return report.get("canonical_bundle") is not None


def _report_case_packages(report: Mapping[str, Any]) -> dict[str, dict[str, str]] | None:
    """Return case_id -> package versions, or None if malformed/conflicting."""
    cases = report.get("cases")
    if not isinstance(cases, list) or not cases:
        return None
    mapping: dict[str, dict[str, str]] = {}
    for case in cases:
        if not isinstance(case, Mapping):
            return None
        case_id = case.get("id")
        packages = case.get("packages")
        if not isinstance(case_id, str) or not case_id:
            return None
        if not isinstance(packages, Mapping):
            return None
        normalized: dict[str, str] = {}
        for name, version in packages.items():
            if not isinstance(name, str) or not isinstance(version, str):
                return None
            normalized[name] = version
        if case_id in mapping:
            return None
        mapping[case_id] = normalized
    return mapping


def _matches_released_case_packages(report: Mapping[str, Any]) -> bool:
    actual = _report_case_packages(report)
    if actual is None:
        return False
    expected = RELEASED_CPU_0_1_0_CASE_PACKAGES
    if set(actual) != set(expected):
        return False
    return all(actual[case_id] == expected[case_id] for case_id in expected)


def is_released_frozen_report(report: Mapping[str, Any]) -> bool:
    """True only for a genuine released 0.1.0 frozen report shape.

    Exemption requires all of:

    * no ``policy`` / ``package_provenance`` fields;
    * exact registered case-id → package-version mapping from the frozen
      released canonical report (not merely “no candidate versions”);
    * authentic frozen identity:
      - canonical report with ``cohort_id``: that id must be the registered
        released cohort **and** ``repository.commit`` must equal that record's
        ``measurement_commit``;
      - raw historical report without a canonical bundle: exact registered
        ``measurement_commit`` plus the same case/package mapping.

    Spoofed reports that copy only a cohort id/commit, or invent released-looking
    package sets, are not exempt.
    """
    if report.get("policy") is not None or report.get("package_provenance") is not None:
        return False
    if not _matches_released_case_packages(report):
        return False

    repository = report.get("repository")
    commit = repository.get("commit") if isinstance(repository, Mapping) else None
    metadata = report.get("canonical_bundle")

    if isinstance(metadata, Mapping) and "cohort_id" in metadata:
        identifier = metadata.get("cohort_id")
        if not isinstance(identifier, str) or identifier not in FROZEN_CANONICAL_COHORTS:
            return False
        frozen = FROZEN_CANONICAL_COHORTS[identifier]
        if frozen.get("policy_id") != "released-cpu-0.1.0":
            return False
        return commit == frozen.get("measurement_commit")

    # Raw historical three-run reports (no canonical bundle).
    if metadata is not None:
        return False
    if not isinstance(commit, str):
        return False
    for frozen in FROZEN_CANONICAL_COHORTS.values():
        if (
            frozen.get("policy_id") == "released-cpu-0.1.0"
            and frozen.get("measurement_commit") == commit
        ):
            return True
    return False


def assemble_candidate_policy_binding(
    versions: Mapping[str, str],
    package_provenance: Mapping[str, Mapping[str, str]],
) -> tuple[dict[str, Any] | None, dict[str, dict[str, str]] | None]:
    """Build report-level policy + provenance when candidate plugin versions are present.

    Returns ``(None, None)`` when no candidate plugin versions appear. Fail closed
    when a candidate version is present but installed PEP 610 provenance is missing
    or mismatches the exact policy pins.
    """
    present = candidate_plugins_in_versions(versions)
    if not present:
        return None, None
    bound_provenance: dict[str, dict[str, str]] = {}
    for name, pin in present.items():
        record = package_provenance.get(name)
        if record is None:
            raise GateError(
                f"candidate package {name} {pin['version']} lacks installed direct_url provenance"
            )
        _require_provenance_matches_pin(name, record, pin)
        bound_provenance[name] = {
            "version": record["version"],
            "url": record["url"],
            "vcs": record["vcs"],
            "commit_id": record["commit_id"],
            **(
                {"requested_revision": record["requested_revision"]}
                if "requested_revision" in record
                else {}
            ),
        }
    policy = {
        "policy_id": CANDIDATE_COHORT_POLICY["policy_id"],
        "policy_version": CANDIDATE_COHORT_POLICY["policy_version"],
        "status": CANDIDATE_COHORT_POLICY["status"],
        "candidate_plugins": {
            name: {
                "version": pin["version"],
                "git_url": pin["git_url"],
                "rev": pin["rev"],
            }
            for name, pin in sorted(present.items())
        },
    }
    return policy, bound_provenance


def _require_provenance_matches_pin(
    name: str,
    record: Mapping[str, str],
    pin: Mapping[str, str],
) -> None:
    if record.get("version") != pin["version"]:
        raise GateError(
            f"{name}: provenance version {record.get('version')!r} != pin {pin['version']!r}"
        )
    if record.get("vcs") != "git":
        raise GateError(f"{name}: provenance vcs must be git")
    if record.get("commit_id") != pin["rev"]:
        raise GateError(
            f"{name}: provenance commit {record.get('commit_id')!r} != pin rev {pin['rev']!r}"
        )
    url = (record.get("url") or "").rstrip("/")
    expected = pin["git_url"].rstrip("/")
    if url != expected:
        raise GateError(f"{name}: provenance url {url!r} != pin {expected!r}")
    requested = record.get("requested_revision")
    # Allow full rev or abbreviated requested revision; reject other values.
    if (
        requested is not None
        and requested not in {pin["rev"], pin["rev"][:12]}
        and not pin["rev"].startswith(requested)
        and requested != pin["rev"]
    ):
        raise GateError(
            f"{name}: requested_revision {requested!r} does not match pin rev {pin['rev']!r}"
        )


def _git_ref_matches(git_value: object, url: str, rev: str) -> bool:
    """True when a uv git field names *url* and full *rev* (query and optional fragment)."""
    if not isinstance(git_value, str) or not git_value:
        return False
    parsed = urlparse(git_value)
    if parsed.scheme not in {"http", "https", "ssh", "git"}:
        return False
    # Reconstruct repo URL without query/fragment; strip trailing slash only.
    repo = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    if repo != url.rstrip("/"):
        return False
    query = parse_qs(parsed.query, keep_blank_values=False)
    revs = query.get("rev") or []
    if len(revs) != 1 or revs[0] != rev:
        return False
    return not parsed.fragment or parsed.fragment == rev


def _pyproject_sources_bind(data: Mapping[str, Any], package: str, url: str, rev: str) -> bool:
    tool = data.get("tool")
    if not isinstance(tool, Mapping):
        return False
    uv = tool.get("uv")
    if not isinstance(uv, Mapping):
        return False
    sources = uv.get("sources")
    if not isinstance(sources, Mapping):
        return False
    entry = sources.get(package)
    if not isinstance(entry, Mapping):
        return False
    git = entry.get("git")
    entry_rev = entry.get("rev")
    if not isinstance(git, str) or not isinstance(entry_rev, str):
        return False
    return git.rstrip("/") == url.rstrip("/") and entry_rev == rev


def _uv_lock_binds(data: Mapping[str, Any], package: str, url: str, rev: str) -> bool:
    """Prove the named package table's own ``source.git`` binds *url*+*rev*.

    ``metadata.requires-dist`` / ``dependencies`` entries may also carry the
    pin, but they are never sufficient when the named package's own source is
    registry, missing, or wrong.
    """
    packages = data.get("package")
    if not isinstance(packages, list):
        return False
    for pkg in packages:
        if not isinstance(pkg, Mapping):
            continue
        if pkg.get("name") != package:
            continue
        source = pkg.get("source")
        if not isinstance(source, Mapping):
            return False
        return _git_ref_matches(source.get("git"), url, rev)
    return False


def lock_or_manifest_binds_pin(text: str, package: str, pin: Mapping[str, str]) -> bool:
    """True when structured TOML proves *package* is bound to *pin*'s git URL+rev.

    Accepts either:

    * ``pyproject.toml`` ``[tool.uv.sources].<package> = { git, rev }``; or
    * ``uv.lock`` named package table with ``source.git`` binding the exact
      URL and full revision (dependency metadata alone is not enough).

    Substring/heuristic matching is intentionally not used.
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return False
    if not isinstance(data, dict):
        return False
    rev = pin["rev"]
    url = pin["git_url"].rstrip("/")
    if _pyproject_sources_bind(data, package, url, rev):
        return True
    return _uv_lock_binds(data, package, url, rev)


def bound_candidate_pins_from_report(report: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    """Return verified candidate pins from report policy + provenance, or empty.

    Fail closed when policy/provenance is present but inconsistent. Does not
    invent pins from package versions alone.
    """
    policy = report.get("policy")
    provenance = report.get("package_provenance")
    if policy is None and provenance is None:
        return {}
    if not isinstance(policy, Mapping) or not isinstance(provenance, Mapping):
        raise GateError("candidate policy and package_provenance must both be objects")
    policy_id = policy.get("policy_id")
    if policy_id not in {CANDIDATE_COHORT_POLICY["policy_id"], TARGET_POLICY_ID}:
        raise GateError(f"unsupported candidate policy_id: {policy_id!r}")
    if policy.get("policy_version") != CANDIDATE_COHORT_POLICY["policy_version"]:
        raise GateError("candidate policy_version differs")
    next_policy = policy_id == TARGET_POLICY_ID
    pins_key = "candidate_packages" if next_policy else "candidate_plugins"
    pins = policy.get(pins_key)
    if not isinstance(pins, Mapping) or not pins:
        raise GateError(f"candidate policy lacks {pins_key}")
    if next_policy and set(pins) != set(TARGET_PACKAGE_VERSIONS):
        raise GateError("next candidate policy package set differs")
    bound: dict[str, dict[str, str]] = {}
    for name, pin in pins.items():
        if not isinstance(name, str) or not isinstance(pin, Mapping):
            raise GateError(f"{pins_key} entries must be objects")
        normalized = {
            "version": str(pin.get("version", "")),
            "git_url": str(pin.get("git_url", "")).rstrip("/"),
            "rev": str(pin.get("rev", "")),
        }
        if next_policy:
            if name not in TARGET_PACKAGE_VERSIONS:
                raise GateError(f"unknown next candidate package in policy: {name}")
            if (
                normalized["version"] != TARGET_PACKAGE_VERSIONS[name]
                or normalized["git_url"] != TARGET_PACKAGE_GIT_URLS[name]
                or _FULL_COMMIT.fullmatch(normalized["rev"]) is None
            ):
                raise GateError(f"next candidate policy pin for {name} differs")
        else:
            expected = CANDIDATE_PLUGIN_PINS.get(name)
            if expected is None:
                raise GateError(f"unknown candidate plugin in policy: {name}")
            if (
                normalized["version"] != expected["version"]
                or normalized["git_url"] != expected["git_url"].rstrip("/")
                or normalized["rev"] != expected["rev"]
            ):
                raise GateError(f"policy pin for {name} does not match frozen candidate pins")
        record = provenance.get(name)
        if not isinstance(record, Mapping):
            raise GateError(f"package_provenance missing for policy pin {name}")
        portable = {str(key): str(value) for key, value in record.items()}
        _require_provenance_matches_pin(name, portable, normalized)
        bound[name] = normalized
    return bound
