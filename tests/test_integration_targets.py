import hashlib
from pathlib import Path

import pytest

from rextio_benchmark.cohort import validate_cohort
from rextio_benchmark.integration_targets import (
    NEXT_DIAGNOSTIC_CASE_IDS,
    TARGET_CONFIG_PATH,
    TARGET_POLICY_ID,
    cases_require_integration_targets,
    integration_policy_binding,
    integration_target_blockers,
    integration_target_pins,
    load_integration_targets,
    parse_integration_targets,
)
from rextio_benchmark.models import load_cases
from rextio_benchmark.verification import GateError
from rextio_benchmark.verifier import _verify_next_integration_policy_and_provenance

ROOT = Path(__file__).resolve().parents[1]


def test_next_candidate_targets_pin_final_integration_merges() -> None:
    targets = {target.name: target for target in load_integration_targets(ROOT)}
    assert targets["rextio"].pin() == {
        "version": "0.1.7",
        "git_url": "https://github.com/rextio/rextio",
        "rev": "b8b8ed11f6b7b7aae4c7ae5205d88529608e8e97",
    }
    assert targets["rextio-tensorflow"].pin() == {
        "version": "0.1.3",
        "git_url": "https://github.com/rextio/rextio-tensorflow",
        "rev": "1fdb2e1cd91d058a056db76c2e0a15d52c855053",
    }
    assert targets["rextio-numpy"].pin() == {
        "version": "0.1.3",
        "git_url": "https://github.com/rextio/rextio-numpy",
        "rev": "cf461e6775780a598517980c555a1aec079285d8",
    }
    assert targets["rextio-torch"].pin() == {
        "version": "0.1.3",
        "git_url": "https://github.com/rextio/rextio-torch",
        "rev": "1e92b24b154c7266dc37d19533fc3e17a8b05f9a",
    }


def test_final_targets_and_profiles_are_ready() -> None:
    targets = {target.name: target for target in load_integration_targets(ROOT)}
    assert targets["rextio-numpy"].rev == "cf461e6775780a598517980c555a1aec079285d8"
    assert targets["rextio-torch"].rev == "1e92b24b154c7266dc37d19533fc3e17a8b05f9a"
    assert integration_target_blockers(ROOT) == []
    binding = integration_policy_binding(ROOT)
    assert binding["status"] == "pre-measurement"
    assert binding["candidate_packages"] == integration_target_pins(tuple(targets.values()))


def test_only_new_diagnostics_activate_the_next_target_gate() -> None:
    assert cases_require_integration_targets(NEXT_DIAGNOSTIC_CASE_IDS)
    assert not cases_require_integration_targets(
        frozenset({"numpy-mixed-fusion", "torch-cpu-deep-mlp"})
    )
    assert TARGET_POLICY_ID == "candidate-boundary-prepost-0.1.1"


def test_next_policy_verifier_requires_run_commit_config_and_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ready_config = (ROOT / TARGET_CONFIG_PATH).read_text(encoding="utf-8")
    targets = parse_integration_targets(ready_config)
    pins = integration_target_pins(targets)
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
    blobs: dict[str, bytes] = {
        TARGET_CONFIG_PATH.as_posix(): ready_config.encode(),
        "src/rextio_benchmark/integration_targets.py": b"integration harness",
    }
    for profile in ("base", "torch-cpu", "tensorflow-cpu"):
        selected = [target for target in targets if profile in target.profiles]
        manifest = (
            "[project]\ndependencies = [\n"
            + "".join(f'  "{target.name}=={target.version}",\n' for target in selected)
            + "]\n[tool.uv.sources]\n"
            + "".join(
                f'{target.name} = {{ git = "{target.git_url}", rev = "{target.rev}" }}\n'
                for target in selected
            )
        )
        lock = "version = 1\n" + "".join(
            "[[package]]\n"
            f'name = "{target.name}"\n'
            f'version = "{target.version}"\n'
            f'source = {{ git = "{target.git_url}?rev={target.rev}#{target.rev}" }}\n'
            for target in selected
        )
        blobs[f"profiles/{profile}/pyproject.toml"] = manifest.encode()
        blobs[f"profiles/{profile}/uv.lock"] = lock.encode()

    def record(path: str) -> dict[str, str]:
        return {
            "kind": "run-input",
            "path": path,
            "sha256": hashlib.sha256(blobs[path]).hexdigest(),
        }

    known = {case.benchmark_id: case for case in load_cases(ROOT)}
    cases = []
    for case in known.values():
        packages = {"rextio": "0.1.7"}
        if case.profile == "base":
            packages["rextio-numpy"] = "0.1.3"
        elif case.profile == "torch-cpu":
            packages["rextio-torch"] = "0.1.3"
        elif case.profile == "tensorflow-cpu":
            packages["rextio-tensorflow"] = "0.1.3"
        cases.append(
            {
                "id": case.benchmark_id,
                "packages": packages,
                "gate": {
                    "evidence": {
                        "integration_target_config": record(TARGET_CONFIG_PATH.as_posix()),
                        "harness_integration_targets": record(
                            "src/rextio_benchmark/integration_targets.py"
                        ),
                        "profile_manifest": record(f"profiles/{case.profile}/pyproject.toml"),
                        "profile_lock": record(f"profiles/{case.profile}/uv.lock"),
                    }
                },
            }
        )
    report = {
        "repository": {"commit": "a" * 40},
        "policy": {
            "policy_id": TARGET_POLICY_ID,
            "policy_version": 1,
            "status": "pre-measurement",
            "candidate_packages": pins,
        },
        "package_provenance": provenance,
        "cases": cases,
    }
    monkeypatch.setattr(
        "rextio_benchmark.verifier._git_blob",
        lambda _root, _commit, path: blobs.get(path),
    )
    _verify_next_integration_policy_and_provenance(report, ROOT, known)

    del cases[0]["gate"]["evidence"]["integration_target_config"]
    with pytest.raises(GateError, match="integration_target_config"):
        _verify_next_integration_policy_and_provenance(report, ROOT, known)


def test_next_policy_and_provenance_are_frozen_into_cohort_summary() -> None:
    ready_config = (ROOT / TARGET_CONFIG_PATH).read_text(encoding="utf-8")
    pins = integration_target_pins(parse_integration_targets(ready_config))
    provenance = {
        name: {
            "version": pin["version"],
            "url": pin["git_url"],
            "vcs": "git",
            "commit_id": pin["rev"],
        }
        for name, pin in pins.items()
    }
    policy = {
        "policy_id": TARGET_POLICY_ID,
        "policy_version": 1,
        "status": "pre-measurement",
        "candidate_packages": pins,
    }
    reports = []
    for index in range(3):
        reports.append(
            {
                "generated_at": f"2026-07-27T00:0{index}:00+00:00",
                "mode": "publish",
                "publishable": True,
                "repository": {"commit": "a" * 40},
                "system": {"toolchain": {}},
                "configuration": {"pairs": 10},
                "policy": policy,
                "package_provenance": provenance,
                "cases": [
                    {
                        "id": "core-hybrid",
                        "eligible": True,
                        "blockers": [],
                        "packages": {"rextio": "0.1.7"},
                        "gate": {"evidence": {}},
                        "paired": {"median_speedup": 1.0},
                    }
                ],
            }
        )
    summary = validate_cohort(reports)
    assert summary["policy_id"] == TARGET_POLICY_ID
    assert summary["candidate_packages"] == pins
    assert summary["package_provenance"] == provenance
