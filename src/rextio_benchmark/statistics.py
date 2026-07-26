from __future__ import annotations

import math
import random
import statistics
from collections.abc import Sequence


def percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        raise ValueError("at least one value is required")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be between zero and one")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


def summarize(samples_ns: Sequence[float]) -> dict[str, float | int]:
    if not samples_ns:
        raise ValueError("at least one sample is required")
    median = statistics.median(samples_ns)
    deviations = [abs(sample - median) for sample in samples_ns]
    return {
        "count": len(samples_ns),
        "median_ns": float(median),
        "mean_ns": float(statistics.fmean(samples_ns)),
        "mad_ns": float(statistics.median(deviations)),
        "p95_ns": percentile(samples_ns, 0.95),
    }


def paired_speedups(source_ns: Sequence[float], native_ns: Sequence[float]) -> list[float]:
    if len(source_ns) != len(native_ns) or not source_ns:
        raise ValueError("paired samples must have equal non-zero lengths")
    if any(value <= 0 for value in native_ns):
        raise ValueError("native samples must be positive")
    return [source / native for source, native in zip(source_ns, native_ns, strict=True)]


def paired_bootstrap_interval(
    source_ns: Sequence[float],
    native_ns: Sequence[float],
    *,
    resamples: int = 10_000,
    seed: int = 20260726,
) -> tuple[float, float]:
    ratios = paired_speedups(source_ns, native_ns)
    if resamples < 100:
        raise ValueError("resamples must be at least 100")
    rng = random.Random(seed)
    estimates = []
    for _ in range(resamples):
        sample = [ratios[rng.randrange(len(ratios))] for _ in ratios]
        estimates.append(statistics.median(sample))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)

