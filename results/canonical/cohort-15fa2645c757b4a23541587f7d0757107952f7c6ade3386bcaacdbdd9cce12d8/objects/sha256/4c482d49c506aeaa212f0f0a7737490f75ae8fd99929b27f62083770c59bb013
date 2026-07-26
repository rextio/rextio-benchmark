from rextio_torch.types import TensorF32Cpu1D, TensorF32Cpu2D


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

