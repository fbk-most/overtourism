"""
Origin-Destination (OD) Matrix Generation and Flow Analysis Module

This module provides comprehensive utilities for computing origin-destination matrices,
analyzing mobility flows, and processing transportation network relationships. It specializes
in GTFS-based transit analysis, spatial joins between transportation elements, and
flow computation for tourism and mobility studies.

Main Components:

1. OD MATRIX COMPUTATION:
   - Grid-based OD matrix generation from GTFS trip data
   - Time-windowed flow analysis with configurable intervals
   - Infrastructure-based flow computation using route timetables
   - Direction-aware trip assignment and flow directionality

2. SPATIAL RELATIONSHIP MAPPING:
   - Grid-to-stop spatial joins and indexing
   - Stop-to-route relationship extraction from GTFS data
   - Route-to-transportation network mapping
   - Multi-level spatial hierarchy (grid → stop → route → transport)

3. DISTANCE AND DIRECTION MATRICES:
   - Vectorized haversine distance computation between centroids
   - Normalized direction vector calculation for flow analysis
   - Optimized batch processing for large spatial datasets
   - Caching system for computed matrices

4. FLOW AGGREGATION AND ANALYSIS:
   - Total in-flow and out-flow computation per grid cell
   - Population-weighted flow analysis
   - Flow masking and filtering by origin/destination lists
   - Integration with gravity model results

Key Functions:

compute_OD_grid_at_t():
    Generates OD matrix for specific time window using GTFS trip data.
    Handles time-based filtering and spatial aggregation.


pipeline_get_grid_idx_2_stop_idx():
    Creates spatial mapping between grid cells and transportation stops.
    Includes caching and automatic relationship discovery.

compute_direction_matrix_optimized():
    Vectorized computation of direction vectors and distances between all grid pairs.
    Uses haversine formula for geographic accuracy.

compute_total_flows_from_flow():
    Aggregates flows to compute total in-flows or out-flows per spatial unit.
    Supports both Polars and Pandas DataFrame inputs.

Pipeline Functions:
- Grid-to-stop relationship mapping with spatial joins
- Stop-to-trip-to-route relationship extraction
- Route-to-transportation network assignment
- Comprehensive caching system for all relationship mappings

Spatial Processing Features:
- CRS-aware spatial joins with configurable buffers
- Multi-geometry handling (points, lines, polygons)
- Distance-based nearest neighbor assignment
- Component-based spatial organization

Integration Points:
- Works with GTFS feeds for public transportation analysis
- Supports gravity model flow generation and validation
- Compatible with tourism flow analysis and hotspot detection
- Provides foundation for mobility hierarchy analysis

Output Structures:
- OD matrices with origin, destination, and flow columns
- Spatial relationship dictionaries (JSON cached)
- Distance matrices with direction vectors
- Flow-aggregated spatial grids

Dependencies: pandas, polars, geopandas, numpy, haversine, gtfs_kit, tqdm
Data Sources: GTFS feeds, OpenStreetMap networks, population grids
Use Cases: Transit analysis, tourism flow modeling, accessibility studies
Author: Alberto Amaduzzi
"""

import pandas as pd
import polars as pl
from haversine import haversine, haversine_vector
from numpy import array, errstate, fill_diagonal, sqrt
from os.path import exists
from pandas import DataFrame, read_parquet
from tqdm import tqdm

####################### DIRECTION MATRIX ###########################


