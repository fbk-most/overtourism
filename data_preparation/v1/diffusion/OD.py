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

from collections import defaultdict
from json import dump, load
from os.path import exists
from pandas import DataFrame, read_parquet
import pandas as pd
import polars as pl
from geopandas import GeoDataFrame,sjoin,sjoin_nearest
from numpy import unique,array,fill_diagonal,errstate,sqrt,column_stack,newaxis,sum,logical_and
from numpy.linalg import norm
from haversine import haversine,haversine_vector

from tqdm import tqdm

from data_preparation.diffusion.GeometrySphere import choose_closest_point
# from VodafoneData import add_column_is_week_and_str_day,extract_date_info

def compute_masked_fluxes_from_OD_lists(df_fluxes, origin_indices, destination_indices, str_origin_col="origin", str_destination_col="destination"):
    """
        @params df_fluxes: DataFrame 
        @params origin_indices: list
            List of origin indices to include
        @params destination_indices: list
            List of destination indices to include
        @params str_origin_col: str
            The name of the column containing the origin indices
        @params str_destination_col: str
            The name of the column containing the destination indices
    """
    is_origin = [True if x in origin_indices else False for x in df_fluxes[str_origin_col].to_numpy()]
    is_destination = [True if x in destination_indices else False for x in df_fluxes[str_destination_col].to_numpy()]
    mask = logical_and(is_origin,is_destination)
    selected_fluxes = df_fluxes[mask].copy()
    if len(selected_fluxes) == 0:
        return df_fluxes
    else:
        return selected_fluxes



def compute_OD_grid_at_t(Grid:GeoDataFrame,
                         grid_idx_2_stop_idx:dict,
                         trips:DataFrame,               
                         t_start,
                         t_end):
    """
    Compute the OD matrix for the grid at a given time window.
    @param Grid: GeoDataFrame with the grid
    @param grid_idx_2_stop_idx: dictionary with the grid index and the stop index
    @param trips: DataFrame with the trips
    @param t_start: start time: in hours
    @param t_end: end time: hours
    @return: DataFrame with the OD matrix
    """

    origin = []
    destination = []
    count = []
    for grid_idx_i, row_idx_i in tqdm(Grid.iterrows(),desc=f"Computing OD matrix {t_start} - {t_end}", unit="row"):
        for grid_idx_j, row_idx_j in Grid.iterrows():
            if grid_idx_i == grid_idx_j:
                origin.append(grid_idx_i)
                destination.append(grid_idx_j)
                count.append(0)
            else:
                # Get the stops in the grid
                stops_i = grid_idx_2_stop_idx[grid_idx_i]
                stops_j = grid_idx_2_stop_idx[grid_idx_j]
                stops_ij = stops_i + stops_j
                # Get the trips stops that are either in the stop or start grid
                trips_ij = trips.loc[(trips["stop_id"].isin(stops_ij))]
                # 
                trips_ij_arrive_window = trips_ij.loc[(trips_ij["arrival_time"]>=t_start) & (trips_ij["arrival_time"]<=t_end)]
                trips_ij_start_and_arrive_window = trips_ij_arrive_window.loc[(trips_ij_arrive_window["departure_time"]>=t_start) & (trips_ij_arrive_window["departure_time"]<=t_end)]
                # Get the count
                count.append(len(trips_ij_start_and_arrive_window))
                # Get the origin and destination
                origin.append(grid_idx_i)
                destination.append(grid_idx_j)
        return DataFrame({"origin":origin,
                     "destination":destination,
                     "n_trips":count})


# Pipeline dictionaries

def pipeline_get_grid_idx_2_stop_idx(gdf_stops,
                                     Grid_gtfs,
                                     str_grid_id,
                                     str_stop_id,
                                     complete_path_grid_idx_2_stop_idx):
    """
        Function to get the grid_idx_2_stop_idx dictionary
        @params grid: GeoDataFrame with the grid
        @params complete_path_grid_idx_2_stop_idx: path to the grid_idx_2_stop_idx file
        @return: grid_idx_2_stop_idx dictionary
    """
    assert isinstance(gdf_stops, GeoDataFrame), f"gdf_stops should be a GeoDataFrame, instead {type(gdf_stops)}"
    assert isinstance(Grid_gtfs, GeoDataFrame), f"Grid_gtfs should be a GeoDataFrame, instead {type(Grid_gtfs)}"
    assert str_grid_id in Grid_gtfs.columns, f"grid_id = {str_grid_id} not in Grid_gtfs columns: {Grid_gtfs.columns}"
    assert str_stop_id in gdf_stops.columns, f"stop_id = {str_stop_id} not in gdf_stops columns: {gdf_stops.columns}"
    # check if the file exists
    if not exists(complete_path_grid_idx_2_stop_idx):
        gdf_stops_and_grid = sjoin(gdf_stops,Grid_gtfs,predicate="intersects")                                                                              # 
        grid_idx_2_stop_idx = gdf_stops_and_grid.groupby(str_grid_id)[str_stop_id].apply(list).to_dict()                                                              # grid 2 stop
        # save the grid_idx_2_stop_id dictionary
        with open(complete_path_grid_idx_2_stop_idx, "w") as f:
            dump(grid_idx_2_stop_idx, f, indent=4)
    else:
        with open(complete_path_grid_idx_2_stop_idx, "r") as f:
            grid_idx_2_stop_idx = load(f)
    return grid_idx_2_stop_idx

