import torch

from rextio_benchmark.canonical import sequence


def make_arguments(benchmark_id: str) -> tuple[object, ...]:
    if benchmark_id == "torch-cpu-small-batch-prepost":
        feature_width = 32
        class_count = 8
        x = torch.arange(feature_width, dtype=torch.float32).reshape(1, feature_width)
        x = x * 0.01 - 0.15
        mean = torch.arange(feature_width, dtype=torch.float32) * 0.001 - 0.01
        scale = 0.75 + torch.arange(feature_width, dtype=torch.float32) * 0.005
        hidden_weight = torch.arange(
            feature_width * feature_width, dtype=torch.float32
        ).reshape(feature_width, feature_width)
        hidden_weight = hidden_weight * 0.002 - 0.05
        hidden_bias = torch.arange(feature_width, dtype=torch.float32) * 0.003
        class_weight = torch.arange(
            class_count * feature_width, dtype=torch.float32
        ).reshape(class_count, feature_width)
        class_weight = class_weight * 0.004 - 0.08
        class_bias = torch.arange(class_count, dtype=torch.float32) * 0.01 - 0.03
        return (
            x,
            mean,
            scale,
            hidden_weight,
            hidden_bias,
            class_weight,
            class_bias,
            4,
            0,
        )
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