def compute_direction_matrix_optimized(
    grid, str_centroid_x_col, str_centroid_y_col, complete_path_direction_distance_df
):
    """
    Vectorized computation of direction and distance matrices.

    Parameters:
        grid: GeoDataFrame with grid points
        str_centroid_x_col: Column name for x coordinates
        str_centroid_y_col: Column name for y coordinates
        complete_path_direction_distance_df: Path to cached results

    Returns:
        direction_matrix: Dictionary of normalized direction vectors
        distance_matrix: Dictionary of haversine distances
    """
    if exists(complete_path_direction_distance_df):
        # Maybe read the file and convert back to dictionaries?
        return None, None
    else:
        # Extract coordinates as arrays (once)
        n = len(grid)
        x_coords = grid[str_centroid_x_col].values
        y_coords = grid[str_centroid_y_col].values

        # Use vectorized operations for direction computation
        # Create coordinate matrices where each element (i,j) has the difference between points i and j
        x_diff = x_coords.reshape(-1, 1) - x_coords.reshape(1, -1)  # shape (n, n)
        y_diff = y_coords.reshape(-1, 1) - y_coords.reshape(1, -1)  # shape (n, n)

        # Compute magnitudes (avoiding division by zero)
        magnitudes = sqrt(x_diff**2 + y_diff**2)

        # Precompute all the normalized vectors
        with errstate(divide="ignore", invalid="ignore"):
            normalized_x = x_diff / magnitudes
            normalized_y = y_diff / magnitudes

        # Fix NaN values (diagonal elements where i == j)
        fill_diagonal(normalized_x, 0)
        fill_diagonal(normalized_y, 0)

        # Create direction matrix as dictionary of dictionaries
        direction_matrix = {}
        for i in tqdm(range(n), desc="Building direction matrix", unit="row"):
            direction_matrix[i] = {}
            for j in range(n):
                if i != j:  # Skip self-connections
                    direction_matrix[i][j] = array(
                        [normalized_x[i, j], normalized_y[i, j]]
                    )
                else:
                    direction_matrix[i][j] = array(
                        [0, 0]
                    )  # Self to self has no direction

        # For haversine computation, prepare coordinates in the required format
        coords1 = [(y_coords[i], x_coords[i]) for i in range(n)]
        coords2_matrix = [
            [(y_coords[j], x_coords[j]) for j in range(n)]
            for i in tqdm(range(n), desc="coords 2 matrix", unit="row")
        ]

        # Use haversine_vector for batch computation if available
        # Otherwise, fall back to dictionary comprehension
        try:
            # Check if haversine_vector is available (newer versions of haversine)
            distance_matrix_array = array(
                [
                    haversine_vector(coords1[i : i + 1] * n, coords2_matrix[i])
                    for i in tqdm(
                        range(n), desc="Building distance matrix array", unit="row"
                    )
                ]
            )

            # Convert array to dictionary format
            distance_matrix = {}
            for i in range(n):
                distance_matrix[i] = {j: distance_matrix_array[i][j] for j in range(n)}

        except (AttributeError, TypeError):
            # Fall back to original method if vectorized version not available
            distance_matrix = {
                i: {
                    j: haversine((y_coords[i], x_coords[i]), (y_coords[j], x_coords[j]))
                    for j in range(n)
                }
                for i in tqdm(
                    range(n), desc="Building distance matrix dict", unit="row"
                )
            }

        return direction_matrix, distance_matrix


def direction_distance_2_df(
    direction_matrix,
    distance_matrix,
    complete_path_direction_distance_df,
    str_i_col="i",
    str_j_col="j",
    str_dir_vector_col="dir_vector",
    str_distance_col="distance",
):
    if exists(complete_path_direction_distance_df):
        df = read_parquet(complete_path_direction_distance_df)
        return df
    else:
        rows = []
        columns = [str_i_col, str_j_col, str_dir_vector_col, str_distance_col]
        # Iterate over the direction and distance matrices to construct DataFrame rows
        for i, dir_row in direction_matrix.items():
            for j, dir_vector in dir_row.items():
                distance = distance_matrix[i][j]
                rows.append([i, j, dir_vector, distance])
        # Create DataFrame
        df = DataFrame(rows, columns=columns)
        df.to_parquet(complete_path_direction_distance_df, index=False)
        return df


