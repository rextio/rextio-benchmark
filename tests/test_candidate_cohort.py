from __future__ import annotations

import importlib.util
from pathlib import Path

from rextio_benchmark.cohort import (
    CANDIDATE_COHORT_POLICY,
    CANDIDATE_PLUGIN_013_COMPLETE_CASE_IDS,
    CANDIDATE_PLUGIN_PINS,
    FROZEN_CANONICAL_COHORTS,
    HEADLINE_CASE_IDS,
    RELEASED_CANONICAL_COHORT_DIR,
    RELEASED_CANONICAL_COHORT_FILE_COUNT,
    RELEASED_CANONICAL_COHORT_TREE_SHA256,
    RELEASED_CPU_COMPLETE_CASE_IDS,
    expected_complete_case_ids,
    tree_fingerprint,
)
from rextio_benchmark.models import load_cases
from rextio_benchmark.readme_blocks import HEADLINE_ROWS

ROOT = Path(__file__).resolve().parents[1]
RELEASED_COHORT_ID = "15fa2645c757b4a23541587f7d0757107952f7c6ade3386bcaacdbdd9cce12d8"
RELEASED_MEASUREMENT_COMMIT = "ff7f4fea34199d850bed0446a8a223ef730ddf17"


def test_candidate_policy_is_pre_measurement_and_complete() -> None:
    assert CANDIDATE_COHORT_POLICY["status"] == "pre-measurement"
    assert CANDIDATE_COHORT_POLICY["policy_version"] == 1
    assert set(CANDIDATE_COHORT_POLICY["complete_case_ids"]) == (
        CANDIDATE_PLUGIN_013_COMPLETE_CASE_IDS
    )
    # Ordered equality: policy list must match HEADLINE_ROWS order exactly.
    assert CANDIDATE_COHORT_POLICY["headline_case_ids"] == [case_id for _, case_id in HEADLINE_ROWS]
    assert set(CANDIDATE_COHORT_POLICY["headline_case_ids"]) == HEADLINE_CASE_IDS
    assert "numpy-mixed-nonfused-phase1" in CANDIDATE_PLUGIN_013_COMPLETE_CASE_IDS
    assert "numpy-mixed-nonfused-phase1" not in HEADLINE_CASE_IDS
    assert {case_id for _, case_id in HEADLINE_ROWS} == HEADLINE_CASE_IDS
    assert load_cases(ROOT)
    assert {case.benchmark_id for case in load_cases(ROOT)} == (
        CANDIDATE_PLUGIN_013_COMPLETE_CASE_IDS
    )


def test_candidate_plugin_pins_are_exact_git_revisions() -> None:
    assert CANDIDATE_PLUGIN_PINS["rextio-numpy"] == {
        "version": "0.1.3",
        "git_url": "https://github.com/rextio/rextio-numpy",
        "rev": "7316c47393a86f1c701049b878d01e8d8f561cdb",
    }
    assert CANDIDATE_PLUGIN_PINS["rextio-tensorflow"] == {
        "version": "0.1.3",
        "git_url": "https://github.com/rextio/rextio-tensorflow",
        "rev": "346ca58148ed2563d4c7547dd8443d60cd4f905b",
    }
    base = (ROOT / "profiles/base/pyproject.toml").read_text(encoding="utf-8")
    assert "7316c47393a86f1c701049b878d01e8d8f561cdb" in base
    assert "rextio-numpy==0.1.3" in base
    for profile in ("tensorflow-cpu", "tensorflow-cuda"):
        text = (ROOT / "profiles" / profile / "pyproject.toml").read_text(encoding="utf-8")
        assert "346ca58148ed2563d4c7547dd8443d60cd4f905b" in text
        assert "rextio-tensorflow==0.1.3" in text


def test_historical_cohort_keeps_released_complete_case_set() -> None:
    report = {
        "canonical_bundle": {
            "cohort_id": RELEASED_COHORT_ID,
        }
    }
    expected = expected_complete_case_ids(
        report,
        current_case_ids=CANDIDATE_PLUGIN_013_COMPLETE_CASE_IDS,
    )
    assert expected == RELEASED_CPU_COMPLETE_CASE_IDS
    assert "numpy-mixed-nonfused-phase1" not in expected

    # Raw three-run reports (no canonical_bundle) still map via measurement_commit.
    raw_report = {
        "repository": {
            "commit": RELEASED_MEASUREMENT_COMMIT,
        }
    }
    raw_expected = expected_complete_case_ids(
        raw_report,
        current_case_ids=CANDIDATE_PLUGIN_013_COMPLETE_CASE_IDS,
    )
    assert raw_expected == RELEASED_CPU_COMPLETE_CASE_IDS
    assert "numpy-mixed-nonfused-phase1" not in raw_expected

    # Unknown / current commit is fail-closed onto the live 9-case set.
    live = expected_complete_case_ids(
        {},
        current_case_ids=CANDIDATE_PLUGIN_013_COMPLETE_CASE_IDS,
    )
    assert live == CANDIDATE_PLUGIN_013_COMPLETE_CASE_IDS
    assert "numpy-mixed-nonfused-phase1" in live
    unknown_commit = expected_complete_case_ids(
        {"repository": {"commit": "0" * 40}},
        current_case_ids=CANDIDATE_PLUGIN_013_COMPLETE_CASE_IDS,
    )
    assert unknown_commit == CANDIDATE_PLUGIN_013_COMPLETE_CASE_IDS
    # Prefix / partial commits must not unlock the frozen set.
    partial = expected_complete_case_ids(
        {"repository": {"commit": RELEASED_MEASUREMENT_COMMIT[:12]}},
        current_case_ids=CANDIDATE_PLUGIN_013_COMPLETE_CASE_IDS,
    )
    assert partial == CANDIDATE_PLUGIN_013_COMPLETE_CASE_IDS

    frozen = FROZEN_CANONICAL_COHORTS[RELEASED_COHORT_ID]
    assert frozen["measurement_commit"] == RELEASED_MEASUREMENT_COMMIT


def test_released_canonical_cohort_directory_is_byte_immutable() -> None:
    cohort_root = ROOT / RELEASED_CANONICAL_COHORT_DIR
    digest, count = tree_fingerprint(cohort_root)
    assert count == RELEASED_CANONICAL_COHORT_FILE_COUNT
    assert digest == RELEASED_CANONICAL_COHORT_TREE_SHA256


def test_numpy_headline_uses_phase0_and_phase1_is_diagnostic() -> None:
    adapter_path = ROOT / "cases/numpy/benchmark_case.py"
    spec = importlib.util.spec_from_file_location("_numpy_case_adapter", adapter_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fused = module.make_arguments("numpy-mixed-fusion")
    phase1 = module.make_arguments("numpy-mixed-nonfused-phase1")
    assert fused[2] == 0
    assert phase1[2] == 1
    assert fused[0].shape == phase1[0].shape == (100_000,)


def test_tensorflow_arguments_use_non_square_weight_for_transpose() -> None:
    adapter_path = ROOT / "cases/tensorflow-cpu/benchmark_case.py"
    # Avoid importing real TensorFlow in unit tests: load source and inspect shapes
    # from the checked-in adapter text contract.
    text = adapter_path.read_text(encoding="utf-8")
    assert "(512, 96)" in text
    assert "(80, 96)" in text
    assert "tf.linspace(-0.1, 0.1, 80)" in text
    workload = (ROOT / "cases/tensorflow-cpu/src/tensorflow_case/workload.py").read_text(
        encoding="utf-8"
    )
    assert "tf.transpose(weight)" in workload
    assert "tf.matmul(x, transposed)" in workload
