import tensorflow as tf

from rextio_benchmark.canonical import exact_sequence


def make_arguments(_benchmark_id: str) -> tuple[object, ...]:
    tf.random.set_seed(20260726)
    x = tf.random.stateless_normal((512, 96), seed=(20, 26), dtype=tf.float32)
    weight = tf.random.stateless_normal((96, 96), seed=(7, 26), dtype=tf.float32) * 0.04
    bias = tf.linspace(-0.1, 0.1, 96)
    return x, weight, bias, 12, 1


def normalize(_benchmark_id: str, value: object) -> object:
    if not isinstance(value, tf.Tensor):
        raise TypeError(f"expected Tensor, got {type(value).__name__}")
    array = value.numpy()
    return exact_sequence(
        kind="tensor",
        shape=array.shape,
        dtype=str(array.dtype),
        values=array.reshape(-1).tolist(),
    )