######################## DIRECTION MATRIX END ########################
######################################################################
########################## OD MATRIX #################################
def compute_total_flows_from_flow(
    flows,
    grid,
    is_in_flows,
    str_col_total_flows_grid,
    str_col_origin="i",
    str_col_destination="j",
    str_col_n_trips="n_trips",
):
    """
    @params flows: pl.DataFrame -> col [str_col_origin, str_col_destination, str_col_n_trips]
    @params grid: GeoDataFrame -> whose index has values that are in "str_col_origin" or "str_col_destination"
    @params is_in_flows: bool -> True for inflows (destinations), False for outflows (origins)
    @params str_col_total_flows_grid: str -> name of the column to add to grid with total flows
    Compute the total in or out flows of a certain geometry contained in the grid.
    """
    # Make a copy of the grid to avoid modifying the original
    grid_result = grid.copy()

    if is_in_flows:
        # Compute inflows (sum of trips ending at each destination)
        total_flows = (
            flows.group_by(str_col_destination)
            .agg(pl.col(str_col_n_trips).sum())
            .sort(str_col_destination)
        )

        # Create a mapping dictionary from destination index to total flows
        flows_dict = dict(
            zip(
                total_flows[str_col_destination].to_list(),
                total_flows[str_col_n_trips].to_list(),
            )
        )

        # Add inflows column to grid, filling missing indices with 0
        grid_result[str_col_total_flows_grid] = grid_result.index.map(
            flows_dict
        ).fillna(0)

    else:
        # Compute outflows (sum of trips starting from each origin)
        total_flows = (
            flows.group_by(str_col_origin)
            .agg(pl.col(str_col_n_trips).sum())
            .sort(str_col_origin)
        )

        # Create a mapping dictionary from origin index to total flows
        flows_dict = dict(
            zip(
                total_flows[str_col_origin].to_list(),
                total_flows[str_col_n_trips].to_list(),
            )
        )

        # Add outflows column to grid, filling missing indices with 0
        grid_result[str_col_total_flows_grid] = grid_result.index.map(
            flows_dict
        ).fillna(0)

    return grid_result


# VODAFONE FUNCTIONS WITH LATEST DATASET

#


def join_Tij_Vodafone_with_distance_matrix(
    df_od: pd.DataFrame | pl.DataFrame,
    df_distance_matrix: pd.DataFrame | pl.DataFrame,
    str_origin_od: str,  # NOTE: origin area (ITA.<code>)
    str_destination_od: str,  # NOTE: destination area (ITA.<code>)
    str_area_code_origin_col: str,
    str_area_code_destination_col: str,
):
    """
    Goal: Join the dataframe with the OD data with the distance matrix.
    Input:
        df_od: DataFrame with OD data
        df_distance_matrix: DataFrame with the distance matrix
    Output:
        df_od_with_distance: DataFrame with the OD data and the distance column
    """
    if isinstance(df_od, pd.DataFrame):
        df_od = pl.from_pandas(
            df_od
        )  # Convert to Polars DataFrame if it's a Pandas DataFrame
    else:
        pass

    if isinstance(df_distance_matrix, pd.DataFrame):
        df_distance_matrix = pl.from_pandas(
            df_distance_matrix
        )  # Convert to Polars DataFrame if it's a Pandas DataFrame
    else:
        pass

    df_od_with_distance = df_od.join(
        df_distance_matrix,
        left_on=[str_origin_od, str_destination_od],
        right_on=[str_area_code_origin_col, str_area_code_destination_col],
        how="left",
    )

    return df_od_with_distance


