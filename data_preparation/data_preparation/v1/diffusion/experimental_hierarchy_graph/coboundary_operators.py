import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from typing import Dict, Tuple
from GraphComplex import GraphComplex

# NOTE: Gradient operator (edges to nodes)

def build_gradient_operator(graph:GraphComplex) -> sp.csr_matrix:
    """Builds the gradient (incidence) matrix D (|E| x |V|)"""
    num_edges = len(graph.edge2idx)
    num_nodes = len(graph.node2idx)
    data, rows, cols = [], [], []

    for (i, j), k in graph.edge2idx.items():
        rows.append(k)
        cols.append(i)
        data.append(-1)

        rows.append(k)
        cols.append(j)
        data.append(+1)

    D = sp.coo_matrix((data, (rows, cols)), shape=(num_edges, num_nodes))
    return D.tocsr()

def project_onto_gradient_space(Y: np.ndarray, D: sp.csr_matrix, W: sp.csr_matrix = None):
    """
        Given edge flow Y (|E|,), incidence matrix D (|E| x |V|),
        and optional edge weight matrix W (|E| x |E|), return best-fit grad s.
    """
    if W is None:
        W = sp.eye(D.shape[0])  # Identity if unweighted

    A = D.T @ W @ D            # Laplacian matrix (symmetric, positive semi-definite)
    b = D.T @ W @ Y            # RHS of normal equations

    # Solve A s = b (with pinv if singular)
    s = spla.lsqr(A, b)[0]     # or spla.cg(A, b)[0] if A is well-conditioned

    grad_s = D @ s             # This is the projection of Y onto im(grad)
    return s, grad_s

# NOTE: Curl operator (triangles to edges)
def build_curl_operator(graph:GraphComplex) -> sp.csr_matrix:
    """Builds the curl operator (triangles × edges)"""
    num_triangles = len(graph.triangle2idx)
    num_edges = len(graph.edge2idx)
    data, rows, cols = [], [], []

    for (i, j, k), t_idx in graph.triangle2idx.items():
        # Each triangle contributes 3 oriented edges
        oriented_edges = [((i, j), +1),
                          ((j, k), +1),
                          ((k, i), +1)]

        for (u, v), sign in oriented_edges:
            edge = (min(u, v), max(u, v))
            edge_sign = sign if (u < v) else -sign
            if edge in graph.edge2idx:
                e_idx = graph.edge2idx[edge]
                rows.append(t_idx)
                cols.append(e_idx)
                data.append(edge_sign)

    C = sp.coo_matrix((data, (rows, cols)), shape=(num_triangles, num_edges))
    return C.tocsr()