def pipeline_get_stop_idx_2_grid_idx(gdf_stops,
                                     Grid_gtfs,
                                     str_grid_id,
                                     str_stop_id,
                                     str_name_stop_id,
                                     complete_path_stop_idx_2_grid_idx,
                                     complete_path_name_stop_idx_2_grid_idx):
    """
        Function to get the grid_idx_2_stop_idx dictionary
        @params grid: GeoDataFrame with the grid
        @params complete_path_grid_idx_2_stop_idx: path to the grid_idx_2_stop_idx file
        @return: grid_idx_2_stop_idx dictionary
    """
    assert isinstance(gdf_stops, GeoDataFrame), f"gdf_stops should be a GeoDataFrame, instead {type(gdf_stops)}"
    assert isinstance(Grid_gtfs, GeoDataFrame), f"Grid_gtfs should be a GeoDataFrame, instead {type(Grid_gtfs)}"
    assert str_grid_id in Grid_gtfs.columns, f"grid_id = {str_grid_id} not in Grid_gtfs columns: {Grid_gtfs.columns}"
    assert str_stop_id in gdf_stops.columns, f"stop_id = {str_stop_id} not in gdf_stops columns: {gdf_stops.columns}"
    assert str_name_stop_id in gdf_stops.columns, f"stop_id = {str_name_stop_id} not in gdf_stops columns: {gdf_stops.columns}"
    # check if the file exists
    if not exists(complete_path_stop_idx_2_grid_idx):
        # Integer stop_id
        gdf_stops_and_grid = sjoin(gdf_stops,Grid_gtfs,predicate="intersects")                                                                              # 
        stop_idx_2_grid_idx = gdf_stops_and_grid.groupby(str_stop_id)[str_grid_id].apply(list).to_dict()                                                              # grid 2 stop
        # Name stop_id
        name_stop_idx_2_grid_idx = gdf_stops_and_grid.groupby(str_name_stop_id)[str_grid_id].apply(list).to_dict()                                                              # grid 2 stop
        # save the grid_idx_2_stop_id dictionary
        with open(complete_path_stop_idx_2_grid_idx, "w") as f:
            dump(stop_idx_2_grid_idx, f, indent=4)
        with open(complete_path_name_stop_idx_2_grid_idx, "w") as f:
            dump(name_stop_idx_2_grid_idx, f, indent=4)
    else:
        with open(complete_path_stop_idx_2_grid_idx, "r") as f:
            stop_idx_2_grid_idx = load(f)
        with open(complete_path_name_stop_idx_2_grid_idx, "r") as f:
            name_stop_idx_2_grid_idx = load(f)
    return stop_idx_2_grid_idx, name_stop_idx_2_grid_idx



def pipeline_get_stop_id_2_trip_id(stop_times,
                                   str_stop_id,
                                   str_trip_id,
                                   complete_path_stop_id_2_trip_id):
    """
        Function to get the stop_id_2_trip_id dictionary
        @params feed: gtfs feed
        @params complete_path_stop_id_2_trip_id: path to the stop_id_2_trip_id file
        @return: stop_id_2_trip_id dictionary
    """
    assert isinstance(complete_path_stop_id_2_trip_id, str), f"complete_path_stop_id_2_trip_id should be a string, instead {type(complete_path_stop_id_2_trip_id)}"
    assert str_stop_id in stop_times.columns, f"stop_id = {str_stop_id} not in stop_times columns: {stop_times.columns}"
    assert str_trip_id in stop_times.columns, f"trip_id = {str_trip_id} not in stop_times columns: {stop_times.columns}"
    # check if the file exists
    if not exists(complete_path_stop_id_2_trip_id):
        stop_id_2_trip_id = defaultdict(list)
        for stop_id, trip_id in zip(stop_times[str_stop_id], stop_times[str_trip_id]):
            stop_id_2_trip_id[stop_id].append(trip_id)
        # save the stop_id_2_trip_id dictionary
        with open(complete_path_stop_id_2_trip_id, "w") as f:
            dump(stop_id_2_trip_id, f, indent=4)
    else:
        with open(complete_path_stop_id_2_trip_id, "r") as f:
            stop_id_2_trip_id = load(f)
    return stop_id_2_trip_id