def add_column_area_code_OD_df_distance(
    df_distance_matrix,
    map_idx_cities_gdf_2_area_code: dict[int, str],
    str_col_origin: str,
    str_col_destination: str,
    str_area_code_origin_col: str = "AREA_CODE_ORIGIN",
    str_area_code_destination_col: str = "AREA_CODE_DESTINATION",
) -> pd.DataFrame:
    """
    Add the area code to the origin and destination columns of the distance matrix.
    Check that the OD be with the distance.
    """
    # Convert to Polars if it's pandas
    if isinstance(df_distance_matrix, pd.DataFrame):
        df_distance_matrix = pl.from_pandas(df_distance_matrix)

    # Get unique indices from the distance matrix
    unique_origins = set(df_distance_matrix[str_col_origin].to_list())
    unique_destinations = set(df_distance_matrix[str_col_destination].to_list())
    all_unique_indices = unique_origins.union(unique_destinations)

    # Check which indices are missing from the mapping
    missing_indices = all_unique_indices - set(map_idx_cities_gdf_2_area_code.keys())

    if missing_indices:
        print(
            f"Warning: {len(missing_indices)} indices are missing from the mapping dictionary:"
        )
        print(f"Missing indices: {sorted(missing_indices)}")
        print(
            f"Available mapping keys: {sorted(map_idx_cities_gdf_2_area_code.keys())}"
        )

    # Create the mapping using Polars
    df_distance_matrix = df_distance_matrix.with_columns(
        [
            pl.col(str_col_origin)
            .map_elements(
                lambda x: map_idx_cities_gdf_2_area_code.get(x, None),
                return_dtype=pl.Utf8,
            )
            .alias(str_area_code_origin_col),
            pl.col(str_col_destination)
            .map_elements(
                lambda x: map_idx_cities_gdf_2_area_code.get(x, None),
                return_dtype=pl.Utf8,
            )
            .alias(str_area_code_destination_col),
        ]
    )

    # Check for null values after mapping
    null_origins = df_distance_matrix[str_area_code_origin_col].null_count()
    null_destinations = df_distance_matrix[str_area_code_destination_col].null_count()

    if null_origins > 0 or null_destinations > 0:
        print(
            f"Warning: Found {null_origins} null values in {str_area_code_origin_col}"
        )
        print(
            f"Warning: Found {null_destinations} null values in {str_area_code_destination_col}"
        )

    return df_distance_matrix


def compute_difference_trips_col_day_baseline(
    Tij_dist: pl.DataFrame,
    Tij_dist_baseline: pl.DataFrame,
    str_col_n_trips: str,
    str_col_n_trips_baseline: str,
    str_col_difference_baseline: str,
    str_col_origin: str,
    str_col_destination: str,
    on_colums_flows_2_join: list,
) -> pl.DataFrame:
    """
    @Description: Compute the difference between the number of trips in the current day and the baseline day.
    @params Tij_dist: pl.DataFrame -> DataFrame with the number of trips for the current day
    @params Tij_dist_baseline: pl.DataFrame -> DataFrame with the number of trips for the baseline day
    @params str_col_n_trips: str -> name of the column with the number of trips in the current day
    @params str_col_n_trips_baseline: str -> name of the column with the number of trips in the baseline day
    @params str_col_difference_baseline: str -> name of the column to add with the difference between the number of trips in the current day and the baseline day
    @params str_col_origin: str -> name of the column with the origin index
    @params str_col_destination: str -> name of the column with the destination index
    @params on_colums_flows_2_join: list -> list of columns to join on
    @return: pl.DataFrame -> DataFrame with the difference between the number of trips in the current day and the baseline day
    """
    assert (
        str_col_n_trips in Tij_dist.columns
    ), f"{str_col_n_trips} not in Tij_dist columns"
    assert (
        str_col_n_trips_baseline in Tij_dist_baseline.columns
    ), f"{str_col_n_trips_baseline} not in Tij_dist_baseline columns"
    assert (
        str_col_origin in Tij_dist.columns
    ), f"{str_col_origin} not in Tij_dist columns"
    assert (
        str_col_destination in Tij_dist.columns
    ), f"{str_col_destination} not in Tij_dist columns"
    assert (
        str_col_origin in Tij_dist_baseline.columns
    ), f"{str_col_origin} not in Tij_dist_baseline columns"
    assert (
        str_col_destination in Tij_dist_baseline.columns
    ), f"{str_col_destination} not in Tij_dist_baseline columns"

    flows_merged = Tij_dist.join(
        Tij_dist_baseline[
            [str_col_origin, str_col_destination, str_col_n_trips_baseline]
        ],
        on=on_colums_flows_2_join,
        how="left",
    )

    flows_merged = flows_merged.with_columns(
        (pl.col(str_col_n_trips_baseline) - pl.col(str_col_n_trips)).alias(
            str_col_difference_baseline
        )
    )
    return flows_merged


