import torch

from rextio_benchmark.canonical import sequence


def make_arguments(_benchmark_id: str) -> tuple[object, ...]:
    torch.manual_seed(20260726)
    x = torch.randn((512, 96), dtype=torch.float32)
    weight = torch.randn((96, 96), dtype=torch.float32) * 0.04
    bias = torch.linspace(-0.1, 0.1, 96, dtype=torch.float32)
    return x, weight, bias, 12, 1


def normalize(_benchmark_id: str, value: object) -> object:
    if not isinstance(value, torch.Tensor):
        raise TypeError(f"expected Tensor, got {type(value).__name__}")
    detached = value.detach().cpu()
    return sequence(
        kind="tensor",
        shape=tuple(detached.shape),
        dtype=str(detached.dtype),
        values=detached.reshape(-1).tolist(),
    )
