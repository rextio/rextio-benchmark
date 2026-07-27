import tensorflow as tf

from rextio_benchmark.canonical import exact_sequence


def make_arguments(benchmark_id: str) -> tuple[object, ...]:
    if benchmark_id == "tensorflow-cpu-small-batch-prepost":
        feature_width = 32
        class_count = 8
        x = tf.reshape(
            tf.range(feature_width, dtype=tf.float32) * 0.01 - 0.15,
            (1, feature_width),
        )
        mean = tf.range(feature_width, dtype=tf.float32) * 0.001 - 0.01
        scale = 0.75 + tf.range(feature_width, dtype=tf.float32) * 0.005
        feature_w = tf.reshape(
            tf.range(feature_width * feature_width, dtype=tf.float32) * 0.002 - 0.05,
            (feature_width, feature_width),
        )
        feature_b = tf.range(feature_width, dtype=tf.float32) * 0.003
        head_w = tf.reshape(
            tf.range(feature_width * class_count, dtype=tf.float32) * 0.004 - 0.08,
            (feature_width, class_count),
        )
        head_b = tf.range(class_count, dtype=tf.float32) * 0.01 - 0.03
        return x, mean, scale, feature_w, feature_b, head_w, head_b
    # x: 512x96, weight: 80x96 (non-square), default transpose -> 96x80, bias: 80.
    tf.random.set_seed(20260726)
    x = tf.random.stateless_normal((512, 96), seed=(20, 26), dtype=tf.float32)
    weight = tf.random.stateless_normal((80, 96), seed=(7, 26), dtype=tf.float32) * 0.04
    bias = tf.linspace(-0.1, 0.1, 80)
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
