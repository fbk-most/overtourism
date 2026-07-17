from GraphComplex import GraphComplex
from RankingData import RankingData
from graph_complex_functions import build_gradient_operator, build_curl_operator
from networkx import Graph
from numpy import ndarray
from scipy.sparse import eye
from scipy.sparse.linalg import lsqr 
class HodgeAnalyzer:
    def __init__(self, G: Graph):
        self.graph = GraphComplex(G)
        self.D = build_gradient_operator(self.graph)  # δ0: edges × nodes
        self.C = build_curl_operator(self.graph)      # δ1: triangles × edges
        self.W = eye(self.D.shape[0])              # weight matrix (optional)

        # Construct Laplacians
        self.L0 = self.D.T @ self.W @ self.D                      # node Laplacian
        self.L1 = self.D @ self.D.T + self.C.T @ self.C           # edge Laplacian

    def decompose(self, Y: ndarray):
        """
        Given edge flow Y (vector of size |E|), returns:
        - s: node potential (scores)
        - grad_s: projection of Y onto grad space
        - residual: Y - grad_s
        """
        b = self.D.T @ self.W @ Y
        A = self.L0

        s = lsqr(A, b)[0]
        grad_s = self.D @ s
        residual = Y - grad_s
        return s, grad_s, residual

    def curl(self, residual: ndarray):
        """
        Applies curl operator to residual edge flow
        Returns: triangle flow vector
        """
        return self.C @ residual
