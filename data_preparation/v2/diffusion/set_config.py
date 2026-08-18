"""
Created on 19/04/2025 author: Alberto Amaduzzi
This script is used to set the configuration for the project.
It contains the paths to the data and output folders, the names of the datasets,
the names of the variables, and the parameters for the analysis.
It is used to set the configuration for the project.
NOTE: Change here the paths to the data and output folders, the names of the datasets,
"""

import os
import polars as pl
from data_preparation.v2.diffusion.constant_names_variables import *

### ---------------------------- CONFIGURATION ---------------------------- ###
from collections import defaultdict


def set_config(
    str_name_project,  # NAME PROJECT
    str_dir_data_path,  # PATH DATA
    str_dir_output_path,  # PATH OUTPUT
    complete_path_Istat_population,  # PATH ISTAT DATA
    str_prefix_complete_path,  # PREFIX COMPLETE PATH
    str_start_time_window_interest,  # TIME (str): START WINDOW INTEREST
    str_end_time_window_interest,  # TIME (str): END WINDOW INTEREST
    int_number_people_per_bus,  # NUMBER PEOPLE PER BUS
    str_name_file_gtfs_zip,
    str_name_dataset_gtfs,
    str_name_gdf_transport,
    str_name_graph_transport,
    str_name_grid,
    str_name_grid_2_city,
    str_name_shape_city,
    str_name_centroid_city,
    str_route_idx,
    str_trip_idx,
    str_stop_idx,
    str_transport_idx,
    str_grid_idx,
    str_name_stop_2_trip,
    str_name_stop_2_route,
    str_name_grid_2_stop,
    str_name_grid_2_route,
    str_name_graph_2_route,
    str_name_route_2_graph,
    str_dir_plots_path,
    int_hour_start_window_interest,
    int_hour_end_window_interest,
    int_min_aggregation_OD,
    Lx,
    Ly,
):
    config = defaultdict()

    # Project
    config["name_project"] = str_name_project  # name of the project

    # Paths
    config[str_dir_data] = str_dir_data_path  # path to the data folder
    config[str_dir_output] = str_dir_output_path  # path to the output folder
    config[str_dir_plots] = str_dir_plots_path  # path to the plots folder
    os.makedirs(
        str_dir_plots_path, exist_ok=True
    )  # Create the plots folder if it does not exist
    os.makedirs(
        str_dir_output_path, exist_ok=True
    )  # Create the output folder if it does not exist
    os.makedirs(
        str_dir_data_path, exist_ok=True
    )  # Create the data folder if it does not exist
    # Bounding Box
    config["south"] = 45.994481  # south bound of the bounding box -> longitude coords
    config["north"] = 46.249579  # north bound of the bounding box -> longitude coords
    config["west"] = 10.880035  # west bound of the bounding box -> latitude coords
    config["east"] = 11.281036  # east bound of the bounding box -> latitude coords

    # Time constraint
    config["start_time_window_interest"] = (
        str_start_time_window_interest  # start time of the time window of interest -> HH:MM:SS window of time for which we are interested about trips
    )
    config["end_time_window_interest"] = (
        str_end_time_window_interest  # end time of the time window of interest -> HH:MM:SS window of time for which we are interested about trips
    )
    config["int_hour_start_window_interest"] = (
        int_hour_start_window_interest  # start time of the time window of interest -> hours
    )
    config["int_hour_end_window_interest"] = (
        int_hour_end_window_interest  # end time of the time window of interest -> hours
    )
    config["int_min_aggregation_OD"] = (
        int_min_aggregation_OD  # time window for the aggregation of the OD matrix in minutes (we count the number of routes are available in the time window of interest)
    )

    # Stops

    # Transport network

    # Grid
    config["Lx"] = Lx  # size of x of a cell in the grid in meters
    config["Ly"] = Ly  # size of y of a cell in the grid in meters

    # Bus parameters
    config["number_people_per_bus"] = (
        int_number_people_per_bus  # number of people per bus
    )

    # Output variables
    config[f"{str_prefix_complete_path}_{str_name_dataset_gtfs}"] = os.path.join(
        config[str_dir_data], str_name_file_gtfs_zip
    )  # full path GTFS file
    config[f"{str_prefix_complete_path}_{str_name_grid}"] = os.path.join(
        config[str_dir_output], f"{str_name_grid}_boundary_Lx_{Lx}_Ly_{Ly}.geojson"
    )  # full path grid
    # Public transport                                                                                                                                                                         #
    config[f"{str_prefix_complete_path}_{str_name_gdf_transport}"] = os.path.join(
        config[str_dir_output],
        f"{str_name_gdf_transport}_boundary_Lx_{Lx}_Ly_{Ly}.geojson",
    )  # full path transport network (gdf)
    config[f"{str_prefix_complete_path}_{str_name_graph_transport}"] = os.path.join(
        config[str_dir_output],
        f"{str_name_gdf_transport}_boundary_Lx_{Lx}_Ly_{Ly}.graphml",
    )  # path to the graph transport
    # Cities of Interest and Shapefiles                                                                                                                                    #                   #
    config[f"{str_prefix_complete_path}_{str_name_shape_city}"] = os.path.join(
        config[str_dir_output],
        f"{str_name_shape_city}_boundary_Lx_{Lx}_Ly_{Ly}.geojson",
    )  # full path stops (gdf)
    config[f"{str_prefix_complete_path}_{str_name_centroid_city}"] = os.path.join(
        config[str_dir_output],
        f"{str_name_centroid_city}_boundary_Lx_{Lx}_Ly_{Ly}.geojson",
    )  # full path stops (gdf)

    # dictionaries -> json
    config[f"{str_prefix_complete_path}_{str_name_stop_2_trip}"] = os.path.join(
        config[str_dir_output], f"{str_name_stop_2_trip}_boundary_Lx_{Lx}_Ly_{Ly}.json"
    )  # trip_2_grid
    config[f"{str_prefix_complete_path}_{str_name_stop_2_route}"] = os.path.join(
        config[str_dir_output], f"{str_name_stop_2_route}_boundary_Lx_{Lx}_Ly_{Ly}.json"
    )  # route_2_grid
    config[f"{str_prefix_complete_path}_{str_name_grid_2_stop}"] = os.path.join(
        config[str_dir_output], f"{str_name_grid_2_stop}_boundary_Lx_{Lx}_Ly_{Ly}.json"
    )  # grid_2_trip
    config[f"{str_prefix_complete_path}_{str_name_grid_2_route}"] = os.path.join(
        config[str_dir_output], f"{str_name_grid_2_route}_boundary_Lx_{Lx}_Ly_{Ly}.json"
    )  # grid_2_route
    config[f"{str_prefix_complete_path}_{str_name_grid_2_city}"] = os.path.join(
        config[str_dir_output], f"{str_name_grid_2_city}_boundary_Lx_{Lx}_Ly_{Ly}.json"
    )  # grid_2_route

    # Istat
    config[str_name_istat_data_file] = complete_path_Istat_population
    return config
