import numpy as np
import pandas as pd
from rextio_benchmark.canonical import exact_sequence


def make_arguments(_benchmark_id: str) -> tuple[object, ...]:
    values = np.linspace(-3.0, 3.0, 1_000_000, dtype=np.float64)
    return (pd.Series(values, dtype="float64"),)


def normalize(_benchmark_id: str, value: object) -> object:
    if not isinstance(value, pd.Series):
        raise TypeError(f"expected Series, got {type(value).__name__}")
    array = value.to_numpy()
    return exact_sequence(
        kind="series",
        shape=array.shape,
        dtype=str(array.dtype),
        values=array.reshape(-1).tolist(),
    )
