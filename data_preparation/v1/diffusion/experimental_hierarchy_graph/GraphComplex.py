"""
    # GraphComplex.py
    This module defines the GraphComplex class, which represents a graph complex
    and provides methods to index nodes, edges, and triangles within the graph.
"""
from graph_complex_functions import index_nodes, index_edges, index_triangles
from networkx import Graph

class GraphComplex:
    """
        NOTE:
        node2idx: Maps node to index (the indices of the nodes to their sorted counterpart: {node_index: ordered_node_index})
        idx2node: Maps index to node (the sorted nodes to their indices: {ordered_node_index: node_index})
        edge2idx: Maps ordered edges (ordered_node_index_i, ordered_node_index_j) with ordered_node_index_i < ordered_node_index_j to index (the indices of the edges to their sorted counterpart: {(ordered_node_index_i, ordered_node_index_j): ordered_edge_index})
        idx2edge: Maps index to ordered edge (the sorted edges to their indices: {ordered_edge_index: (ordered_node_index_i, ordered_node_index_j)})
        triangle2idx: Maps triangles (ordered_node_index_i, ordered_node_index_j, ordered_node_index_k) with ordered_node_index_i < ordered_node_index_j < ordered_node_index_k to index (the indices of the triangles to their sorted counterpart: {(ordered_node_index_i, ordered_node_index_j, ordered_node_index_k): ordered_triangle_index})
        idx2triangle: Maps index to
        NOTE: It is important to note that the triangles are needed to be accessed from the sorted nodes
        """
    def __init__(self, G: Graph):
        self.G = G
        self.node2idx, self.idx2node = index_nodes(G)
        self.edge2idx, self.idx2edge = index_edges(G, self.node2idx)
        self.triangle2idx, self.idx2triangle = index_triangles(G, self.node2idx)

    def num_nodes(self): return len(self.node2idx)
    def num_edges(self): return len(self.edge2idx)
    def num_triangles(self): return len(self.triangle2idx)