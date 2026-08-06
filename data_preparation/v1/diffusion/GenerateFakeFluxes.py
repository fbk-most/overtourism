"""
Generate Fake Fluxes - Mobility Flow Generation and Geospatial Processing

This module provides utilities for generating synthetic mobility flows using gravity models
and processing geospatial data for tourism and mobility analysis. It combines geospatial
operations with gravity model-based flow generation to create realistic mobility patterns
for analysis and simulation purposes.

Main Components:

1. GEOSPATIAL PROCESSING FUNCTIONS:
   - Area calculation and fraction computation for city polygons
   - Centroid extraction in geographic coordinates
   - Population redistribution based on area fractions
   - Handling of duplicate city names with suffix addition

2. GRAVITY MODEL IMPLEMENTATION:
   - Standard gravity model for mobility flow generation
   - Polars-optimized batch processing for large datasets
   - Population-weighted flow calculation with distance decay
   - Total flow conservation through intelligent rounding

Key Functions:

add_column_area_and_fraction():
    Computes polygon areas, centroids, and area fractions for city geometries.
    Handles CRS transformations for accurate area calculation.

add_suffix_to_repeated_values():
    Resolves duplicate city names by adding numerical suffixes.

redistribute_population_by_fraction():
    Redistributes population data across city polygons based on area fractions
    using the largest remainder method to preserve total population.

GravityModel() / GravityModel_polars():
    Implements the gravity model equation: T_ij = K * (M_i^α * M_j^γ) * exp(d_ij * β)
    where T_ij is flow from origin i to destination j.

AddGravityColumnTij():
    Applies gravity model to distance matrix with population data.
    Scales flows to match specified total volume and converts to integers
    while preserving total count through remainder distribution.

Mathematical Model:
The gravity model generates flows based on:
- Origin population (M_i) raised to power α
- Destination population (M_j) raised to power γ  
- Distance decay factor exp(d_ij * D0minus1)
- Scaling constant K to match total flow volume

Use Cases:
- Generate baseline mobility scenarios for comparison
- Create synthetic datasets for testing algorithms
- Simulate tourism flows under different conditions
- Validate real mobility data against theoretical models

Dependencies: numpy, polars, pandas, geopandas, GeometrySphere
Author: Alberto Amaduzzi
"""
import numpy as np
import polars as pl
import pandas as pd
from data_preparation.diffusion.GeometrySphere import *



# ---------------- POPULATION FUNCTIONS GIVEN VODAFONE NEW DATA ---------------- #
def add_column_area_and_fraction(cities_gdf, 
                                 str_col_comuni_name,
                                 str_col_area = 'area',
                                 str_col_tot_area = 'total_area_by_name',
                                 str_col_fraction = 'fraction_area',
                                 str_col_centroid_lat = "centroid_lat",
                                 str_col_centroid_lon = "centroid_lon",
                                 crs_proj = 3857, 
                                 crs_geographic = 4326):
    """
    Add area, fraction, and centroid columns to the GeoDataFrame.
    
    Parameters:
    - cities_gdf: GeoDataFrame containing city geometries.
    - str_col_comuni_name: Column name for city names.
    - str_col_area: Column name for area.
    - str_col_tot_area: Column name for total area by name.
    - str_col_fraction: Column name for area fraction.
    - str_col_centroid_lat: Column name for centroid latitude.
    - str_col_centroid_lon: Column name for centroid longitude.
    - crs_proj: Projected CRS for area calculation.
    - crs_geographic: Geographic CRS for final output and centroids.
    
    Returns:
    - Updated GeoDataFrame with area, fraction, and centroid columns.
    """
    # Store original CRS
    original_crs = cities_gdf.crs
    
    # Ensure the geometry is in a projected CRS for accurate area calculation
    if cities_gdf.crs.is_geographic:
        cities_gdf = cities_gdf.to_crs(epsg=crs_proj)  # Convert to a projected CRS (e.g., World Mercator)
    
    # Add area column (in square meters by default, or square units of the CRS)
    cities_gdf[str_col_area] = cities_gdf.geometry.area
    
    # Group by city name and calculate total area for each group
    cities_gdf[str_col_tot_area] = cities_gdf.groupby(str_col_comuni_name)[str_col_area].transform('sum')
    
    # Calculate fraction of area for each polygon within its name group
    cities_gdf[str_col_fraction] = cities_gdf[str_col_area] / cities_gdf[str_col_tot_area]
    
    # Convert to geographic CRS for centroid calculation
    cities_gdf = cities_gdf.to_crs(epsg=crs_geographic)
    
    # Calculate centroids in geographic coordinates
    centroids = cities_gdf.geometry.centroid
    cities_gdf[str_col_centroid_lat] = centroids.y
    cities_gdf[str_col_centroid_lon] = centroids.x
    
    return cities_gdf

