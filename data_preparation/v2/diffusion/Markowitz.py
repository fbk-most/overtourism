import numpy as np
from scipy.optimize import minimize
import polars as pl
import numpy as np
import pandas as pd
from typing import Dict, List


def compute_returns(df: pl.DataFrame,
                    col_id: str,
                    col_date: str,
                    col_price: str,
                    col_return: str) -> pl.DataFrame:
    """
    Compute log returns per asset from a price dataframe with columns:
    col_id, col_date, col_price.
    """
    df = df.sort([col_id, col_date])
    return df.with_columns(
        (pl.col(col_price).log().diff()).over(col_id).alias(col_return)
    ).drop_nulls()

def markowitz_portfolio(df: pl.DataFrame, 
                        col_id: str,
                        col_date: str,
                        col_price: str,
                        col_return: str,
                        col_portfolio_weight: str,
                        target_return: float):
    """
    Compute Markowitz optimal weights for a given target return.
    """
    # pivot to matrix: rows = dates, columns = assets
    df_pivot = df.pivot(index=col_date, columns=col_id, values=col_return)
    returns_matrix = df_pivot.drop(col_date).to_numpy()

    # compute expected returns & covariance matrix
    g = np.nanmean(returns_matrix, axis=0)       # expected returns per asset
    C = np.cov(returns_matrix, rowvar=False)     # covariance matrix

    # invert covariance
    C_inv = np.linalg.pinv(C)                    # pseudo-inverse for stability
    w = target_return * (C_inv @ g) / (g @ C_inv @ g)

    return pd.DataFrame({
        col_id: df_pivot.columns[1:],   # skip "col_date"
        col_portfolio_weight: w
    })


def rmt_clean_correlation_matrix(C, q,is_bulk_mean = True):
    """
    Apply eigenvalue clipping using RMT.
    C: correlation matrix
    q: N/T (number of assets / number of observations)
    """
    eigvals, eigvecs = np.linalg.eigh(C)
    eigvals = np.real(eigvals)

    # Marchenko-Pastur bounds
    lambda_min = (1 - np.sqrt(q))**2
    lambda_max = (1 + np.sqrt(q))**2

    # Replace bulk eigenvalues with their average
    bulk_mask = (eigvals >= lambda_min) & (eigvals <= lambda_max)
    if is_bulk_mean:
        bulk_mean = np.mean(eigvals[bulk_mask])
        eigvals_clean = np.where(bulk_mask, bulk_mean, eigvals)                            # This one gives weights the bulk eigenvectors as the same importance
    else:
        # NOTE: In this way we are considering the eigenvalues that are outside the bulk and we are giving zero importance to the bulk eigenvalues
        # That is we are expressing as linear combination of the eigenvectors that are outside the bulk
        # Since UU.T = eigvecs*eigvecs.T = I -> we can invert it easily
        eigvals_clean = np.where(bulk_mask, 0, eigvals)                                     # This one gives zero importance to the bulk eigenvectors  
    C_clean = (eigvecs @ np.diag(eigvals_clean) @ eigvecs.T)
    return C_clean, eigvals_clean, eigvecs

    

def from_df_correlation_to_numpy_matrix(cov_df, str_area_id_presenze, str_column_cov, area_to_index):
    """
    Transform covariance DataFrame into numpy matrix and create area mapping.
    """
    n_unique_areas = len(area_to_index)
    cov_matrix_numpy = np.zeros((n_unique_areas, n_unique_areas))
    
    for row in cov_df.iter_rows(named=True):
        area_i = row[str_area_id_presenze + "_i"]
        area_j = row[str_area_id_presenze + "_j"]
        cov_value = row[str_column_cov]
        
        i_idx = area_to_index[area_i]
        j_idx = area_to_index[area_j]
        
        cov_matrix_numpy[i_idx, j_idx] = cov_value
    
    return cov_matrix_numpy


