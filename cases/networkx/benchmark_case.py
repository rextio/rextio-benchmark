from rextio_benchmark.canonical import node_float_mapping


def make_arguments(_benchmark_id: str) -> tuple[object, ...]:
    node_count = 20_000
    edges: list[tuple[int, int, float]] = []
    for node in range(node_count - 1):
        edges.append((node, node + 1, 1.0 + (node % 13) / 10.0))
        if node + 17 < node_count:
            edges.append((node, node + 17, 2.0 + (node % 7) / 10.0))
        if node + 101 < node_count:
            edges.append((node, node + 101, 4.0 + (node % 5) / 10.0))
    return edges, 0


def normalize(_benchmark_id: str, value: object) -> object:
    if not isinstance(value, dict):
        raise TypeError(f"expected Dijkstra mapping, got {type(value).__name__}")
    return node_float_mapping(value)
