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

import pandas as pd


# ---------------- POPULATION FUNCTIONS GIVEN VODAFONE NEW DATA ---------------- #
def add_column_area_and_fraction(
    cities_gdf,
    str_col_comuni_name,
    str_col_area="area",
    str_col_tot_area="total_area_by_name",
    str_col_fraction="fraction_area",
    str_col_centroid_lat="centroid_lat",
    str_col_centroid_lon="centroid_lon",
    crs_proj=3857,
    crs_geographic=4326,
):
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
        cities_gdf = cities_gdf.to_crs(
            epsg=crs_proj
        )  # Convert to a projected CRS (e.g., World Mercator)

    # Add area column (in square meters by default, or square units of the CRS)
    cities_gdf[str_col_area] = cities_gdf.geometry.area

    # Group by city name and calculate total area for each group
    cities_gdf[str_col_tot_area] = cities_gdf.groupby(str_col_comuni_name)[
        str_col_area
    ].transform("sum")

    # Calculate fraction of area for each polygon within its name group
    cities_gdf[str_col_fraction] = (
        cities_gdf[str_col_area] / cities_gdf[str_col_tot_area]
    )

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


def redistribute_population_by_fraction(
    cities_gdf,
    str_col_popolazione_totale,
    str_col_fraction,
    str_col_comuni_name,
    conserve_total=True,
):
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
            total_pop = city_data[str_col_popolazione_totale].iloc[
                0
            ]  # Should be same for all polygons of same city

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
            result_gdf.loc[city_mask, str_col_popolazione_totale] = (
                base_allocation.values
            )

    else:
        # Method 2: Simple multiplication with rounding
        result_gdf.loc[mask_valid_pop, str_col_popolazione_totale] = (
            (
                result_gdf.loc[mask_valid_pop, str_col_fraction]
                * result_gdf.loc[mask_valid_pop, str_col_popolazione_totale]
            )
            .round()
            .astype(int)
        )

    return result_gdf


# ---------------- GENERATE FAKE FLUXES GIVEN POPULATION DISTRIBUTION ---------------- #
