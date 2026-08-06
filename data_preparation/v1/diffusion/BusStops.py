from geopandas import GeoDataFrame,read_file
from shapely.geometry import Point 
from os.path import exists,join
from data_preparation.diffusion.OD import *
from data_preparation.diffusion.set_config import convert_values_inside_dict
from data_preparation.diffusion.Grid import is_the_geometry_inside_cell_droppable,count_number_stops_per_grid

def pipeline_get_gdf_stop(stops,complete_path_gdf_stops,crs = "EPSG:4326"):
    """
        Function to get the gdf of the stops
        @params stops: stops dataframe
        @params complete_path_gdf_stops: path to the gdf stops file
        @return: gdf_stops: GeoDataFrame with the stops
    """    
    if not exists(complete_path_gdf_stops):
        stops["geometry"] = stops.apply(lambda x: Point(x.stop_lon, x.stop_lat), axis=1)
        gdf_stops = GeoDataFrame(stops, geometry="geometry",crs=crs)
        gdf_stops.to_file(complete_path_gdf_stops, driver="GeoJSON")
    else:
        gdf_stops = read_file(complete_path_gdf_stops)
        gdf_stops = gdf_stops.to_crs(crs)
    return gdf_stops


## --------------- FILTERING STOPS AND TRIPS BY TIME --------------- ##

def filter_trips_by_time(trip_stats, 
                         time_vector_OD, 
                         str_trip_idx,
                         end_time_col="end_time",
                         start_time_col="start_time"):
    """
    Filter trips based on the end time within a specified time range.
    
    Parameters:
    - trip_stats: DataFrame containing trip statistics.
    - str_day: The day for which the trips are being filtered.
    - time_vector_OD: A vector of timedeltas representing the time range.
    - str_trip_idx: The column name for trip identifiers.
    
    Returns:
    - A DataFrame of trips that fall within the specified time range.
    """
    copy_trip_stats = trip_stats.copy()
    
    # Convert timedelta to hours for easier handling
    start_hours = time_vector_OD[0].total_seconds() / 3600
    end_hours = time_vector_OD[-1].total_seconds() / 3600
    
    # Create time objects for comparison
    start_time = pd.Timestamp(f"1900-01-01 {int(start_hours):02d}:{int((start_hours % 1) * 60):02d}:00").time()
    end_time = pd.Timestamp(f"1900-01-01 {int(end_hours):02d}:{int((end_hours % 1) * 60):02d}:00").time()
    
    # Handle different formats of the end_time column
    if copy_trip_stats[end_time_col].dtype == 'object':
        # If it's string format like "07:30:00"
        try:
            copy_trip_stats[f"{end_time_col}_parsed"] = pd.to_datetime(copy_trip_stats[end_time_col], format='%H:%M:%S').dt.time
        except:
            copy_trip_stats[f"{end_time_col}_parsed"] = pd.to_datetime(copy_trip_stats[end_time_col]).dt.time
    elif 'datetime' in str(copy_trip_stats[end_time_col].dtype):
        # If it's already datetime, extract time
        copy_trip_stats[f"{end_time_col}_parsed"] = pd.to_datetime(copy_trip_stats[end_time_col]).dt.time
    else:
        # If it's numeric (seconds since midnight), convert to time
        copy_trip_stats[f"{end_time_col}_parsed"] = pd.to_datetime(copy_trip_stats[end_time_col], unit='s').dt.time
    
    # Create mask for filtering
    mask = (copy_trip_stats[f"{end_time_col}_parsed"] >= start_time) & (copy_trip_stats[f"{end_time_col}_parsed"] <= end_time)
    
    # Filter and return
    users = copy_trip_stats[mask][str_trip_idx].unique().tolist()
    return copy_trip_stats[copy_trip_stats[str_trip_idx].isin(users)]

def filter_stop_times_by_time(stop_times, start_interval, end_interval, str_trip_idx, end_time_col="departure_time"):
    """
        Filter stop times based on a specified time interval.
    """
    copy_stop_times = stop_times.copy()
    
    # Convert timedelta intervals to hours for easier handling
    if isinstance(start_interval, pd.Timedelta):
        start_hours = start_interval.total_seconds() / 3600
        end_hours = end_interval.total_seconds() / 3600
    else:
        start_hours = start_interval
        end_hours = end_interval
    
    # Create time objects for comparison
    start_time = pd.Timestamp(f"1900-01-01 {int(start_hours):02d}:{int((start_hours % 1) * 60):02d}:00").time()
    end_time = pd.Timestamp(f"1900-01-01 {int(end_hours):02d}:{int((end_hours % 1) * 60):02d}:00").time()
    
    # Handle different formats of the departure_time column
    if copy_stop_times[end_time_col].dtype == 'object':
        # If it's string format like "07:30:00"
        copy_stop_times[f"{end_time_col}_parsed"] = pd.to_datetime(copy_stop_times[end_time_col], format='%H:%M:%S').dt.time
    elif 'datetime' in str(copy_stop_times[end_time_col].dtype):
        # If it's already datetime, extract time
        copy_stop_times[f"{end_time_col}_parsed"] = pd.to_datetime(copy_stop_times[end_time_col]).dt.time
    else:
        # If it's numeric (seconds since midnight), convert to time
        copy_stop_times[f"{end_time_col}_parsed"] = pd.to_datetime(copy_stop_times[end_time_col], unit='s').dt.time
    
    # Create mask for filtering
    mask = (copy_stop_times[f"{end_time_col}_parsed"] >= start_time) & (copy_stop_times[f"{end_time_col}_parsed"] <= end_time)
    
    # Filter and return
    users = copy_stop_times[mask][str_trip_idx].unique().tolist()
    return copy_stop_times[copy_stop_times[str_trip_idx].isin(users)]