def map_portfolio_numpy_to_cities_gdf(cities_gdf,portfolio_weights,index_to_area,str_area_id_presenze,str_col_portfolio="portfolio"):
    """
    Map portfolio weights onto a GeoDataFrame of areas.
    """
    from geopandas import GeoDataFrame
    if not isinstance(cities_gdf, GeoDataFrame):
        raise TypeError("cities_gdf must be a GeoDataFrame")
    # Build mapping from area_id -> weight
    area_to_weight = {area: float(portfolio_weights[idx]) for idx, area in index_to_area.items()}

    # Map weights onto the GeoDataFrame
    mapped = cities_gdf[str_area_id_presenze].map(area_to_weight)
    cities_gdf = cities_gdf.copy()
    cities_gdf.loc[:, str_col_portfolio] = mapped
    return cities_gdf

def from_areas_and_times_to_q(area_to_index:Dict,
                              list_str_days:List):
    """
    Compute q = T/N where T is the number of observations and N is the number of
    assets (areas).
    Parameters:
    - area_to_index: Dict, mapping from area IDs to indices.
    - list_str_days: List, list of unique days (observations).
    Returns:
    - q: float, ratio T/N.
    """    
    # Transform covariance DataFrame into numpy matrix and create area mapping
    n_unique_areas = len(area_to_index)
    T = len(list_str_days)
    # Correctly define q as T/N. The Marchenko-Pastur distribution requires q.
    q = T / n_unique_areas
    print(f"T (observations) = {T}, N (assets) = {n_unique_areas}, q = T/N = {q:.4f}")
    return q


def compute_MP_limits_and_mask(eigvals_clean, q, is_covariance_standardized=True, sigma = None):
    """
    Compute the Marchenko-Pastur limits and the mask for significant eigenvalues.
    Parameters:
    - eigvals_clean: array-like, eigenvalues of the cleaned correlation matrix.
    - q: float, ratio T/N where T is the number of observations and N is the number of assets.
    Returns:
    - lambda_minus: float, lower limit of the MP distribution.
    - lambda_plus: float, upper limit of the MP distribution.
    - mask_eigvals: boolean array, mask indicating which eigenvalues are above lambda_plus
    NOTE: The covariance matrix is standardized, so the variance is 1.
    """
    if is_covariance_standardized:
        lambda_plus = (1 + np.sqrt(1/q))**2
        lambda_minus = (1 - np.sqrt(1/q))**2
        print(f"MP limits (standardized covariance): lambda_minus = {lambda_minus:.4f}, lambda_plus = {lambda_plus:.4f}")
    else:
        if sigma is None:
            raise ValueError("sigma must be provided for non-standardized covariance matrices.")
        else:
            lambda_plus = sigma**2 * (1 + np.sqrt(1/q))**2
            lambda_minus = sigma**2 * (1 - np.sqrt(1/q))**2
            print(f"MP limits (non-standardized covariance): lambda_minus = {lambda_minus:.4f}, lambda_plus = {lambda_plus:.4f}")

    mask_eigvals = eigvals_clean > lambda_plus
    print(f"Number of eigenvalues above lambda_plus: {np.sum(mask_eigvals)} out of {len(eigvals_clean)}, fraction: {np.sum(mask_eigvals)/len(eigvals_clean):.4f}")
    return lambda_minus, lambda_plus, mask_eigvals