def pipeline_get_stop_id_2_route_id(trips,
                                    stop_id_2_trip_id,
                                    str_trip_id,
                                    str_route_id,
                                    complete_path_stop_id_2_route_id):
    """
        Function to get the stop_id_2_route_id dictionary
        @params trips: trips dataframe
        @params stop_id_2_trip_id: dictionary of stop_id and trip_id
        @params complete_path_stop_id_2_route_id: path to the stop_id_2_route_id file
        @return: stop_id_2_route_id dictionary
    """
    assert str_trip_id in trips.columns, f"trip_id = {str_trip_id} not in trips columns: {trips.columns}"
    assert str_route_id in trips.columns, f"route_id = {str_route_id} not in trips columns: {trips.columns}"
    if not isinstance(trips, DataFrame):
        trips = DataFrame(trips)
    assert isinstance(trips, DataFrame), f"trips should be a pandas dataframe, instead: {type(trips)}"
    assert isinstance(stop_id_2_trip_id, dict), f"stop_id_2_trip_id should be a dictionary, instead {type(stop_id_2_trip_id)}"
    
    if not exists(complete_path_stop_id_2_route_id):
        stop_id_2_route_id = defaultdict(list)
        # for each stop_id, get the route_id
        for stop_id in tqdm(stop_id_2_trip_id.keys(),desc=f"Building stop_id_2_route_id", unit="row"):
            # for each stop_id, get the route_id
            for idx,row in trips.iterrows():
                trip_id = row[str_trip_id]
                route_id = row[str_route_id]
                if route_id not in stop_id_2_route_id[stop_id]: 
                    # if the trip_id passes through the stop_id 
                    if trip_id in stop_id_2_trip_id[stop_id]:
                        stop_id_2_route_id[stop_id].append(route_id)
                    else:
                        pass
                # if the route_id has not yet been associated with the stop_id
                pass
        # save the stop_id_2_route_id dictionary
        with open(complete_path_stop_id_2_route_id, "w") as f:
            dump(stop_id_2_route_id, f, indent=4)
    else:
        with open(complete_path_stop_id_2_route_id, "r") as f:
            stop_id_2_route_id = load(f)
    return stop_id_2_route_id


### GRID TO ROUTE ###

def pipeline_get_grid_idx_2_route_idx(grid_idx_2_stop_idx,
                                      stop_id_2_route_id,
                                      complete_path_grid_idx_2_route_idx):
    """
    Function to compute the grid_idx_2_route_idx dictionary
    :param grid_idx_2_stop_idx: {grid_id:stop_id} grid 2 stop
    :param stop_id_2_route_id: {stop_id: route_id} -> useful to associate route to grid
    :return: {grid_id:[route_idces]} grid 2 route
    """
    if not exists(complete_path_grid_idx_2_route_idx):
        grid_idx_2_route_idx = dict()
        for grid_idx, stop_idces in tqdm(grid_idx_2_stop_idx.items(),desc="Building grid to route idx", unit="row"):
            grid_idx_2_route_idx[grid_idx] = []
            for stop_idx in stop_idces:
                if stop_idx in stop_id_2_route_id.keys():
                    route_idces = stop_id_2_route_id[stop_idx]
                    grid_idx_2_route_idx[grid_idx] += route_idces
            grid_idx_2_route_idx[grid_idx] = list(unique(grid_idx_2_route_idx[grid_idx]))
        # save the grid_idx_2_route_idx dictionary
        with open(complete_path_grid_idx_2_route_idx, "w") as f:
            dump(grid_idx_2_route_idx, f, indent=4)
    else:
        with open(complete_path_grid_idx_2_route_idx, "r") as f:
            grid_idx_2_route_idx = load(f)
    return grid_idx_2_route_idx

