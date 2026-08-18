import os
from data_preparation.v2.diffusion.default_parameters import *

from data_preparation.v2.utils import DATA_PREFIX, BASE_DIR

## ---------- ERROR VARIABLES ---------- ##
date_in_file_2_skip = {
    f"{DATA_PREFIX}vodafone-aixpa/od-mask_202407.parquet": "2024-08-08",
    f"{DATA_PREFIX}vodafone-aixpa/od-mask_202408.parquet": "2024-07-23",
}


### ---------------------------- VARIABLE NAMES ---------------------------- ###
### --------------------- INPUT VARIABLES --------------------- ###
# Name Project
str_name_project = "Vodafone-Data"  # "Trento-Molveno-Aldeno"

# name variable paths
str_prefix_complete_path = "complete_path"  # prefix for any "complete_path" variable
str_dir_data = "dir_data"  # name of the data folder
str_dir_output = "dir_output"  # name of the output folder
str_dir_plots = "dir_plots"  # name of the plots folder


base_dir_output = BASE_DIR  # Get the current working directory
base_dir_data = BASE_DIR  # Get the current working directory
# name paths
str_dir_data_path = os.path.join(base_dir_data, "Data")  # path to the data folder
str_dir_output_path = os.path.join(
    base_dir_output, "Output", str_name_project
)  # path to the output folder
str_dir_plots_path = os.path.join(
    str_dir_output_path, "Plots"
)  # path to the plots folder

# GTFS
str_name_dataset_gtfs = (
    "extraurbano_invernale"  # name of the dataset: referring to the GTFS file
)
str_name_file_gtfs_zip = "google_transit_extraurbano_tte.zip"  # name of the GTFS file: referring to the GTFS zip file


# Geometries
str_name_gdf_transport = "gdf_transport"  # name of the transport network saved as a gdf -> geometry: LineString
str_name_graph_transport = "graph_transport"  # name of the transport network saved as a graph -> geometry: LineString
str_name_grid = "grid"  # name of the grid gdf -> geometry: Polygon
str_name_shape_city = "shape_city"  # name of the shape gdf -> geometry: Polygon
str_name_centroid_city = "centroid_city"  # name of the centroid gdf -> geometry: Point


# Column names: NOTE: they must retain the same values among different objects.
str_route_idx = (
    "route_id"  # name of the column for the route id -> it is about the bus routes
)
str_trip_idx = (
    "trip_id"  # name of the column for the trip id -> it is about the bus trips
)
str_stop_idx = (
    "stop_id"  # name of the column for the stop id -> it is about the bus stops
)
str_transport_idx = "route_graph_id"  # name of the column for the transport id -> it is the roads in the road network
str_grid_idx = (
    "grid_id"  # name of the column for the grid id -> it is about the grid cells
)


str_centroid_lat = (
    "centroid_lat"  # NOTE: name of the column for the grid centroid latitude coordinate
)
str_centroid_lon = "centroid_lon"  # NOTE: name of the column for the grid centroid longitude coordinate


# Dictionaries for different geometries id
str_name_stop_2_trip = (
    "stop_2_trip"  # NOTE: name of the dictionary for the stops id 2 trip id
)
str_name_stop_2_route = (
    "stop_2_route"  # NOTE: name of the dictionary for the routes id 2 route id
)
str_name_grid_2_stop = (
    "grid_2_stop"  # NOTE: name of the dictionary for the grid id 2 stop id
)
str_name_grid_2_route = (
    "grid_2_route"  # NOTE: name of the dictionary for the grid id 2 routes id
)
str_name_graph_2_route = (
    "graph_2_route"  # NOTE: name of the dictionary for the transport id 2 routes id
)
str_name_route_2_graph = (
    "route_2_graph"  # NOTE: name of the dictionary for the routes id 2 transport id
)
str_name_grid_2_city = (
    "grid_2_city"  # NOTE: name of the dictionary for the grid id 2 city id
)
str_name_distance_matrix = (
    "distance_matrix"  # NOTE: name of the dictionary for the distance matrix
)


# Istat data
str_name_istat_data_file = "POSAS_2024_it_022_Trento.csv"
complete_path_Istat_population = os.path.join(
    str_dir_data_path, str_name_istat_data_file
)  # complete path to the Istat data file


str_col_comuni_istat = "Comune"
str_hotspot_prefix = "hotspot_level"
str_col_origin = "i"
str_col_destination = "j"
str_centroid_lat = "centroid_lat"
str_centroid_lon = "centroid_lon"
str_col_comuni_name = "AREA_LABEL"  # "city_name" NOTE: case download from OSM
str_population_col_grid = "Popolazione_Totale"  # NOTE: for grid (creation fluxes via gravity) in the distance matrix -> df_fluxes