def add_suffix_to_repeated_values(cities_gdf, str_col_comuni_name):
    """
    Add suffix "_{i}" to repeated values in the specified column.
    
    Parameters:
    -----------
    cities_gdf : gpd.GeoDataFrame
        GeoDataFrame containing city data
    str_col_comuni_name : str
        Column name where repeated values should get suffixes
        
    Returns:
    --------
    gpd.GeoDataFrame
        Updated GeoDataFrame with suffixed values
    """
    result_gdf = cities_gdf.copy()
    
    # Count occurrences of each value
    value_counts = result_gdf[str_col_comuni_name].value_counts()
    
    # For values that appear more than once, add suffix
    repeated_values = value_counts[value_counts > 1].index
    
    # Dictionary to keep track of suffix counter for each repeated value
    suffix_counters = {value: 0 for value in repeated_values}
    
    # Iterate through the dataframe and add suffixes
    for idx, row in result_gdf.iterrows():
        original_value = row[str_col_comuni_name]
        
        if original_value in repeated_values:
            # Add suffix to the value
            new_value = f"{original_value}_{suffix_counters[original_value]}"
            result_gdf.at[idx, str_col_comuni_name] = new_value
            
            # Increment the counter for this value
            suffix_counters[original_value] += 1
    
    return result_gdf

def redistribute_population_by_fraction(cities_gdf, 
                                      str_col_popolazione_totale, 
                                      str_col_fraction,
                                      str_col_comuni_name,
                                      conserve_total=True):
    """
    Redistribute population based on area fractions.
    
    Parameters:
    -----------
    cities_gdf : gpd.GeoDataFrame
        GeoDataFrame containing city data
    str_col_popolazione_totale : str
        Column name for total population
    str_col_fraction : str
        Column name for area fraction
    str_col_comuni_name : str
        Column name for city names (to group by)
    conserve_total : bool
        If True, conserve total population by distributing remainders
        
    Returns:
    --------
    gpd.GeoDataFrame
        Updated GeoDataFrame with redistributed population
    """
    result_gdf = cities_gdf.copy()
    
    # Handle missing population values
    mask_valid_pop = ~result_gdf[str_col_popolazione_totale].isna()
    
    if conserve_total:
        # Method 1: Conserve total population using largest remainder method
        for city_name in result_gdf[str_col_comuni_name].unique():
            city_mask = (result_gdf[str_col_comuni_name] == city_name) & mask_valid_pop
            
            if not city_mask.any():
                continue
                
            city_data = result_gdf.loc[city_mask]
            total_pop = city_data[str_col_popolazione_totale].iloc[0]  # Should be same for all polygons of same city
            
            if pd.isna(total_pop):
                continue
            
            # Calculate base allocation (integer part)
            fractions = city_data[str_col_fraction]
            base_allocation = (fractions * total_pop).astype(int)
            allocated_so_far = base_allocation.sum()
            
            # Calculate remainders
            remainders = (fractions * total_pop) - base_allocation
            remaining_people = int(total_pop) - allocated_so_far
            
            # Distribute remaining people to polygons with largest remainders
            if remaining_people > 0:
                # Get indices sorted by remainder (descending) - fix the index access
                remainder_order = remainders.sort_values(ascending=False).index
                
                # Distribute one person each to polygons with largest remainders
                for i in range(min(remaining_people, len(remainder_order))):
                    idx = remainder_order[i]  # Use bracket notation instead of iloc
                    base_allocation.loc[idx] += 1
            
            # Update the population values
            result_gdf.loc[city_mask, str_col_popolazione_totale] = base_allocation.values
            
    else:
        # Method 2: Simple multiplication with rounding
        result_gdf.loc[mask_valid_pop, str_col_popolazione_totale] = (
            result_gdf.loc[mask_valid_pop, str_col_fraction] * 
            result_gdf.loc[mask_valid_pop, str_col_popolazione_totale]
        ).round().astype(int)
    
    return result_gdf



