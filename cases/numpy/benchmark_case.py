import numpy as np
from rextio_benchmark.canonical import sequence


def make_arguments(benchmark_id: str) -> tuple[object, ...]:
    if benchmark_id == "numpy-f64-1d-boundary-direct-sink":
        values = np.linspace(-2.0, 2.0, 4_096, dtype=np.float64)
        values.flags.writeable = False
        return (values,)
    if benchmark_id == "numpy-mixed-fusion":
        # phase=0 selects the fused expression (left + right) * (left - right).
        left = np.linspace(0.01, 0.15, 100_000, dtype=np.float64)
        right = np.linspace(0.001, 0.01, 100_000, dtype=np.float64)
        return left, right, 0
    if benchmark_id == "numpy-mixed-nonfused-phase1":
        # phase=1 selects the non-fused diagnostic (left - right) / (right + 2.0).
        left = np.linspace(0.01, 0.15, 100_000, dtype=np.float64)
        right = np.linspace(0.001, 0.01, 100_000, dtype=np.float64)
        return left, right, 1
    left = np.linspace(-1.0, 1.0, 2_000_000, dtype=np.float64)
    right = np.linspace(1.0, -1.0, 2_000_000, dtype=np.float64)
    return left, right


def normalize(_benchmark_id: str, value: object) -> object:
    if isinstance(value, np.ndarray):
        return sequence(
            kind="ndarray",
            shape=value.shape,
            dtype=str(value.dtype),
            values=value.reshape(-1).tolist(),
        )
    return float(value)
