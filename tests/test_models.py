from pathlib import Path

from rextio_benchmark.models import load_cases, paired_orders

ROOT = Path(__file__).resolve().parents[1]


def test_lane_orders_are_counterbalanced() -> None:
    assert paired_orders(4) == [
        ("python-source", "rextio-native"),
        ("rextio-native", "python-source"),
        ("python-source", "rextio-native"),
        ("rextio-native", "python-source"),
    ]


def test_required_case_set_is_present() -> None:
    identifiers = {case.benchmark_id for case in load_cases(ROOT)}
    assert identifiers == {
        "core-hybrid",
        "core-native-executable",
        "numpy-mixed-fusion",
        "numpy-mixed-nonfused-phase1",
        "numpy-blas-dot-negative-control",
        "numpy-f64-1d-boundary-direct-sink",
        "networkx-dijkstra",
        "pandas-series-map",
        "torch-cpu-deep-mlp",
        "torch-cpu-small-batch-prepost",
        "tensorflow-cpu-eager-chain",
        "tensorflow-cpu-small-batch-prepost",
    }


def test_framework_profiles_are_isolated() -> None:
    cases = {case.benchmark_id: case for case in load_cases(ROOT)}
    assert cases["torch-cpu-deep-mlp"].profile == "torch-cpu"
    assert cases["tensorflow-cpu-eager-chain"].profile == "tensorflow-cpu"
    assert cases["core-hybrid"].profile == "base"
