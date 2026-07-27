from rextio_networkx import (
    DijkstraLengthsI64,
    NodeI64,
    WeightedEdgeListI64F64,
    dijkstra_path_lengths,
    weighted_graph_from_edgelist,
)


def dijkstra(
    edges: WeightedEdgeListI64F64,
    source: NodeI64,
) -> DijkstraLengthsI64:
    return dijkstra_path_lengths(weighted_graph_from_edgelist(edges), source)

