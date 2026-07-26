from rextio_numpy.types import F64Arr1

import numpy as np


def boundary_direct_sink(values: F64Arr1) -> F64Arr1:
    return values + 0.25


def mixed_fusion(
    left: F64Arr1,
    right: F64Arr1,
    phase: int,
) -> F64Arr1:
    if phase % 2 == 0:
        return (left + right) * (left - right)
    return (left - right) / (right + 2.0)


def blas_dot(left: F64Arr1, right: F64Arr1) -> float:
    return np.dot(left, right)