## GRID TO CITY ##
def pipeline_get_grid_idx_2_city_idx(grid_gdf,
                                     cities_gdf,
                                     grid_idx_col,
                                     complete_path_grid_idx_2_city_idx):
    """
    Function to compute the grid_idx_2_city_idx dictionary
    :param grid_gdf: GeoDataFrame with the grid 
    :param cities_gdf: GeoDataFrame with the cities
    :param grid_idx_2_route_idx: {grid_id:[city_names]} for which there is an intersection.
    """
    if exists(complete_path_grid_idx_2_city_idx):
        with open(complete_path_grid_idx_2_city_idx, 'r') as f:
            grid_idx_2_city_name = load(f)
        return grid_idx_2_city_name
    else:
        # Perform a spatial join to find the intersection between grid and cities
        spatial_join = sjoin(grid_gdf, cities_gdf, predicate='intersects')
        # Group by grid id and aggregate city names into lists
        grid_idx_2_city_name = spatial_join.groupby(grid_idx_col)['city_name'].agg(list).to_dict()
        # Create a new dictionary to store the grid id to city names mapping
        return grid_idx_2_city_name

# TRANSPORT NETWORK TO ROUTE (public transport) # 

def assign_stops_to_routes(gdf_public_transport,
                            gdf_stops,
                            str_route_idx,
                            str_stop_idx,
                            stop_id_2_route_id,
                            crs = "EPSG:3857",
                            buffer = 3
                            ):
    """
        @param gdf_public_transport: GeoDataFrame with the public transport network
        @param gdf_stops: GeoDataFrame with the stops
        @param str_route_idx: name of the column with the route id
        @param str_stop_idx: name of the column with the stop id
        @param stop_id_2_route_id: dictionary with the stop id as key and the route id as value
        @param crs: coordinate reference system
        @param buffer: buffer size to use for the spatial join
        @return: gdf_public_transport_and_stops: GeoDataFrame with the public transport network and the stops
        ------------------------------------------------------------------------------------------------------
        @describe:
        Associates the route to the stops roads.
        It does so by looking at the stops that form a route:
        Example:
            route1 = [stop1, stop2, stop3] -> stop_id_2_route_id[stop1] = route1, stop_id_2_route_id[stop2] = route1 ecc.
            stop1 is joined to road1 ->  gdf_public_transport_and_stops[str_route_idx] = route1 where gdf_public_transport_and_stops[str_transport_idx] = road1
    """
    if "index_right" in gdf_public_transport.columns:
        gdf_public_transport = gdf_public_transport.drop(columns=["index_right"])

    gdf_public_transport = gdf_public_transport.to_crs(crs)
    gdf_stops = gdf_stops.to_crs(crs)    
    gdf_public_transport_and_stops = sjoin_nearest(gdf_public_transport,gdf_stops, how='left', distance_col='distance',max_distance=buffer)
    gdf_public_transport_and_stops[str_route_idx] = gdf_public_transport_and_stops[str_stop_idx].apply(lambda x: stop_id_2_route_id[x] if x in stop_id_2_route_id else None)
    return gdf_public_transport_and_stops    


def assign_grid_2_transport_gdf(gdf_transport,Grid_gtfs,str_col_is_droppable,columns_2_keep_transport,crs_proj = "EPSG:3857",crs = "EPSG:4326"):
    """
        Assign the grid to the transport gdf

    """
    if "index_right" in gdf_transport.columns:
        gdf_transport = gdf_transport.drop(columns=["index_right"])
    Grid_gtfs.to_crs(crs_proj,inplace=True)
    gdf_transport = gdf_transport.to_crs(crs_proj)
    gdf_transport = sjoin(gdf_transport,Grid_gtfs,how="left")
    gdf_transport = gdf_transport.loc[gdf_transport[str_col_is_droppable] == True]
    gdf_transport = gdf_transport[columns_2_keep_transport]
    gdf_transport = gdf_transport.to_crs(crs)
    return gdf_transport