def extract_portfolio_from_eigenpairs(C_clean, 
                                      eigvals_clean, 
                                      eigvecs, 
                                      expected_return, 
                                      sum_w = 1,
                                      is_normalize_portfolio=True):
    """
    Reconstruct Inverse Solution for Markowitz:
        - choose eigenvalues larger than lambda_plus (max expected by MP)
        - reconstruct the inverse covariance matrix using only the selected eigenvalues and their corresponding eigenvectors
        - compute the Markowitz portfolio weights using the cleaned inverse covariance matrix
    Inputs:
        - eigvals_clean: np.array, cleaned eigenvalues of the covariance matrix
        - eigvecs: np.array, eigenvectors of the covariance matrix
        - mask_eigvals: np.array of bool, mask to select eigenvalues larger than lambda_plus
        - g: np.array, expected returns (usually considered as the observed average over the period of interest)
        - C_clean: np.array, cleaned covariance matrix
    Outputs:
        - w: np.array, portfolio weights
    """
    assert C_clean.shape[0] == C_clean.shape[1], "Covariance matrix must be square"
    assert C_clean.shape[0] == eigvals_clean.shape[0], "Covariance matrix and eigenvalues must have compatible dimensions"
    assert C_clean.shape[0] == eigvecs.shape[0], "Covariance matrix and eigenvectors must have compatible dimensions"
    assert eigvecs.shape[0] == eigvecs.shape[1], "Eigenvectors matrix must be square"
    assert eigvals_clean.shape[0] == eigvecs.shape[0], "Eigenvalues and eigenvectors must have compatible dimensions"
    assert expected_return.shape[0] == C_clean.shape[0], "Expected returns vector must have compatible dimensions"    
    print("Extract portfolio")
    N = len(C_clean)
    # NOTE: cumulative expectations -> fixed -> lagrange multiplier for the constraint \sum_i w_i g_i = G
    G = np.sum(expected_return)
    # NOTE: vector of ones (of fixed sum_w) -> lagrange multiplier for the constraint \sum_i w_i = sum_w
    vec_ones = np.ones(N)*sum_w
    # NOTE: Sigma^{-1} present in the solution of the optimization problem of Markowitz
    print("Compute inverse of the cleaned covariance matrix")
    # NOTE: U.T*U = I, therefore the inverse is U*Lambda^{-1}*U.T
    Sigma_inv_clean = np.linalg.pinv(C_clean)
    print("Compute A = 1^T Sigma^{-1} 1")
    A = vec_ones @ Sigma_inv_clean @ vec_ones
    print("Compute B = 1^T Sigma^{-1} g")
    B = vec_ones @ Sigma_inv_clean @ expected_return   # NOTE: g is a vector of ones since we want to maximize the number of presences
    print("Compute C = g^T Sigma^{-1} g")
    C = expected_return @ Sigma_inv_clean @ expected_return
    print("Compute D = AC - B^2")
    D = A * C - B**2
    print(f"A = {A}, B = {B}, C = {C}, D = {D}")
    # Reconstruct Inverse Solution for Markowitz
    print("w* = Sigma^{-1} ((C - B G)/D 1 + (A G - B)/D g )")
    # NOTE: Solution of Markowitz: w = C^{-1} 1 / (1^T C^{-1} 1)
    w = np.linalg.pinv(Sigma_inv_clean) @ ((C - B * G) / D * vec_ones + (A * G - B) / D * expected_return)
    # NOTE: Normalize the portfolio to sum to 1
    if is_normalize_portfolio:
        w = w / np.sum(w)  # Normalize to sum to 1
    return w

## Markowitz Functions if not analytical solution is possible

def portfolio_performance(weights, mu, cov):
    """
        Calculate portfolio return and volatility.
    """
    port_return = np.dot(weights, mu)
    port_vol = np.sqrt(np.dot(weights.T, np.dot(cov, weights)))
    return port_return, port_vol


def min_volatility(target_return, mu, cov):
    """
        Minimize portfolio volatility for a given target return.
    """
    n = len(mu)
    init_guess = np.ones(n) / n
    bounds = [(0, 1) for _ in range(n)]  # long-only
    constraints = (
        {"type": "eq", "fun": lambda w: np.sum(w) - 1},              # sum of weights = 1
        {"type": "eq", "fun": lambda w: np.dot(w, mu) - target_return},  # expected return
    )

    result = minimize(
        lambda w: np.sqrt(np.dot(w.T, np.dot(cov, w))),  # objective: volatility
        init_guess,
        bounds=bounds,
        constraints=constraints,
    )
    return result.x
