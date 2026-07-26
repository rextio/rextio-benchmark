import tensorflow as tf
from rextio_tensorflow.types import TensorF32Cpu1D, TensorF32Cpu2D, TensorI64Cpu1D


def inference(
    x: TensorF32Cpu2D,
    weight: TensorF32Cpu2D,
    bias: TensorF32Cpu1D,
    depth: int,
    phase: int,
) -> TensorI64Cpu1D:
    # Default rank-2 transpose on a non-square weight (out, in) -> (in, out).
    transposed = tf.transpose(weight)
    hidden = tf.matmul(x, transposed)
    hidden = tf.nn.relu(hidden)
    for layer in range(depth):
        if (layer + phase) % 2 == 0:
            hidden = tf.nn.sigmoid(hidden)
        else:
            hidden = tf.nn.relu(hidden)
        hidden = tf.nn.tanh(hidden)
    probabilities = tf.nn.softmax(hidden + bias, axis=1)
    return tf.argmax(probabilities, axis=1)