def pipeline_route_idx_2_graph_idx(gdf_public_transport,
                                   str_transport_idx,
                                   str_route_idx,
                                   complete_path_graph_idx_2_route_idx,
                                   complete_path_route_idx_2_graph_idx,
                                   type_route,
                                   type_transport
                                   ):
    """
    Function to associate the route id to the graph id
    :param gdf_public_transport: gdf of the public transport network
    :param gdf_stops: gdf of the stops
    :param str_transport_idx: name of the column with the transport id
    :param str_route_idx: name of the column with the route id
    :param str_stop_idx: name of the column with the stop id
    :param stop_id_2_route_id: dictionary with the stop id as key and the route id as value
    :param complete_path_graph_idx_2_route_idx: path to the json file where to save the graph id to route id
    :param complete_path_route_idx_2_graph_idx: path to the json file where to save the route id to graph id
    :return: route_idx_2_graph_idx: dictionary with the route id as key and the graph id as value

    """
    if exists(complete_path_route_idx_2_graph_idx) and exists(complete_path_graph_idx_2_route_idx):
        with open(complete_path_route_idx_2_graph_idx, 'r') as f:
            route_idx_2_graph_idx = load(f)
        with open(complete_path_graph_idx_2_route_idx, 'r') as f:
            graph_idx_2_route_idx = load(f)
        return route_idx_2_graph_idx, graph_idx_2_route_idx
    # Associate stop to roads
    else:
        route_idx_2_graph_idx = defaultdict(list)
        graph_idx_2_route_idx = defaultdict(list)
        for i in tqdm(range(len(gdf_public_transport)),desc= "Building route to graph idx", unit="row"):
            routes = gdf_public_transport[str_route_idx].iloc[i]
            graph_road_value = gdf_public_transport[str_transport_idx].iloc[i]

            if isinstance(routes, list):
                for route_key in routes:
                    if isinstance(graph_road_value, list):
                        route_idx_2_graph_idx[type_route(route_key)].append([type_transport(g_key) for g_key in graph_road_value])
                    else:
                        route_idx_2_graph_idx[type_route(route_key)].append(type_transport(graph_road_value))
            else:
                route_key = routes
                route_idx_2_graph_idx[type_route(route_key)].append(type_transport(graph_road_value))
            
            if isinstance(graph_road_value, list):
                for graph_key in graph_road_value:
                    if isinstance(routes, list):
                        graph_idx_2_route_idx[type_transport(graph_key)].append([type_route(r_key) for r_key in routes])
                    else:
                        graph_idx_2_route_idx[type_transport(graph_key)].append(type_route(routes))
            else:
                graph_key = graph_road_value
                graph_idx_2_route_idx[type_transport(graph_key)].append(type_route(route_key))
        # Save the route id to graph id
        with open(complete_path_route_idx_2_graph_idx, 'w') as f:
            dump(route_idx_2_graph_idx, f)
        # Save the graph id to route id
        with open(complete_path_graph_idx_2_route_idx, 'w') as f:
            dump(graph_idx_2_route_idx, f)
    return route_idx_2_graph_idx, graph_idx_2_route_idx



####################### DIRECTION MATRIX ###########################

def compute_direction_matrix_optimized(grid, 
                                     str_centroid_x_col,
                                     str_centroid_y_col,
                                     complete_path_direction_distance_df):
    '''
    Vectorized computation of direction and distance matrices.
    
    Parameters:
        grid: GeoDataFrame with grid points
        str_centroid_x_col: Column name for x coordinates
        str_centroid_y_col: Column name for y coordinates
        complete_path_direction_distance_df: Path to cached results
        
    Returns:
        direction_matrix: Dictionary of normalized direction vectors
        distance_matrix: Dictionary of haversine distances
    ''' 
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
        with errstate(divide='ignore', invalid='ignore'):
            normalized_x = x_diff / magnitudes
            normalized_y = y_diff / magnitudes
        
        # Fix NaN values (diagonal elements where i == j)
        fill_diagonal(normalized_x, 0)
        fill_diagonal(normalized_y, 0)
        
        # Create direction matrix as dictionary of dictionaries
        direction_matrix = {}
        for i in tqdm(range(n),desc="Building direction matrix", unit="row"):
            direction_matrix[i] = {}
            for j in range(n):
                if i != j:  # Skip self-connections
                    direction_matrix[i][j] = array([normalized_x[i, j], normalized_y[i, j]])
                else:
                    direction_matrix[i][j] = array([0, 0])  # Self to self has no direction
        
        # For haversine computation, prepare coordinates in the required format
        coords1 = [(y_coords[i], x_coords[i]) for i in range(n)]
        coords2_matrix = [[(y_coords[j], x_coords[j]) for j in range(n)] for i in tqdm(range(n),desc="coords 2 matrix", unit="row")]
        
        # Use haversine_vector for batch computation if available
        # Otherwise, fall back to dictionary comprehension
        try:
            # Check if haversine_vector is available (newer versions of haversine)
            distance_matrix_array = array([haversine_vector(coords1[i:i+1] * n, coords2_matrix[i]) for i in tqdm(range(n),desc="Building distance matrix array", unit="row")])
            
            # Convert array to dictionary format
            distance_matrix = {}
            for i in range(n):
                distance_matrix[i] = {j: distance_matrix_array[i][j] for j in range(n)}
                
        except (AttributeError, TypeError):
            # Fall back to original method if vectorized version not available
            distance_matrix = {i: {j: haversine((y_coords[i], x_coords[i]),
                                              (y_coords[j], x_coords[j])) 
                               for j in range(n)} for i in tqdm(range(n),desc="Building distance matrix dict", unit="row")}
        
        return direction_matrix, distance_matrix