# Population New Dataset Vodafone
str_col_area = "area"
str_col_tot_area = "total_area_by_name"
str_col_fraction = "fraction_area"


# Presences Columns  (raw data)
str_period_id_presenze = "PERIOD_ID"  # NOTE: yyyymmdd (presenze), yyyymmdd [Feriale, Prefestive, Festive] (od)
str_area_id_presenze = "AREA_ID"  # NOTE: id of the area (ITA.<code>)


# OD Columns (raw data)
str_departure_hour_od = "DEPARTURE_HOUR"  # NOTE: departure hour of the trip
str_trip_type_od = "TRIP_TYPE"  # NOTE: 1,2 (1st half august, 2nd half august)
str_origin_od = "O"  # NOTE: origin area (ITA.<code>)
str_destination_od = "D"  # NOTE: destination area (ITA.<code>)
str_origin_visitor_class_id_od = "O_VISITOR_CLASS_ID"  # NOTE: id of the visitor class {"INHABITANT": 1,"COMMUTER": 2,"TOURIST": 3,"VISITOR": 4,"AGGREGATED": 5}
str_area_code_origin_col = "AREA_CODE_ORIGIN"  # NOTE: area code of the origin area (ITA.<code>) Used to associate trips to the OD
str_area_code_destination_col = (
    "AREA_CODE_DESTINATION"  # NOTE: area code of the destination area (ITA.<code>)
)
col_str_day_od = (
    "str_day"  # NOTE: day of the trip (yyyy-mm-dd) Used to associate trips to the OD
)
col_str_is_week = (
    "is_weekday"  # NOTE: is the day a weekday? Used to associate trips to the OD
)
# TYPE USERS PROFILES
UserProfiles = ["INHABITANT", "COMMUTER", "TOURIST", "VISITOR"]  # ,"AGGREGATED"]
UserProfile2IndexVodafone = {
    "INHABITANT": 1,
    "COMMUTER": 2,
    "TOURIST": 3,
    "VISITOR": 4,
}  # ,


conditioning_2_columns_to_hold_when_aggregating = {
    "day_hour_user_weekday": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        col_str_day_od,
        str_departure_hour_od,
        str_origin_visitor_class_id_od,
        col_str_is_week,
    ],
    "hour_user_weekday": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        str_departure_hour_od,
        str_origin_visitor_class_id_od,
        col_str_is_week,
    ],
    "user_weekday": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        str_origin_visitor_class_id_od,
        col_str_is_week,
    ],
    "user": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        str_origin_visitor_class_id_od,
    ],
    "hour_weekday": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        str_departure_hour_od,
        col_str_is_week,
    ],
    "hour": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        str_departure_hour_od,
    ],
    "weekday": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        col_str_is_week,
    ],
    "_": [str_origin_od, str_destination_od, str_col_origin, str_col_destination],
    "day_hour_weekday": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        col_str_day_od,
        str_departure_hour_od,
        col_str_is_week,
    ],
    "hour_user_weekday": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        str_departure_hour_od,
        str_origin_visitor_class_id_od,
        col_str_is_week,
    ],
}

conditioning_2_columns_to_hold_when_aggregating_baseline = {
    "day_hour_user_weekday": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        str_departure_hour_od,
        str_origin_visitor_class_id_od,
        col_str_is_week,
    ],
    "hour_user_weekday": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        str_departure_hour_od,
        str_origin_visitor_class_id_od,
        col_str_is_week,
    ],
    "user_weekday": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        str_origin_visitor_class_id_od,
        col_str_is_week,
    ],
    "user": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        str_origin_visitor_class_id_od,
    ],
    "hour_weekday": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        str_departure_hour_od,
        col_str_is_week,
    ],
    "hour": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        str_departure_hour_od,
    ],
    "weekday": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        col_str_is_week,
    ],
    "_": [str_origin_od, str_destination_od, str_col_origin, str_col_destination],
    "day_hour_weekday": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        str_departure_hour_od,
        col_str_is_week,
    ],
    "hour_user_weekday": [
        str_origin_od,
        str_destination_od,
        str_col_origin,
        str_col_destination,
        str_departure_hour_od,
        str_origin_visitor_class_id_od,
        col_str_is_week,
    ],
}


# NOTE: This is the name_base for diffusione 3


#########################################################
############### NEW PIPELINE DICTIONARIES ###############
#########################################################


## IN and OUT FLOWS
case_2_is_in_flow = {
    "in": True,
    "out": False,
}  # NOTE: We associate the strings "in", "out" to True, False to differentiate the case of studying in and out flows


## NOTE that this part of the code tells what are the cases that we implemented for the post-processing and visualization of the flows in the grid and hotspot analysis