# ---------------- GENERATE FAKE FLUXES GIVEN POPULATION DISTRIBUTION ---------------- #

def GravityModel(Mi,Mj,Dij,k,alpha,gamma,d0minus1):
    """
        @param Mi: (int) -> Mass of the origin
        @param Mj: (int) -> Mass of the destination
        @param Dij: (float) -> Distance between origin and destination
        @param k: (float) -> Multiplicative factor
        @param alpha: (float) -> Exponent of the origin
        @param gamma: (float) -> Exponent of the destination
        @param d0minus1: (float) -> Exponential factor
        @return: (float) -> Gravity Fluxes
    """
    return k*Mi**alpha*Mj**gamma* np.exp(Dij*d0minus1)

def GravityModel_polars(pop_i, pop_j, distance, K, Alpha, Gamma, D0minus1):
    """Polars-compatible GravityModel function"""
    import polars as pl
    import numpy as np
    
    # Handle the case where inputs might be Polars Series
    if hasattr(pop_i, 'to_numpy'):
        pop_i = pop_i.to_numpy()
    if hasattr(pop_j, 'to_numpy'):
        pop_j = pop_j.to_numpy()
    if hasattr(distance, 'to_numpy'):
        distance = distance.to_numpy()
    
    # Convert to numpy arrays if they're not already
    pop_i = np.array(pop_i)
    pop_j = np.array(pop_j)
    distance = np.array(distance)
    
    # Initialize result array
    result = np.zeros_like(distance, dtype=np.float64)
    
    # Handle zero distances
    non_zero_mask = distance > 0
    
    # Handle null values
    valid_mask = (~np.isnan(pop_i)) & (~np.isnan(pop_j)) & (pop_i > 0) & (pop_j > 0)
    
    # Combine masks
    compute_mask = non_zero_mask & valid_mask
    
    # Calculate gravity model for valid entries
    if np.any(compute_mask):
        result[compute_mask] = (K * 
                               np.power(pop_i[compute_mask], Alpha) * 
                               np.power(pop_j[compute_mask], Gamma) * 
                               np.exp(D0minus1 * distance[compute_mask]))
    
    return result

def AddGravityColumnTij(Tij_dist_fit_gravity,
                        K,
                        Alpha,
                        Gamma,
                        D0minus1,
                        total_number_people,
                        str_distance_column,
                        str_population_origin_column,
                        str_population_destination_column,
                        str_fluxes_column):
    """
        @param Tij_dist_fit_gravity: (polars.DataFrame) -> Dataframe with the distances and populations
        @param K: (float) -> Multiplicative factor
        @param Alpha: (float) -> Exponent of the origin
        @param Gamma: (float) -> Exponent of the destination
        @param D0minus1: (float) -> Exponential factor
        @param total_number_people: (int) -> Total number of people that have flown
        @param str_distance_column: (str) -> Name of the column with the distances
        @param str_population_origin_column: (str) -> Name of the column with the population of the origin
        @param str_population_destination_column: (str) -> Name of the column with the population of the destination
        @param str_fluxes_column: (str) -> Name of the column with the fluxes
        @return: (polars.DataFrame) -> Dataframe with the distances, populations and fluxes
    """
    assert str_distance_column in Tij_dist_fit_gravity.columns, f"Column {str_distance_column} not found in dataframe"
    assert str_population_origin_column in Tij_dist_fit_gravity.columns, f"Column {str_population_origin_column} not found in dataframe"
    assert str_population_destination_column in Tij_dist_fit_gravity.columns, f"Column {str_population_destination_column} not found in dataframe"
    
    # Use GravityModel_polars instead of GravityModel
    def apply_gravity_model_batch(batch):
        return GravityModel_polars(
            batch.struct.field(str_population_origin_column),
            batch.struct.field(str_population_destination_column),
            batch.struct.field(str_distance_column),
            K, Alpha, Gamma, D0minus1
        )
    
    # Add a column to the dataframe with the gravity fluxes
    Tij_dist_fit_gravity = Tij_dist_fit_gravity.with_columns(
        pl.struct([str_distance_column, str_population_origin_column, str_population_destination_column])
        .map_batches(apply_gravity_model_batch).alias(str_fluxes_column)
    )
    
    # Calculate scaling factor
    flux_sum = Tij_dist_fit_gravity[str_fluxes_column].sum()
    K1 = K * total_number_people / flux_sum
    
    # Rescale by the total number of people that have flown
    def apply_gravity_model_batch_scaled(batch):
        return GravityModel_polars(
            batch.struct.field(str_population_origin_column),
            batch.struct.field(str_population_destination_column),
            batch.struct.field(str_distance_column),
            K1, Alpha, Gamma, D0minus1
        )
    
    Tij_dist_fit_gravity = Tij_dist_fit_gravity.with_columns(
        pl.struct([str_distance_column, str_population_origin_column, str_population_destination_column])
        .map_batches(apply_gravity_model_batch_scaled).alias(str_fluxes_column)
    )
    
    # Advanced integer conversion that preserves total count
    import numpy as np
    
    # Get the float values
    float_fluxes = Tij_dist_fit_gravity[str_fluxes_column].to_numpy()
    
    # Use numpy's rounding with remainder distribution to preserve total
    int_fluxes = np.floor(float_fluxes).astype(int)
    remainders = float_fluxes - int_fluxes
    
    # Calculate how many additional units to distribute
    total_remainder = int(total_number_people - int_fluxes.sum())
    
    # Distribute the remainder based on the fractional parts
    if total_remainder > 0:
        # Get indices sorted by remainder (descending)
        sorted_indices = np.argsort(remainders)[::-1]
        # Add 1 to the top remainder entries
        int_fluxes[sorted_indices[:total_remainder]] += 1
    
    # Convert back to polars and update the dataframe
    Tij_dist_fit_gravity = Tij_dist_fit_gravity.with_columns(
        pl.Series(str_fluxes_column, int_fluxes, dtype=pl.Int64)
    )
    
    return Tij_dist_fit_gravity, K1