## ----------------------- ASSOCIATE STOPS, ROUTES, TRIPS TO GRID ----------------------- ##

def pipeline_associate_stops_trips_routes_2_grid(config,
                                                 stop_times,
                                                 trips,
                                                 gdf_stops,
                                                 Grid_gtfs,
                                                 str_grid_idx,
                                                 str_stop_idx, 
                                                 str_trip_idx, 
                                                 str_route_idx,
                                                 str_name_stop_id,
                                                 type_grid_idx,
                                                 type_stop_idx,
                                                 type_trip_idx,
                                                 type_route_idx,                                                 
                                                 str_col_n_stops = "n_stops",
                                                 str_prefix_complete_path = "complete_path",
                                                  str_dir_output_date = "output",
                                                  str_name_stop_2_trip = "stop_id_2_trip_id",
                                                  str_name_stop_2_route = "stop_id_2_route_id",
                                                  str_name_grid_2_stop = "grid_idx_2_stop_idx",
                                                  str_name_stop_2_grid = "stop_idx_2_grid_idx",
                                                  str_name_name_stop_2_grid = "name_stop_idx_2_grid_idx",
                                                  str_name_grid_2_route = "grid_idx_2_route_idx"):
    """
        @description: Function to associate stops, trips and routes to grid cells.
        This function aims to generate the map of stops, trips and routes to grid cells.
        This is needed for the creation of flows between different grid cells. In pipeline_associate_route_trips_2_flows
    """
    # NOTE: Stop -> Trip and Routes
    config[f"{str_prefix_complete_path}_{str_name_stop_2_trip}"] = join(str_dir_output_date,f"{str_name_stop_2_trip}.json")                                                          # NOTE: Path -> trip_2_grid
    config[f"{str_prefix_complete_path}_{str_name_stop_2_route}"] = join(str_dir_output_date,f"{str_name_stop_2_route}.json")                                                        # NOTE: Path -> route_2_grid
    # NOTE: Grid and Stops
    config[f"{str_prefix_complete_path}_{str_name_grid_2_stop}"] = join(str_dir_output_date,f"{str_name_grid_2_stop}.json")                                                          # NOTE: Path -> grid_2_stop
    config[f"{str_prefix_complete_path}_{str_name_stop_2_grid}"] = join(str_dir_output_date,f"{str_name_stop_2_grid}.json")                                                          # NOTE: Path -> stop_2_grid
    config[f"{str_prefix_complete_path}_{str_name_name_stop_2_grid}"] = join(str_dir_output_date,f"{str_name_name_stop_2_grid}.json")                                                # NOTE: Path -> name_stop_2_grid
    # NOTE: Grid and Routes
    config[f"{str_prefix_complete_path}_{str_name_grid_2_route}"] = join(str_dir_output_date,f"{str_name_grid_2_route}.json")                                                        # NOTE: Path -> grid_2_route
    print(f"Compute grid_2_stop: ",config[f"{str_prefix_complete_path}_{str_name_grid_2_stop}"])                                                                                                                          #
    # NOTE: Grid 2 Stop
    grid_idx_2_stop_idx = pipeline_get_grid_idx_2_stop_idx(gdf_stops,
                                                           Grid_gtfs,
                                                           str_grid_idx,
                                                           str_stop_idx,
                                                           config[f"{str_prefix_complete_path}_{str_name_grid_2_stop}"])                                                             # NOTE: Dict -> {grid_id: [stop_id]} grid 2 stop
    grid_idx_2_stop_idx = convert_values_inside_dict(grid_idx_2_stop_idx,
                                                     type_grid_idx,type_stop_idx)                                                                                                    # NOTE: Convert -> the values of the dictionary to the right type NOTE: needed if want to access geodataframes correctly                                                          
    # NOTE: Stop 2 Grid
    stop_idx_2_grid_idx, name_stop_idx_2_grid_idx = pipeline_get_stop_idx_2_grid_idx(gdf_stops,
                                                                                    Grid_gtfs,
                                                                                    str_grid_idx,
                                                                                    str_stop_idx,
                                                                                    str_name_stop_id,
                                                                                    config[f"{str_prefix_complete_path}_{str_name_stop_2_grid}"],
                                                                                    config[f"{str_prefix_complete_path}_{str_name_name_stop_2_grid}"])        
    stop_idx_2_grid_idx = convert_values_inside_dict(stop_idx_2_grid_idx,
                                                     type_stop_idx,
                                                     type_grid_idx)                                                                                                                 # NOTE: Convert -> the values of the dictionary to the right type NOTE: needed if want to access geodataframes correctly
    name_stop_idx_2_grid_idx = convert_values_inside_dict(name_stop_idx_2_grid_idx,
                                                          str,
                                                          type_grid_idx)                                                                                                            # NOTE: Convert -> the values of the dictionary to the right type NOTE: needed if want to access geodataframes correctly
    print("Count the number of stops per cells...")
    Grid_gtfs = count_number_stops_per_grid(Grid_gtfs,
                                            str_grid_idx,
                                            grid_idx_2_stop_idx,
                                            str_col_n_stops)                                                                                                                    # NOTE: Count -> the number of stops per grid cell
    Grid_gtfs = is_the_geometry_inside_cell_droppable(Grid_gtfs,
                                                      str_col_n_stops)                                                                                                              # NOTE: Check -> if the geometry is inside the grid cell, NOTE: will be used to simplify gdf_transport
    print(f"Compute stop_id_2_trip_id: ",config[f"{str_prefix_complete_path}_{str_name_stop_2_trip}"])                                                                                                                      #   
    stop_id_2_trip_id = pipeline_get_stop_id_2_trip_id(stop_times,
                                                       str_stop_idx,
                                                       str_trip_idx,
                                                       config[f"{str_prefix_complete_path}_{str_name_stop_2_trip}"])                                                                # NOTE: Dict -> {stop_id: [trip_id]} -> useful to associate route to stops
    stop_id_2_trip_id = convert_values_inside_dict(stop_id_2_trip_id,  # CORRECT VARIABLE
                                                type_stop_idx,
                                                type_trip_idx)
    print(f"Compute stop_id_2_route_id: ",config[f"{str_prefix_complete_path}_{str_name_stop_2_route}"])                                                                                                                    #                                     
    stop_id_2_route_id = pipeline_get_stop_id_2_route_id(trips,
                                                         stop_id_2_trip_id,
                                                         str_trip_idx,
                                                         str_route_idx,
                                                         config[f"{str_prefix_complete_path}_{str_name_stop_2_route}"])                                                             # NOTE: Dict -> {stop_id: [route_id]} -> useful to associate route to grid
    stop_id_2_route_id = convert_values_inside_dict(stop_id_2_route_id,
                                                    type_stop_idx,
                                                    type_route_idx)                                                                                 # NOTE: Convert -> the values of the dictionary to the right type NOTE: needed if want to access geodataframes correctly
    print(f"Compute grid_idx_2_route_idx: ",config[f"{str_prefix_complete_path}_{str_name_grid_2_route}"])                                                                                                                #
    grid_idx_2_route_idx = pipeline_get_grid_idx_2_route_idx(grid_idx_2_stop_idx,
                                                             stop_id_2_route_id,
                                                             config[f"{str_prefix_complete_path}_{str_name_grid_2_route}"])                                                         # {grid_id: [route_id]} grid 2 route

    grid_idx_2_route_idx = convert_values_inside_dict(grid_idx_2_route_idx,
                                                      type_grid_idx,
                                                      type_route_idx)                                                                                        # convert the values of the dictionary to the right type NOTE: needed if want to access geodataframes correctly  
    return Grid_gtfs,config, grid_idx_2_route_idx, stop_id_2_trip_id, stop_id_2_route_id, grid_idx_2_stop_idx, stop_idx_2_grid_idx, name_stop_idx_2_grid_idx


## ----------------------- ASSOCIATE ROUTES TO FLOWS ----------------------- ##

def compute_route_intersection(i, j, grid_2_route_idx):
    """
    Compute the number of common routes between grid cell i and grid cell j
    """
    routes_i = set(grid_2_route_idx.get(i, []))
    routes_j = set(grid_2_route_idx.get(j, []))
    return len(routes_i.intersection(routes_j))

def pipeline_associate_route_trips_2_flows(flows,
                                           grid_2_route_idx,
                                           str_col_origin,
                                           str_col_destination,
                                           str_col_n_trips_bus):
    """
        Computes the number of bus trips between origin and destination.
    """
    # Convert flows to pandas if it's a polars DataFrame
    if hasattr(flows, 'to_pandas'):
        flows_df = flows.to_pandas()
    else:
        flows_df = flows.copy()

    # Apply the function to compute route intersections
    flows_df[str_col_n_trips_bus] = flows_df.apply(
        lambda row: compute_route_intersection(
            row[str_col_origin], 
            row[str_col_destination], 
            grid_2_route_idx
        ), 
        axis=1
    )
    return flows_df