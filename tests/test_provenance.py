"""Candidate policy / PEP 610 provenance binding and README fail-closed tests."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from rextio_benchmark.cohort import (
    CANDIDATE_COHORT_POLICY,
    CANDIDATE_PLUGIN_PINS,
    FROZEN_CANONICAL_COHORTS,
    RELEASED_CANONICAL_COHORT_DIR,
    RELEASED_CPU_0_1_0_CASE_PACKAGES,
    validate_cohort,
)
from rextio_benchmark.integration_targets import (
    TARGET_CONFIG_PATH,
    TARGET_POLICY_ID,
    integration_target_pins,
    parse_integration_targets,
)
from rextio_benchmark.models import BenchmarkCase
from rextio_benchmark.provenance import (
    assemble_candidate_policy_binding,
    bound_candidate_pins_from_report,
    candidate_plugins_in_versions,
    is_released_frozen_report,
    lock_or_manifest_binds_pin,
    report_package_versions,
)
from rextio_benchmark.readme_blocks import generate_blocks
from rextio_benchmark.verification import GateError
from rextio_benchmark.verifier import (
    _replay_generated_expectations,
    _verify_candidate_policy_and_provenance,
)

ROOT = Path(__file__).resolve().parents[1]
NUMPY_PIN = CANDIDATE_PLUGIN_PINS["rextio-numpy"]
TF_PIN = CANDIDATE_PLUGIN_PINS["rextio-tensorflow"]


def _policy_and_provenance(
    plugins: dict[str, dict[str, str]] | None = None,
) -> tuple[dict, dict]:
    pins = plugins or {
        "rextio-numpy": {
            "version": NUMPY_PIN["version"],
            "git_url": NUMPY_PIN["git_url"],
            "rev": NUMPY_PIN["rev"],
        },
        "rextio-tensorflow": {
            "version": TF_PIN["version"],
            "git_url": TF_PIN["git_url"],
            "rev": TF_PIN["rev"],
        },
    }
    policy = {
        "policy_id": CANDIDATE_COHORT_POLICY["policy_id"],
        "policy_version": CANDIDATE_COHORT_POLICY["policy_version"],
        "status": "pre-measurement",
        "candidate_plugins": pins,
    }
    provenance = {
        name: {
            "version": pin["version"],
            "url": pin["git_url"],
            "vcs": "git",
            "commit_id": pin["rev"],
            "requested_revision": pin["rev"],
        }
        for name, pin in pins.items()
    }
    return policy, provenance


def _case(
    case_id: str,
    *,
    packages: dict[str, str],
    profile: str,
) -> dict:
    return {
        "id": case_id,
        "eligible": True,
        "blockers": [],
        "packages": packages,
        "gate": {
            "evidence": {
                "profile_manifest": {
                    "kind": "run-input",
                    "path": f"profiles/{profile}/pyproject.toml",
                    "sha256": "0" * 64,
                },
                "profile_lock": {
                    "kind": "run-input",
                    "path": f"profiles/{profile}/uv.lock",
                    "sha256": "1" * 64,
                },
            }
        },
        "lanes": {
            "python-source": {"steady_state": {"median_ns": 2_000_000.0}},
            "rextio-native": {"steady_state": {"median_ns": 1_000_000.0}},
        },
        "paired": {
            "median_speedup": 2.0,
            "orders": [["python-source", "rextio-native"]] * 10,
        },
    }


def _minimal_report(*, with_binding: bool = True) -> dict:
    base_packages = {
        "rextio": "0.1.6",
        "rextio-numpy": "0.1.3",
        "rextio-networkx": "0.1.1",
        "rextio-pandas": "0.1.2",
    }
    torch_packages = {"rextio": "0.1.6", "rextio-torch": "0.1.2"}
    tf_packages = {
        "rextio": "0.1.6",
        "rextio-tensorflow": "0.1.3",
        "tensorflow": "2.21.0",
    }
    cases = [
        _case("core-hybrid", packages=base_packages, profile="base"),
        _case("core-native-executable", packages=base_packages, profile="base"),
        _case("networkx-dijkstra", packages=base_packages, profile="base"),
        _case("numpy-mixed-fusion", packages=base_packages, profile="base"),
        _case("numpy-blas-dot-negative-control", packages=base_packages, profile="base"),
        _case("numpy-mixed-nonfused-phase1", packages=base_packages, profile="base"),
        _case("pandas-series-map", packages=base_packages, profile="base"),
        _case("torch-cpu-deep-mlp", packages=torch_packages, profile="torch-cpu"),
        _case(
            "tensorflow-cpu-eager-chain",
            packages=tf_packages,
            profile="tensorflow-cpu",
        ),
    ]
    report: dict = {
        "schema_version": 1,
        "generated_at": "2026-07-26T00:00:00+00:00",
        "mode": "publish",
        "publishable": True,
        "repository": {"commit": "a" * 40, "dirty": False},
        "system": {
            "platform": "macOS-15",
            "machine": "arm64",
            "processor": "arm",
            "python_controller": "3.11.9",
            "toolchain": {"rustc": "rustc 1.88", "cargo": "cargo 1.88"},
            "host": {"model": "Mac15,8", "cpu_brand": "Apple M3 Pro"},
        },
        "configuration": {"pairs": 12},
        "cases": cases,
        "canonical_bundle": {
            "manifest_path": "results/canonical/cohort/manifest.json",
            "report_markdown_path": "results/canonical/cohort/report.md",
        },
    }
    if with_binding:
        policy, provenance = _policy_and_provenance()
        report["policy"] = policy
        report["package_provenance"] = provenance
    return report


RELEASED_COHORT_ID = next(iter(FROZEN_CANONICAL_COHORTS))
RELEASED_MEASUREMENT_COMMIT = FROZEN_CANONICAL_COHORTS[RELEASED_COHORT_ID]["measurement_commit"]


def test_lock_and_manifest_bind_exact_next_candidate_pins() -> None:
    targets = parse_integration_targets(
        (ROOT / TARGET_CONFIG_PATH).read_text(encoding="utf-8")
    )
    for target in targets:
        pin = target.pin()
        for profile in target.profiles:
            manifest = (ROOT / "profiles" / profile / "pyproject.toml").read_text(
                encoding="utf-8"
            )
            lock = (ROOT / "profiles" / profile / "uv.lock").read_text(
                encoding="utf-8"
            )
            assert lock_or_manifest_binds_pin(manifest, target.name, pin)
            assert lock_or_manifest_binds_pin(lock, target.name, pin)
    numpy = next(target for target in targets if target.name == "rextio-numpy")
    base_lock = (ROOT / "profiles/base/uv.lock").read_text(encoding="utf-8")
    bad = numpy.pin() | {"rev": "0" * 40}
    assert not lock_or_manifest_binds_pin(base_lock, numpy.name, bad)


def test_lock_binding_rejects_deceptive_unrelated_package_source() -> None:
    """Substring-adjacent unrelated package must not satisfy the named pin."""
    url = NUMPY_PIN["git_url"]
    rev = NUMPY_PIN["rev"]
    deceptive_lock = f'''
version = 1
revision = 2
requires-python = "==3.11.*"

[[package]]
name = "unrelated-decoy"
version = "9.9.9"
source = {{ git = "{url}?rev={rev}#{rev}" }}

[[package]]
name = "rextio-numpy"
version = "0.1.3"
source = {{ registry = "https://pypi.org/simple" }}
'''
    assert not lock_or_manifest_binds_pin(deceptive_lock, "rextio-numpy", NUMPY_PIN)

    deceptive_pyproject = f'''
[project]
name = "fixture"
version = "0.0.0"
dependencies = ["rextio-numpy==0.1.3"]

[tool.uv.sources]
# Decoy binds the candidate URL/rev under a different package key.
unrelated-decoy = {{ git = "{url}", rev = "{rev}" }}
'''
    assert not lock_or_manifest_binds_pin(deceptive_pyproject, "rextio-numpy", NUMPY_PIN)

    # Even comments/raw text containing the pin must not bypass structured parse.
    text_only = (
        f'# rextio-numpy git = "{url}" rev = "{rev}"\n'
        f'name = "rextio-numpy"\n'
        f'source = {{ git = "{url}?rev={rev}" }}\n'
    )
    # Not valid full lock structure for the named package table — fail closed.
    assert not lock_or_manifest_binds_pin(text_only, "rextio-numpy", NUMPY_PIN)

    wrong_rev_sources = f'''
[tool.uv.sources]
rextio-numpy = {{ git = "{url}", rev = "{"0" * 40}" }}
'''
    assert not lock_or_manifest_binds_pin(wrong_rev_sources, "rextio-numpy", NUMPY_PIN)

    # Valid structured package-source bind.
    good_lock = f'''
version = 1
[[package]]
name = "rextio-numpy"
version = "0.1.3"
source = {{ git = "{url}?rev={rev}#{rev}" }}
'''
    assert lock_or_manifest_binds_pin(good_lock, "rextio-numpy", NUMPY_PIN)


def test_lock_binding_rejects_metadata_exact_with_registry_package_source() -> None:
    """Exact metadata.requires-dist pin is insufficient if package source is registry."""
    url = NUMPY_PIN["git_url"]
    rev = NUMPY_PIN["rev"]
    deceptive = f'''
version = 1
[[package]]
name = "workspace"
version = "0.0.0"
source = {{ virtual = "." }}
[package.metadata]
requires-dist = [
  {{ name = "rextio-numpy", git = "{url}?rev={rev}" }},
]

[[package]]
name = "rextio-numpy"
version = "0.1.3"
source = {{ registry = "https://pypi.org/simple" }}
'''
    assert not lock_or_manifest_binds_pin(deceptive, "rextio-numpy", NUMPY_PIN)

    metadata_only = f'''
version = 1
[[package]]
name = "workspace"
version = "0.0.0"
source = {{ virtual = "." }}
[package.metadata]
requires-dist = [
  {{ name = "rextio-numpy", git = "{url}?rev={rev}" }},
]
'''
    assert not lock_or_manifest_binds_pin(metadata_only, "rextio-numpy", NUMPY_PIN)


def test_spoofed_released_cohort_id_does_not_exempt_candidate_report() -> None:
    """Copying the frozen cohort_id must not skip candidate policy gates."""
    report = _minimal_report(with_binding=False)
    report["canonical_bundle"] = {
        "cohort_id": RELEASED_COHORT_ID,
        "manifest_path": "results/canonical/cohort/manifest.json",
        "report_markdown_path": "results/canonical/cohort/report.md",
    }
    assert is_released_frozen_report(report) is False
    with pytest.raises(GateError, match="requires policy and package_provenance"):
        _verify_candidate_policy_and_provenance(report, ROOT)


def test_spoofed_released_measurement_commit_does_not_exempt_candidate_report() -> None:
    """Copying the frozen measurement_commit must not skip candidate policy gates."""
    report = _minimal_report(with_binding=False)
    report.pop("canonical_bundle", None)
    report["repository"]["commit"] = RELEASED_MEASUREMENT_COMMIT
    assert is_released_frozen_report(report) is False
    with pytest.raises(GateError, match="requires policy and package_provenance"):
        _verify_candidate_policy_and_provenance(report, ROOT)


def _released_shape_report(
    *,
    with_canonical: bool = True,
    commit: str | None = RELEASED_MEASUREMENT_COMMIT,
    cohort_id: str | None = RELEASED_COHORT_ID,
    case_packages: dict[str, dict[str, str]] | None = None,
) -> dict:
    packages = case_packages or RELEASED_CPU_0_1_0_CASE_PACKAGES
    report: dict = {
        "repository": {"commit": commit, "dirty": False},
        "cases": [
            {"id": case_id, "packages": dict(versions)} for case_id, versions in packages.items()
        ],
    }
    if with_canonical:
        report["canonical_bundle"] = {
            "cohort_id": cohort_id,
            "manifest_path": f"{RELEASED_CANONICAL_COHORT_DIR}/manifest.json",
            "report_markdown_path": f"{RELEASED_CANONICAL_COHORT_DIR}/report.md",
        }
    return report


def test_genuine_released_shape_is_exempt() -> None:
    # Real frozen canonical report on disk.
    real = json.loads(
        (ROOT / RELEASED_CANONICAL_COHORT_DIR / "report.json").read_text(encoding="utf-8")
    )
    assert is_released_frozen_report(real) is True

    # Exact registered mapping + identity also exempts without loading the file.
    synthetic = _released_shape_report()
    assert is_released_frozen_report(synthetic) is True

    # Raw historical path (no canonical bundle) with exact measurement_commit.
    raw = _released_shape_report(with_canonical=False)
    assert is_released_frozen_report(raw) is True

    # policy alone spoils exemption even with full released shape
    report_with_policy = deepcopy(synthetic)
    report_with_policy["policy"] = {"policy_id": "candidate-plugin-0.1.3-pre-measurement"}
    assert is_released_frozen_report(report_with_policy) is False


def test_released_exemption_rejects_wrong_missing_extra_cases_and_versions() -> None:
    base = _released_shape_report()

    missing = deepcopy(base)
    missing["cases"] = [case for case in missing["cases"] if case["id"] != "core-hybrid"]
    assert is_released_frozen_report(missing) is False

    extra = deepcopy(base)
    extra["cases"].append(
        {
            "id": "numpy-mixed-nonfused-phase1",
            "packages": dict(RELEASED_CPU_0_1_0_CASE_PACKAGES["numpy-mixed-fusion"]),
        }
    )
    assert is_released_frozen_report(extra) is False

    wrong_plugin = deepcopy(base)
    for case in wrong_plugin["cases"]:
        if case["id"] == "numpy-mixed-fusion":
            case["packages"] = {**case["packages"], "rextio-numpy": "0.1.3"}
    assert is_released_frozen_report(wrong_plugin) is False

    # Correct cohort id with wrong measurement commit.
    wrong_commit = deepcopy(base)
    wrong_commit["repository"]["commit"] = "0" * 40
    assert is_released_frozen_report(wrong_commit) is False

    # Arbitrary released-looking package set (subset only) is not enough.
    arbitrary = {
        "canonical_bundle": {"cohort_id": RELEASED_COHORT_ID},
        "repository": {"commit": RELEASED_MEASUREMENT_COMMIT},
        "cases": [
            {
                "id": "numpy-mixed-fusion",
                "packages": {"rextio": "0.1.6", "rextio-numpy": "0.1.2"},
            }
        ],
    }
    assert is_released_frozen_report(arbitrary) is False

    # Registered mapping must match the frozen report bytes.
    real = json.loads(
        (ROOT / RELEASED_CANONICAL_COHORT_DIR / "report.json").read_text(encoding="utf-8")
    )
    actual = {case["id"]: case["packages"] for case in real["cases"]}
    assert actual == RELEASED_CPU_0_1_0_CASE_PACKAGES


def test_report_package_versions_allows_heterogeneous_unrelated_deps() -> None:
    """Isolated profiles may ship different numpy/networkx; only candidate plugins conflict."""
    report = {
        "cases": [
            {
                "id": "numpy-mixed-fusion",
                "packages": {
                    "numpy": "2.3.5",
                    "networkx": "3.5",
                    "rextio": "0.1.6",
                    "rextio-numpy": "0.1.3",
                },
            },
            {
                "id": "tensorflow-cpu-eager-chain",
                "packages": {
                    "numpy": "2.4.6",
                    "networkx": "3.6.1",
                    "rextio": "0.1.6",
                    "rextio-tensorflow": "0.1.3",
                },
            },
            {
                "id": "torch-cpu-deep-mlp",
                "packages": {
                    "numpy": "2.4.6",
                    "networkx": "3.6.1",
                    "rextio": "0.1.6",
                    "rextio-torch": "0.1.2",
                },
            },
        ]
    }
    versions = report_package_versions(report)
    assert versions == {
        "rextio-numpy": "0.1.3",
        "rextio-tensorflow": "0.1.3",
    }
    assert set(candidate_plugins_in_versions(versions)) == {
        "rextio-numpy",
        "rextio-tensorflow",
    }


def test_report_package_versions_rejects_candidate_plugin_conflict() -> None:
    report = {
        "cases": [
            {
                "id": "numpy-mixed-fusion",
                "packages": {"rextio-numpy": "0.1.3", "numpy": "2.3.5"},
            },
            {
                "id": "numpy-blas-dot-negative-control",
                "packages": {"rextio-numpy": "0.1.2", "numpy": "2.3.5"},
            },
        ]
    }
    with pytest.raises(GateError, match="package version conflict for rextio-numpy"):
        report_package_versions(report)


def test_assemble_fails_without_direct_url_provenance() -> None:
    versions = {"rextio-numpy": "0.1.3"}
    with pytest.raises(GateError, match="lacks installed direct_url"):
        assemble_candidate_policy_binding(versions, {})


def test_assemble_binds_matching_provenance() -> None:
    versions = {"rextio-numpy": "0.1.3", "rextio": "0.1.6"}
    provenance = {
        "rextio-numpy": {
            "version": "0.1.3",
            "url": NUMPY_PIN["git_url"],
            "vcs": "git",
            "commit_id": NUMPY_PIN["rev"],
            "requested_revision": NUMPY_PIN["rev"],
        }
    }
    policy, bound = assemble_candidate_policy_binding(versions, provenance)
    assert policy is not None and bound is not None
    assert policy["policy_id"] == "candidate-plugin-0.1.3-pre-measurement"
    assert bound["rextio-numpy"]["commit_id"] == NUMPY_PIN["rev"]


def test_assemble_rejects_url_or_revision_mismatch() -> None:
    versions = {"rextio-numpy": "0.1.3"}
    bad_url = {
        "rextio-numpy": {
            "version": "0.1.3",
            "url": "https://evil.example/rextio-numpy",
            "vcs": "git",
            "commit_id": NUMPY_PIN["rev"],
        }
    }
    with pytest.raises(GateError, match="url"):
        assemble_candidate_policy_binding(versions, bad_url)
    bad_rev = {
        "rextio-numpy": {
            "version": "0.1.3",
            "url": NUMPY_PIN["git_url"],
            "vcs": "git",
            "commit_id": "0" * 40,
        }
    }
    with pytest.raises(GateError, match="commit"):
        assemble_candidate_policy_binding(versions, bad_rev)


def test_verify_report_requires_binding_for_candidate_versions(tmp_path: Path) -> None:
    report = _minimal_report(with_binding=False)
    with pytest.raises(GateError, match="requires policy and package_provenance"):
        _verify_candidate_policy_and_provenance(report, ROOT)


def test_verify_rejects_tampered_policy_id(tmp_path: Path) -> None:
    report = _minimal_report(with_binding=True)
    report["policy"]["policy_id"] = "not-a-real-policy"
    with pytest.raises(GateError, match="unsupported candidate policy_id"):
        _verify_candidate_policy_and_provenance(report, ROOT)


def test_verify_rejects_tampered_provenance_revision(tmp_path: Path) -> None:
    report = _minimal_report(with_binding=True)
    report["package_provenance"]["rextio-numpy"]["commit_id"] = "f" * 40
    with pytest.raises(GateError, match="commit"):
        _verify_candidate_policy_and_provenance(report, ROOT)


def test_verify_rejects_lock_that_does_not_bind_pin(tmp_path: Path) -> None:
    report = _minimal_report(with_binding=True)
    # Only numpy/tf profiles matter; write locks that omit exact git revs.
    for profile in ("base", "tensorflow-cpu"):
        lock = tmp_path / f"profiles/{profile}/uv.lock"
        lock.parent.mkdir(parents=True)
        lock.write_text('name = "placeholder"\n', encoding="utf-8")
        manifest = tmp_path / f"profiles/{profile}/pyproject.toml"
        manifest.write_text('name = "placeholder"\n', encoding="utf-8")
    for case in report["cases"]:
        for role in ("profile_lock", "profile_manifest"):
            case["gate"]["evidence"][role]["kind"] = "run-output"
    report["repository"]["commit"] = None
    with pytest.raises(GateError, match="no profile_lock binds"):
        _verify_candidate_policy_and_provenance(report, tmp_path)


def test_verify_rejects_historical_candidate_against_advanced_live_profiles() -> None:
    report = _minimal_report(with_binding=True)
    report["repository"]["commit"] = None  # force live path reads of profile files
    with pytest.raises(GateError, match="no profile_lock binds rextio-numpy"):
        _verify_candidate_policy_and_provenance(report, ROOT)


def test_validate_cohort_includes_policy_in_identity_and_summary() -> None:
    reports = []
    for index in range(3):
        report = _minimal_report(with_binding=True)
        report["generated_at"] = f"2026-07-26T00:0{index}:00+00:00"
        report.pop("canonical_bundle", None)
        reports.append(report)
    summary = validate_cohort(reports)
    assert summary["policy_id"] == "candidate-plugin-0.1.3-pre-measurement"
    assert summary["candidate_plugins"]["rextio-numpy"]["rev"] == NUMPY_PIN["rev"]
    assert summary["candidate_plugins"]["rextio-tensorflow"]["rev"] == TF_PIN["rev"]

    # Tampered policy breaks frozen identity.
    reports[1] = deepcopy(reports[1])
    reports[1]["policy"]["policy_id"] = "tampered"
    with pytest.raises(GateError, match="frozen run identity"):
        validate_cohort(reports)


def test_validate_cohort_released_shape_omits_candidate_fields() -> None:
    """Released-style reports without policy keep the historical summary shape."""
    from test_publication import _report

    reports = [_report(f"2026-07-26T00:0{index}:00+00:00") for index in range(3)]
    summary = validate_cohort(reports)
    assert "policy_id" not in summary
    assert "candidate_plugins" not in summary


def test_readme_labels_candidate_only_from_bound_provenance() -> None:
    report = _minimal_report(with_binding=True)
    blocks = generate_blocks(
        report,
        report_logical_path="results/canonical/cohort/report.json",
        measurement_commit="a" * 40,
        evidence_commit="b" * 40,
        github_url="https://github.com/rextio/rextio-benchmark",
    )
    english = blocks["README.md"]
    assert "rextio-numpy 0.1.3 candidate@7316c47393a8" in english
    assert "rextio-tensorflow 0.1.3 candidate@346ca58148ed" in english
    assert "PyPI" in english


def test_readme_labels_all_four_next_candidate_packages_in_every_locale() -> None:
    report = _minimal_report(with_binding=False)
    for case in report["cases"]:
        packages = dict(case["packages"])
        packages["rextio"] = "0.1.7"
        if "rextio-torch" in packages:
            packages["rextio-torch"] = "0.1.3"
        case["packages"] = packages
    ready = (ROOT / TARGET_CONFIG_PATH).read_text(encoding="utf-8")
    pins = integration_target_pins(parse_integration_targets(ready))
    report["policy"] = {
        "policy_id": TARGET_POLICY_ID,
        "policy_version": 1,
        "status": "pre-measurement",
        "candidate_packages": pins,
    }
    report["package_provenance"] = {
        name: {
            "version": pin["version"],
            "url": pin["git_url"],
            "vcs": "git",
            "commit_id": pin["rev"],
        }
        for name, pin in pins.items()
    }
    blocks = generate_blocks(
        report,
        report_logical_path="results/canonical/cohort/report.json",
        measurement_commit="a" * 40,
        evidence_commit="b" * 40,
        github_url="https://github.com/rextio/rextio-benchmark",
    )
    for block in blocks.values():
        assert "rextio 0.1.7 candidate@b8b8ed11f6b7" in block
        assert "rextio-numpy 0.1.3 candidate@cf461e677578" in block
        assert "rextio-torch 0.1.3 candidate@1e92b24b154c" in block
        assert "rextio-tensorflow 0.1.3 candidate@1fdb2e1cd91d" in block
        assert "Core 0.1.7" in block
        assert "rextio-torch 0.1.3" in block


def test_readme_fails_for_candidate_versions_without_binding() -> None:
    report = _minimal_report(with_binding=False)
    with pytest.raises(GateError, match="require bound policy"):
        generate_blocks(
            report,
            report_logical_path="results/canonical/cohort/report.json",
            measurement_commit="a" * 40,
            evidence_commit="b" * 40,
            github_url="https://github.com/rextio/rextio-benchmark",
        )


def test_readme_rejects_cross_case_candidate_plugin_version_conflict() -> None:
    """Last-wins display must not hide conflicting rextio-numpy across cases."""
    report = _minimal_report(with_binding=True)
    for case in report["cases"]:
        if case["id"] == "numpy-mixed-fusion":
            case["packages"] = {**case["packages"], "rextio-numpy": "0.1.3"}
        elif "rextio-numpy" in case["packages"]:
            case["packages"] = {**case["packages"], "rextio-numpy": "0.1.2"}
    with pytest.raises(GateError, match="package version conflict for rextio-numpy"):
        generate_blocks(
            report,
            report_logical_path="results/canonical/cohort/report.json",
            measurement_commit="a" * 40,
            evidence_commit="b" * 40,
            github_url="https://github.com/rextio/rextio-benchmark",
        )


def test_readme_fails_for_tampered_binding() -> None:
    report = _minimal_report(with_binding=True)
    report["package_provenance"]["rextio-numpy"]["commit_id"] = "0" * 40
    with pytest.raises(GateError, match="commit"):
        generate_blocks(
            report,
            report_logical_path="results/canonical/cohort/report.json",
            measurement_commit="a" * 40,
            evidence_commit="b" * 40,
            github_url="https://github.com/rextio/rextio-benchmark",
        )


def test_readme_rejects_released_versions_plus_candidate_policy() -> None:
    """Downgraded package versions with leftover candidate policy fail closed."""
    report = _minimal_report(with_binding=True)
    for case in report["cases"]:
        packages = dict(case["packages"])
        if packages.get("rextio-numpy") == "0.1.3":
            packages["rextio-numpy"] = "0.1.2"
        if packages.get("rextio-tensorflow") == "0.1.3":
            packages["rextio-tensorflow"] = "0.1.2"
        case["packages"] = packages
    with pytest.raises(GateError, match="full frozen candidate plugin set"):
        generate_blocks(
            report,
            report_logical_path="results/canonical/cohort/report.json",
            measurement_commit="a" * 40,
            evidence_commit="b" * 40,
            github_url="https://github.com/rextio/rextio-benchmark",
        )


def test_readme_rejects_partial_candidate_set_mismatch() -> None:
    report = _minimal_report(with_binding=True)
    # Drop tensorflow from packages while policy still binds both pins.
    for case in report["cases"]:
        packages = dict(case["packages"])
        packages.pop("rextio-tensorflow", None)
        case["packages"] = packages
    with pytest.raises(GateError, match="full frozen candidate plugin set"):
        generate_blocks(
            report,
            report_logical_path="results/canonical/cohort/report.json",
            measurement_commit="a" * 40,
            evidence_commit="b" * 40,
            github_url="https://github.com/rextio/rextio-benchmark",
        )


def test_readme_and_verify_reject_downgrade_or_omitted_candidate_subset() -> None:
    """Publishable/canonical non-released reports cannot omit or downgrade either pin."""
    # Full downgrade of both candidate packages, no binding.
    downgraded = _minimal_report(with_binding=False)
    for case in downgraded["cases"]:
        packages = dict(case["packages"])
        if packages.get("rextio-numpy") == "0.1.3":
            packages["rextio-numpy"] = "0.1.2"
        if packages.get("rextio-tensorflow") == "0.1.3":
            packages["rextio-tensorflow"] = "0.1.2"
        case["packages"] = packages
    with pytest.raises(GateError, match="full frozen candidate plugin set"):
        _verify_candidate_policy_and_provenance(downgraded, ROOT)
    with pytest.raises(GateError, match="full frozen candidate plugin set"):
        generate_blocks(
            downgraded,
            report_logical_path="results/canonical/cohort/report.json",
            measurement_commit="a" * 40,
            evidence_commit="b" * 40,
            github_url="https://github.com/rextio/rextio-benchmark",
        )

    # Omit tensorflow only (subset spoof) with binding stripped.
    omit_tf = _minimal_report(with_binding=False)
    for case in omit_tf["cases"]:
        packages = dict(case["packages"])
        packages.pop("rextio-tensorflow", None)
        case["packages"] = packages
    with pytest.raises(GateError, match="full frozen candidate plugin set"):
        _verify_candidate_policy_and_provenance(omit_tf, ROOT)
    with pytest.raises(GateError, match="full frozen candidate plugin set"):
        generate_blocks(
            omit_tf,
            report_logical_path="results/canonical/cohort/report.json",
            measurement_commit="a" * 40,
            evidence_commit="b" * 40,
            github_url="https://github.com/rextio/rextio-benchmark",
        )

    # Partial binding removed after full versions: delete package_provenance for one pin.
    partial_binding = _minimal_report(with_binding=True)
    del partial_binding["package_provenance"]["rextio-tensorflow"]
    del partial_binding["policy"]["candidate_plugins"]["rextio-tensorflow"]
    with pytest.raises(GateError, match="full frozen candidate"):
        _verify_candidate_policy_and_provenance(partial_binding, ROOT)


def test_authentic_released_frozen_readme_has_no_candidate_labels() -> None:
    real = json.loads(
        (ROOT / RELEASED_CANONICAL_COHORT_DIR / "report.json").read_text(encoding="utf-8")
    )
    blocks = generate_blocks(
        real,
        report_logical_path=f"{RELEASED_CANONICAL_COHORT_DIR}/report.json",
        measurement_commit=real["repository"]["commit"],
        evidence_commit=FROZEN_CANONICAL_COHORTS[RELEASED_COHORT_ID]["evidence_commit"],
        github_url="https://github.com/rextio/rextio-benchmark",
    )
    assert "candidate@" not in blocks["README.md"]
    assert "0.1.3" not in blocks["README.md"] or "rextio-numpy 0.1.2" in blocks["README.md"]
    assert is_released_frozen_report(real) is True
    _verify_candidate_policy_and_provenance(real, ROOT)


def test_quick_non_publishable_may_omit_candidate_binding() -> None:
    report = {
        "mode": "quick",
        "publishable": False,
        "repository": {"commit": "a" * 40, "dirty": True},
        "cases": [
            {
                "id": "numpy-mixed-fusion",
                "packages": {"rextio": "0.1.6", "rextio-numpy": "0.1.2"},
            }
        ],
    }
    _verify_candidate_policy_and_provenance(report, ROOT)


def test_bundled_semantic_replay_uses_resolved_paths_not_live(
    tmp_path: Path,
) -> None:
    """Correct bundled check/source pass; tampered bundle fails even if live matches."""
    case = BenchmarkCase(
        benchmark_id="numpy-mixed-fusion",
        project="numpy",
        profile="base",
        project_root=tmp_path / "cases/numpy",
        adapter_path=tmp_path / "cases/numpy/benchmark_case.py",
        kind="python-module",
        module="numpy_case.workload",
        function="mixed_fusion",
        qualname="numpy_case.workload.mixed_fusion",
        expected_route="native-plugin:rextio-numpy",
        tolerance={"absolute": 0.0, "relative": 0.0},
        raw={
            "generated_expectations": {
                "plugin_rules": [
                    {
                        "rule_id": "rextio-numpy/elementwise-chain-fusion",
                        "operand_mode": "leaves",
                    }
                ],
                "generated_rust_source_substrings": ["__rxtnp_echain_"],
            }
        },
    )
    good_check = {
        "modules": [
            {
                "functions": [
                    {
                        "qualname": "numpy_case.workload.mixed_fusion",
                        "route": "native-plugin:rextio-numpy",
                        "native_status": "accepted",
                        "plugin_claims": [
                            {
                                "rule_id": "rextio-numpy/elementwise-chain-fusion",
                                "operand_mode": "leaves",
                            }
                        ],
                    }
                ]
            }
        ]
    }
    bundle_check = tmp_path / "objects/check.json"
    bundle_rust = tmp_path / "objects/lib.rs"
    bundle_check.parent.mkdir(parents=True)
    bundle_check.write_text(json.dumps(good_check), encoding="utf-8")
    bundle_rust.write_text("fn x() { __rxtnp_echain_demo(); }\n", encoding="utf-8")

    # Live files are correct too — replay must still use resolved (bundled) paths.
    live_check = tmp_path / "cases/numpy/.rextio/reports/portable/check.json"
    live_rust = tmp_path / "cases/numpy/.rextio/generated/rust/src/lib.rs"
    live_check.parent.mkdir(parents=True)
    live_rust.parent.mkdir(parents=True)
    live_check.write_text(json.dumps(good_check), encoding="utf-8")
    live_rust.write_text("fn x() { __rxtnp_echain_demo(); }\n", encoding="utf-8")

    _replay_generated_expectations(
        case,
        {
            "check_report": bundle_check,
            "generated_rust_source": bundle_rust,
        },
    )

    # Tampered bundled check fails even when live still has the correct rule.
    bad_check = deepcopy(good_check)
    bad_check["modules"][0]["functions"][0]["plugin_claims"] = []
    bundle_check.write_text(json.dumps(bad_check), encoding="utf-8")
    with pytest.raises(GateError, match="missing required plugin rule"):
        _replay_generated_expectations(
            case,
            {
                "check_report": bundle_check,
                "generated_rust_source": bundle_rust,
            },
        )

    # Missing helper in bundled rust fails even if live has it.
    bundle_check.write_text(json.dumps(good_check), encoding="utf-8")
    bundle_rust.write_text("fn x() { /* no helper */ }\n", encoding="utf-8")
    with pytest.raises(GateError, match="generated Rust source lacks"):
        _replay_generated_expectations(
            case,
            {
                "check_report": bundle_check,
                "generated_rust_source": bundle_rust,
            },
        )


def test_installed_base_profile_numpy_provenance_when_present() -> None:
    """If the base profile has candidate numpy installed, capture exact rev."""
    direct = (
        ROOT
        / "profiles/base/.venv/lib/python3.11/site-packages"
        / "rextio_numpy-0.1.3.dist-info"
        / "direct_url.json"
    )
    if not direct.is_file():
        pytest.skip("candidate rextio-numpy not installed in base profile")
    # Import against the profile is not guaranteed in the test interpreter; read file.
    document = json.loads(direct.read_text(encoding="utf-8"))
    assert document["url"].rstrip("/") == NUMPY_PIN["git_url"]
    assert document["vcs_info"]["commit_id"] == NUMPY_PIN["rev"]


def test_candidate_plugins_in_versions_is_version_scoped() -> None:
    assert candidate_plugins_in_versions({"rextio-numpy": "0.1.2"}) == {}
    assert set(candidate_plugins_in_versions({"rextio-numpy": "0.1.3"})) == {"rextio-numpy"}


def test_bound_pins_empty_without_policy() -> None:
    assert bound_candidate_pins_from_report({}) == {}
