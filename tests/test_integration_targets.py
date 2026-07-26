from pathlib import Path

import pytest

from rextio_benchmark.integration_targets import (
    NEXT_DIAGNOSTIC_CASE_IDS,
    TARGET_POLICY_ID,
    cases_require_integration_targets,
    integration_policy_binding,
    integration_target_blockers,
    load_integration_targets,
)
from rextio_benchmark.verification import GateError

ROOT = Path(__file__).resolve().parents[1]


def test_next_candidate_targets_pin_final_core_and_tensorflow_merges() -> None:
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


def test_unavailable_numpy_and_torch_merges_fail_closed() -> None:
    targets = {target.name: target for target in load_integration_targets(ROOT)}
    assert targets["rextio-numpy"].rev == "PENDING_INTEGRATION_SHA"
    assert targets["rextio-torch"].rev == "PENDING_INTEGRATION_SHA"
    blockers = integration_target_blockers(ROOT)
    assert "rextio-numpy: pending full integration SHA" in blockers
    assert "rextio-torch: pending full integration SHA" in blockers
    with pytest.raises(GateError, match="blocked"):
        integration_policy_binding(ROOT)


def test_only_new_diagnostics_activate_the_next_target_gate() -> None:
    assert cases_require_integration_targets(NEXT_DIAGNOSTIC_CASE_IDS)
    assert not cases_require_integration_targets(
        frozenset({"numpy-mixed-fusion", "torch-cpu-deep-mlp"})
    )
    assert TARGET_POLICY_ID == "candidate-boundary-prepost-0.1.1"