def direction_distance_2_df(direction_matrix,
                            distance_matrix,
                            complete_path_direction_distance_df,
                            str_i_col = "i",
                            str_j_col = "j",
                            str_dir_vector_col = "dir_vector",
                            str_distance_col = "distance"):
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

def compute_distance_matrix_numpy(grid_gdf, x_col, y_col):
    """
    Ultra-fast Euclidean distance matrix computation using NumPy vectorization.
    
    Parameters:
        grid_gdf: GeoDataFrame with point coordinates
        x_col: Name of x-coordinate column
        y_col: Name of y-coordinate column
        
    Returns:
        distance_matrix: 2D NumPy array with pairwise distances
    """
    # Extract coordinates as NumPy arrays
    points = column_stack([grid_gdf[x_col].values, grid_gdf[y_col].values])
    
    # Compute pairwise squared differences
    diff = points[:, newaxis, :] - points[newaxis, :, :]
    
    # Compute Euclidean distances using vectorized operations
    distance_matrix = sqrt(sum(diff**2, axis=-1))
    
    return distance_matrix

def add_population_column_2_distance_matrix(df_distance_matrix,
                                        cities_gdf,
                                        str_col_i,
                                        str_col_j,
                                        str_population_col = "Popolazione_Totale",
                                        str_population_i_col = "population_i",
                                        str_population_j_col = "population_j"):
    """
        Add population columns to the distance matrix DataFrame.
        
        Parameters:
        df_distance_matrix (pd.DataFrame): The distance matrix DataFrame.
        cities_gdf (GeoDataFrame): The GeoDataFrame containing city population data.
        
        Returns:
        pd.DataFrame: The updated distance matrix with population columns.
    """
    # Map population data to the distance matrix
    df_distance_matrix[str_population_i_col] = df_distance_matrix[str_col_i].map(cities_gdf[str_population_col])
    df_distance_matrix[str_population_j_col] = df_distance_matrix[str_col_j].map(cities_gdf[str_population_col])
    return df_distance_matrix


######################## DIRECTION MATRIX END ########################
######################################################################
########################## OD MATRIX #################################
def compute_total_flows_from_flow(flows,
                                  grid,
                                  is_in_flows,
                                  str_col_total_flows_grid,
                                  str_col_origin = "i",
                                  str_col_destination = "j",
                                  str_col_n_trips = "n_trips"):
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
        total_flows = flows.group_by(str_col_destination).agg(
            pl.col(str_col_n_trips).sum()
        ).sort(str_col_destination)
        
        # Create a mapping dictionary from destination index to total flows
        flows_dict = dict(zip(
            total_flows[str_col_destination].to_list(), 
            total_flows[str_col_n_trips].to_list()
        ))
        
        # Add inflows column to grid, filling missing indices with 0
        grid_result[str_col_total_flows_grid] = grid_result.index.map(flows_dict).fillna(0)
        
    else:
        # Compute outflows (sum of trips starting from each origin)
        total_flows = flows.group_by(str_col_origin).agg(
            pl.col(str_col_n_trips).sum()
        ).sort(str_col_origin)
        
        # Create a mapping dictionary from origin index to total flows
        flows_dict = dict(zip(
            total_flows[str_col_origin].to_list(), 
            total_flows[str_col_n_trips].to_list()
        ))
        
        # Add outflows column to grid, filling missing indices with 0
        grid_result[str_col_total_flows_grid] = grid_result.index.map(flows_dict).fillna(0)
    
    return grid_result

# VODAFONE FUNCTIONS WITH LATEST DATASET

#



def join_Tij_Vodafone_with_distance_matrix(df_od: pd.DataFrame | pl.DataFrame,
                                           df_distance_matrix: pd.DataFrame | pl.DataFrame,
                                           str_origin_od:str,                                   # NOTE: origin area (ITA.<code>)
                                           str_destination_od:str,                              # NOTE: destination area (ITA.<code>)    
                                           str_area_code_origin_col:str,
                                           str_area_code_destination_col:str):
    """
        Goal: Join the dataframe with the OD data with the distance matrix.
        Input:
            df_od: DataFrame with OD data
            df_distance_matrix: DataFrame with the distance matrix
        Output:
            df_od_with_distance: DataFrame with the OD data and the distance column
    """
    if isinstance(df_od, pd.DataFrame):
        df_od = pl.from_pandas(df_od)  # Convert to Polars DataFrame if it's a Pandas DataFrame
    else:
        pass

    if isinstance(df_distance_matrix, pd.DataFrame):
        df_distance_matrix = pl.from_pandas(df_distance_matrix)  # Convert to Polars DataFrame if it's a Pandas DataFrame
    else:
        pass

    df_od_with_distance = df_od.join(df_distance_matrix, 
                                     left_on=[str_origin_od, str_destination_od], 
                                     right_on=[str_area_code_origin_col, str_area_code_destination_col], 
                                     how='left')
    
    return df_od_with_distance