####################################################
## INITIALIZE THEE AVERAGE STUDY OF DIFFUSION 1,2 ##
###########################################################
def concat_df_od_and_add_columns(
    list_files_od, s3, str_period_id_presenze, col_str_day_od, col_str_is_week
):
    """
    Concatenate the OD data from the list of files and add columns for day and weekday/weekend.
    Output: pl.DataFrame with the concatenated OD data and the added columns.

    """
    from data_preparation.v2.utils.flows_utils.VodafoneData import (
        extract_od_vodafone_from_bucket,
        add_column_is_week_and_str_day,
    )
    from tqdm import tqdm
    from data_preparation.v2.utils.utils import DATA_PREFIX

    for i, file in tqdm(
        enumerate(list_files_od), desc="Files OD Vodafone"
    ):  # for each file in the list of files
        df_od = extract_od_vodafone_from_bucket(s3, list_files_od, i)
        print("Processing file: ", file, f" iter: {i}")  # print the file name
        if file == f"{DATA_PREFIX}vodafone-aixpa/od-mask_202410.parquet":
            is_null_day = True
        else:
            is_null_day = False
        if is_null_day:
            continue

        if i == 0:
            df_od_concat = df_od
        else:
            df_od_concat = pl.concat([df_od_concat, df_od])

    df_od_concat = add_column_is_week_and_str_day(
        df_od=df_od_concat,
        str_period_id_presenze=str_period_id_presenze,
        col_str_day_od=col_str_day_od,
        col_str_is_week=col_str_is_week,
        is_null_day=False,
    )
    return df_od_concat


########### PIPELINE FILTERING DATAFRAME DIFFUSION 1,2 #############


def filter_flows_by_conditions(
    df: pl.DataFrame, tuple_filters: tuple, message: tuple[str] = []
) -> pl.DataFrame:
    """
    Function to filter the DataFrame based on a tuple of Polars expressions.
    Parameters:
        - df: Polars DataFrame to be filtered.
        - tuple_filters: Tuple of Polars expressions to filter the DataFrame.
    Returns:
        - df_filtered: Polars DataFrame after applying the filters.
    USAGE:
    - Keep only the relevant trip types in-in, out-in -> Just trips that are incoming to the Trentino region
    NOTE: suggested:
                    tuple_filters = (pl.col(str_trip_type_od) != "out-out",
                                    pl.col(str_trip_type_od) != "in-out")

    """
    assert len(tuple_filters) == len(
        message
    ), "Length of tuple_filters and message must be the same or message can be empty"
    df_filtered = df
    for i, filter_ in enumerate(tuple_filters):
        df_filtered = df_filtered.filter(filter_)
        print(
            f"Resulting OD after filtering {message[i]}: ", df_filtered.shape
        )  # print the shape of the resulting dataframe

    return df_filtered


def aggregate_flows(
    df: pl.DataFrame,
    list_columns_groupby: list,
    str_col_trips_to_be_aggregated: str,
    str_col_name_aggregated: str,
    method_aggregation: str = "sum",
):
    if method_aggregation == "sum":
        print("Aggregating by sum keeping fixed columns: ", list_columns_groupby)
        return aggregate_flows_by_sum(
            df,
            list_columns_groupby,
            str_col_trips_to_be_aggregated,
            str_col_name_aggregated,
        )
    elif method_aggregation == "average":
        print("Aggregating by average keeping fixed columns: ", list_columns_groupby)
        return aggregate_flows_by_average(
            df,
            list_columns_groupby,
            str_col_trips_to_be_aggregated,
            str_col_name_aggregated,
        )
    else:
        raise ValueError(
            f"Method {method_aggregation} not recognized. Use 'sum' or 'average'."
        )


