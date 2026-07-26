import math

import pytest

from rextio_benchmark.statistics import (
    paired_bootstrap_interval,
    paired_speedups,
    percentile,
    summarize,
)


def test_summary_is_deterministic() -> None:
    summary = summarize([10.0, 20.0, 30.0, 40.0])
    assert summary == {
        "count": 4,
        "median_ns": 25.0,
        "mean_ns": 25.0,
        "mad_ns": 10.0,
        "p95_ns": 38.5,
    }
    assert percentile([1.0, 2.0, 3.0], 0.5) == 2.0


def test_paired_bootstrap_is_seeded_and_keeps_slower_results() -> None:
    source = [10.0, 12.0, 14.0, 16.0]
    native = [20.0, 24.0, 28.0, 32.0]
    assert paired_speedups(source, native) == [0.5, 0.5, 0.5, 0.5]
    first = paired_bootstrap_interval(source, native, resamples=500)
    second = paired_bootstrap_interval(source, native, resamples=500)
    assert first == second == (0.5, 0.5)
    assert math.isfinite(first[0])


def test_paired_inputs_must_match() -> None:
    with pytest.raises(ValueError, match="equal"):
        paired_speedups([1.0], [1.0, 2.0])