def add_column_area_code_OD_df_distance(df_distance_matrix,
                                        map_idx_cities_gdf_2_area_code:dict[int,str],
                                        str_col_origin:str,
                                        str_col_destination:str,
                                        str_area_code_origin_col:str = "AREA_CODE_ORIGIN",
                                        str_area_code_destination_col:str = "AREA_CODE_DESTINATION",
                                        ) -> pd.DataFrame:
    """
        Add the area code to the origin and destination columns of the distance matrix.

    """
    df_distance_matrix[str_area_code_origin_col] = df_distance_matrix[str_col_origin].map(map_idx_cities_gdf_2_area_code)
    df_distance_matrix[str_area_code_destination_col] = df_distance_matrix[str_col_destination].map(map_idx_cities_gdf_2_area_code)
    return df_distance_matrix


# Check that the OD be with the distance.

def add_column_area_code_OD_df_distance(df_distance_matrix,
                                        map_idx_cities_gdf_2_area_code: dict[int, str],
                                        str_col_origin: str,
                                        str_col_destination: str,
                                        str_area_code_origin_col: str = "AREA_CODE_ORIGIN",
                                        str_area_code_destination_col: str = "AREA_CODE_DESTINATION",
                                        ) -> pd.DataFrame:
    """
    Add the area code to the origin and destination columns of the distance matrix.
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
        print(f"Warning: {len(missing_indices)} indices are missing from the mapping dictionary:")
        print(f"Missing indices: {sorted(missing_indices)}")
        print(f"Available mapping keys: {sorted(map_idx_cities_gdf_2_area_code.keys())}")
    
    # Create the mapping using Polars
    df_distance_matrix = df_distance_matrix.with_columns([
        pl.col(str_col_origin).map_elements(
            lambda x: map_idx_cities_gdf_2_area_code.get(x, None),
            return_dtype=pl.Utf8
        ).alias(str_area_code_origin_col),
        
        pl.col(str_col_destination).map_elements(
            lambda x: map_idx_cities_gdf_2_area_code.get(x, None),
            return_dtype=pl.Utf8
        ).alias(str_area_code_destination_col)
    ])
    
    # Check for null values after mapping
    null_origins = df_distance_matrix[str_area_code_origin_col].null_count()
    null_destinations = df_distance_matrix[str_area_code_destination_col].null_count()
    
    if null_origins > 0 or null_destinations > 0:
        print(f"Warning: Found {null_origins} null values in {str_area_code_origin_col}")
        print(f"Warning: Found {null_destinations} null values in {str_area_code_destination_col}")
    
    return df_distance_matrix



def compute_difference_trips_col_day_baseline(Tij_dist: pl.DataFrame, 
                                                Tij_dist_baseline: pl.DataFrame,
                                                str_col_n_trips: str, 
                                                str_col_n_trips_baseline: str,
                                                str_col_difference_baseline: str,
                                                str_col_origin: str, str_col_destination: str,
                                                on_colums_flows_2_join: list) -> pl.DataFrame:
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
    assert str_col_n_trips in Tij_dist.columns, f"{str_col_n_trips} not in Tij_dist columns"
    assert str_col_n_trips_baseline in Tij_dist_baseline.columns, f"{str_col_n_trips_baseline} not in Tij_dist_baseline columns"
    assert str_col_origin in Tij_dist.columns, f"{str_col_origin} not in Tij_dist columns"
    assert str_col_destination in Tij_dist.columns, f"{str_col_destination} not in Tij_dist columns"
    assert str_col_origin in Tij_dist_baseline.columns, f"{str_col_origin} not in Tij_dist_baseline columns"
    assert str_col_destination in Tij_dist_baseline.columns, f"{str_col_destination} not in Tij_dist_baseline columns"
    
    flows_merged = Tij_dist.join(
        Tij_dist_baseline[[str_col_origin, str_col_destination, str_col_n_trips_baseline]], 
        on= on_colums_flows_2_join, 
        how="left"
    )
    
    flows_merged = flows_merged.with_columns(
        (pl.col(str_col_n_trips_baseline) - pl.col(str_col_n_trips)).alias(str_col_difference_baseline)
    )
    return flows_merged

####################################################
## INITIALIZE THEE AVERAGE STUDY OF DIFFUSION 1,2 ## 
###########################################################
def concat_df_od_and_add_columns(list_files_od, s3, str_period_id_presenze, col_str_day_od, col_str_is_week):
    """ 
        Concatenate the OD data from the list of files and add columns for day and weekday/weekend. 
        Output: pl.DataFrame with the concatenated OD data and the added columns.

    """
    from data_preparation.diffusion.VodafoneData import extract_od_vodafone_from_bucket, add_column_is_week_and_str_day
    from tqdm import tqdm
    from data_preparation.utils import DATA_PREFIX

    for i,file in tqdm(enumerate(list_files_od),desc="Files OD Vodafone"):                                                                                           # for each file in the list of files
        df_od = extract_od_vodafone_from_bucket(s3,list_files_od, i)
        print("Processing file: ", file,f" iter: {i}")                                                                                                                                          # print the file name
        if file == f'{DATA_PREFIX}vodafone-aixpa/od-mask_202410.parquet':
            is_null_day = True
        else:
            is_null_day = False
        if is_null_day:
            continue

        if i == 0:
            df_od_concat = df_od
        else:
            df_od_concat = pl.concat([df_od_concat, df_od])

    df_od_concat = add_column_is_week_and_str_day(df_od = df_od_concat,
                                            str_period_id_presenze = str_period_id_presenze,
                                            col_str_day_od = col_str_day_od,
                                            col_str_is_week = col_str_is_week,
                                            is_null_day = False)
    return df_od_concat


########### PIPELINE FILTERING DATAFRAME DIFFUSION 1,2 #############

def filter_flows_by_conditions(df: pl.DataFrame,
                               tuple_filters: tuple,
                               message:tuple[str] = []
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
    assert len(tuple_filters) == len(message), "Length of tuple_filters and message must be the same or message can be empty"
    df_filtered = df
    for i,filter_ in enumerate(tuple_filters):
        df_filtered = df_filtered.filter(filter_)
        print(f"Resulting OD after filtering {message[i]}: ", df_filtered.shape)                                                                                                   # print the shape of the resulting dataframe

    return df_filtered

def aggregate_flows(df: pl.DataFrame, 
                    list_columns_groupby: list, 
                    str_col_trips_to_be_aggregated: str, 
                    str_col_name_aggregated: str,
                    method_aggregation: str = "sum"):
    if method_aggregation == "sum":
        print("Aggregating by sum keeping fixed columns: ", list_columns_groupby)
        return aggregate_flows_by_sum(df, 
                           list_columns_groupby, 
                           str_col_trips_to_be_aggregated, 
                           str_col_name_aggregated)
    elif method_aggregation == "average":
        print("Aggregating by average keeping fixed columns: ", list_columns_groupby)
        return aggregate_flows_by_average(df, 
                    list_columns_groupby,
                    str_col_trips_to_be_aggregated,
                    str_col_name_aggregated)
    else:
        raise ValueError(f"Method {method_aggregation} not recognized. Use 'sum' or 'average'.")
    

def aggregate_flows_by_sum(df: pl.DataFrame, 
                           list_columns_groupby: list, 
                           str_col_trips_to_be_aggregated: str, 
                           str_col_name_aggregated: str):
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

def aggregate_flows_by_average(df: pl.DataFrame, 
                            columns_to_aggregate_over: list,
                            str_col_trips_to_be_aggregated: str,
                            str_col_name_aggregated: str):
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
                                                        pl.col(str_col_trips_to_be_aggregated).mean().floor().alias(str_col_name_aggregated)                                                               # 3. compute average over days
                                                        )
    



def pipeline_initial_df_flows_aggregation_on_dat_hour_user_weekday(df: pl.DataFrame,
                                                                   tuple_filters: tuple,
                                                                   message_filters: str,
                                                                   list_columns_groupby: list,
                                                                   str_col_trips_to_be_aggregated: str,
                                                                   str_col_name_aggregated: str,
                                                                   method_aggregation: str = "sum"
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
        Tij_dist = filter_flows_by_conditions(df = df,
                                            tuple_filters = tuple_filters,
                                            message = message_filters
                                    )
    else:
        Tij_dist = df
        pass

    # NOTE: Aggregate by sum over all the other columns that are not in the group by list
    Tij_dist = aggregate_flows(df = Tij_dist, 
                                list_columns_groupby = list_columns_groupby,            # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{str_day}_{is_weekday}
                                str_col_trips_to_be_aggregated = str_col_trips_to_be_aggregated,
                                str_col_name_aggregated = str_col_name_aggregated,
                                method_aggregation= method_aggregation)

    return Tij_dist