def aggregate_flows_by_sum(
    df: pl.DataFrame,
    list_columns_groupby: list,
    str_col_trips_to_be_aggregated: str,
    str_col_name_aggregated: str,
):
    """
    Function to initialize the aggregation of trips based on specified filters and grouping columns.
    It starts from the raw dataframe from Vodafone and applies the filters to:
        - Group by the specified columns and aggregate the trips
    Parameters:
    - df: Polars DataFrame containing the raw trip data.
    - tuple_filters: Tuple of Polars expressions to filter the DataFrame.
    - list_columns_groupby: List of column names to group by.
    - str_col_trips_to_be_aggregated: Name of the column containing the trip counts to be aggregated.
    - str_col_name_aggregated: Name of the new column to store the aggregated trip counts.
    Returns:
        - df_agg: Polars DataFrame with aggregated trip counts NOTE: over all the classes that are not specified in the group by. (i.e. TRIP_TYPE,NATIONALITY_CLASS_ID)

    """
    for col in list_columns_groupby:
        if col not in df.columns:
            raise ValueError(f"Column {col} not found in DataFrame")
    df_sum = df.group_by(list_columns_groupby).agg(
        pl.col(str_col_trips_to_be_aggregated).sum().alias(str_col_name_aggregated)
    )
    return df_sum


def aggregate_flows_by_average(
    df: pl.DataFrame,
    columns_to_aggregate_over: list,
    str_col_trips_to_be_aggregated: str,
    str_col_name_aggregated: str,
):
    """
    Function to aggregate trips by summing over specified columns and computing the average over days.
    Parameters:
    - df: Polars DataFrame containing the trip data.
    - columns_to_aggregate_over: List of column names to group by for aggregation.
    - col_output_total_trips: Name of the column containing the trip counts to be summed.
    Returns:
        - df_agg: Polars DataFrame with aggregated trip counts and average trips over days
    """

    return df.group_by(columns_to_aggregate_over).agg(
        pl.col(str_col_trips_to_be_aggregated)
        .mean()
        .floor()
        .alias(str_col_name_aggregated)  # 3. compute average over days
    )


def pipeline_initial_df_flows_aggregation_on_dat_hour_user_weekday(
    df: pl.DataFrame,
    tuple_filters: tuple,
    message_filters: str,
    list_columns_groupby: list,
    str_col_trips_to_be_aggregated: str,
    str_col_name_aggregated: str,
    method_aggregation: str = "sum",
) -> pl.DataFrame:
    """
    Function to initialize the aggregation of trips based on specified filters and grouping columns.
    It starts from the raw dataframe from Vodafone and applies the filters to:
        - Keep only the relevant trip types in-in, out-in -> Just trips that are incoming to the Trentino region
        - Group by the specified columns and aggregate the trips
        - Compute average over days
    # NOTE: Filter by kind of trips -> just incoming trips in Trentino
    """
    if len(tuple_filters) != 0:
        Tij_dist = filter_flows_by_conditions(
            df=df, tuple_filters=tuple_filters, message=message_filters
        )
    else:
        Tij_dist = df
        pass

    # NOTE: Aggregate by sum over all the other columns that are not in the group by list
    Tij_dist = aggregate_flows(
        df=Tij_dist,
        list_columns_groupby=list_columns_groupby,  # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{str_day}_{is_weekday}
        str_col_trips_to_be_aggregated=str_col_trips_to_be_aggregated,
        str_col_name_aggregated=str_col_name_aggregated,
        method_aggregation=method_aggregation,
    )

    return Tij_dist