def routine_generation_flows(df_distance_matrix,
                            cities_gdf,
                            str_col_i,
                            str_col_j,
                            str_population_col,
                            str_population_i_col,
                            str_population_j_col):
    """
    Routine to generate flows using a gravity model.
        @param df_distance_matrix: (pl.DataFrame) -> Dataframe with the distances between the cities
        @param cities_gdf: (gpd.GeoDataFrame) -> GeoDataframe with the cities
        @param str_col_i: (str) -> Name of the column with the origin city
        @param str_col_j: (str) -> Name of the column with the
        @param str_population_col: (str) -> Name of the column with the population
        @param str_population_i_col: (str) -> Name of the column with the population of the origin
        @param str_population_j_col: (str) -> Name of the column with the population of the destination
        @return: (pl.DataFrame, pl.DataFrame) -> Dataframe with the flows and dataframe with the baseline flows 
    """

    # NOTE: The str_population_col_grid contains information about the state of the population in time, in this case, without data I have 
    Tij_dist = add_population_column_2_distance_matrix(df_distance_matrix,
                                                        cities_gdf,
                                                        str_col_i = str_col_origin,
                                                        str_col_j = str_col_destination,
                                                        str_population_col = str_population_col_grid,
                                                        str_population_i_col = str_population_i,
                                                        str_population_j_col = str_population_j)   

    K = 1.0                                                                                                                         # Gravity model parameter K
    Alpha = 1.0                                                                                                                   # Gravity model parameter Alpha
    Gamma = 1.0                                                                                                                   # Gravity model parameter Gamma
    D0minus1 = -0.1     
    total_number_people = 10000                                                                                      # Gravity model parameter D0minus1
    Tij_dist,K1 = AddGravityColumnTij(pl.DataFrame(Tij_dist),
                                                K,
                                                Alpha,
                                                Gamma,
                                                D0minus1,
                                                total_number_people,
                                                str_distance_column = str_distance_column,
                                                str_population_origin_column = str_population_i,
                                                str_population_destination_column = str_population_j,
                                                str_fluxes_column = str_col_n_trips)
    total_number_people_baseline = 2000
    Tij_dist_baseline, K2 =  AddGravityColumnTij(pl.DataFrame(Tij_dist),
                                                K,
                                                Alpha,
                                                Gamma,
                                                D0minus1,
                                                total_number_people,
                                                str_distance_column = str_distance_column,
                                                str_population_origin_column = str_population_i,
                                                str_population_destination_column = str_population_j,
                                                str_fluxes_column = str_col_n_trips)
    
    # Memory management: Clear temporary variables
    del K, Alpha, Gamma, D0minus1, total_number_people, total_number_people_baseline, K1, K2
    return Tij_dist, Tij_dist_baseline