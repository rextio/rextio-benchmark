import torch.nn.functional as F
from rextio_torch.types import TensorF32Cpu1D, TensorF32Cpu2D, TensorI64Cpu1D


def small_batch_prepost(
    x: TensorF32Cpu2D,
    mean: TensorF32Cpu1D,
    scale: TensorF32Cpu1D,
    hidden_weight: TensorF32Cpu2D,
    hidden_bias: TensorF32Cpu1D,
    class_weight: TensorF32Cpu2D,
    class_bias: TensorF32Cpu1D,
    rounds: int,
    phase: int,
) -> TensorI64Cpu1D:
    centered = x - mean
    normalized = centered / scale
    hidden = F.linear(normalized, hidden_weight, hidden_bias)
    for layer in range(rounds):
        if (layer + phase) % 2 == 0:
            hidden = hidden.relu()
        else:
            hidden = hidden.tanh()
    logits = F.linear(hidden, class_weight, class_bias)
    probabilities = logits.softmax(dim=1)
    return probabilities.argmax(dim=1, keepdim=False)


def inference(
    x: TensorF32Cpu2D,
    weight: TensorF32Cpu2D,
    bias: TensorF32Cpu1D,
    depth: int,
    phase: int,
) -> TensorF32Cpu1D:
    hidden = x
    for layer in range(depth):
        if (layer + phase) % 2 == 0:
            even = hidden @ weight + bias
            hidden = even.relu()
        else:
            odd = hidden @ weight + bias
            hidden = odd.sigmoid()
    return hidden.mean(dim=1, keepdim=False)
