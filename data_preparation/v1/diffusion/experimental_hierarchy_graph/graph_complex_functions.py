import networkx as nx
from itertools import combinations
from typing import Dict, Tuple

def index_nodes(G: nx.Graph) -> Tuple[Dict[int, int], Dict[int, int]]:
    """Map nodes to index and vice versa"""
    nodes = sorted(G.nodes())
    node2idx = {node: idx for idx, node in enumerate(nodes)}
    idx2node = {idx: node for node, idx in node2idx.items()}
    return node2idx, idx2node


def index_edges(G: nx.Graph, node2idx: Dict[int, int]) -> Tuple[Dict[Tuple[int, int], int], Dict[int, Tuple[int, int]]]:
    """Map ordered edges (i, j) with i < j to index and vice versa"""
    edge_set = set()
    for u, v in G.edges():
        i, j = sorted((node2idx[u], node2idx[v]))
        edge_set.add((i, j))
    
    sorted_edges = sorted(edge_set)
    edge2idx = {edge: idx for idx, edge in enumerate(sorted_edges)}
    idx2edge = {idx: edge for edge, idx in edge2idx.items()}
    return edge2idx, idx2edge


def index_triangles(G: nx.Graph, node2idx: Dict[int, int]) -> Tuple[Dict[Tuple[int, int, int], int], Dict[int, Tuple[int, int, int]]]:
    """Find all triangles (3-cliques) and index them"""
    triangle_list = []
    nodes = list(G.nodes())
    for i, j, k in combinations(nodes, 3):
        if G.has_edge(i, j) and G.has_edge(j, k) and G.has_edge(k, i):
            a, b, c = sorted((node2idx[i], node2idx[j], node2idx[k]))
            triangle_list.append((a, b, c))

    triangle2idx = {tri: idx for idx, tri in enumerate(sorted(triangle_list))}
    idx2triangle = {idx: tri for tri, idx in triangle2idx.items()}
    return triangle2idx, idx2triangle
