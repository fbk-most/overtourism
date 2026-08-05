import os
from polars import Utf8
from data_preparation.diffusion.default_parameters import *
from datetime import timedelta, date

from data_preparation.utils import DATA_PREFIX, BASE_DIR

## ---------- ERROR VARIABLES ---------- ##
date_in_file_2_skip = {f'{DATA_PREFIX}vodafone-aixpa/od-mask_202407.parquet':"2024-08-08",
                       f'{DATA_PREFIX}vodafone-aixpa/od-mask_202408.parquet':"2024-07-23"}


## HOLIDAYS ###
public_holidays = {
    date(2023, 1, 1),   # New Year's Day
    date(2023, 1, 6),   # Epiphany
    date(2023, 4, 25),  # Liberation Day
    date(2023, 5, 1),   # Labor Day
    date(2023, 6, 2),   # Republic Day
    date(2023, 8, 15),  # Assumption Day
    date(2023, 11, 1),  # All Saints' Day
    date(2023, 12, 8),  # Immaculate Conception
    date(2023, 12, 25), # Christmas
    date(2023, 12, 26), # St. Stephen's Day
}


### ---------------------------- VARIABLE NAMES ---------------------------- ###
### --------------------- INPUT VARIABLES --------------------- ###
# Name Project
str_name_project = "Vodafone-Data"#"Trento-Molveno-Aldeno"

# name variable paths
str_prefix_complete_path = "complete_path"                                          # prefix for any "complete_path" variable
str_dir_data = "dir_data"                                                           # name of the data folder
str_dir_output = "dir_output"                                                       # name of the output folder
str_dir_plots = "dir_plots"                                                         # name of the plots folder


base_dir_output = BASE_DIR # Get the current working directory
base_dir_data = BASE_DIR  # Get the current working directory
# name paths
str_dir_data_path = os.path.join(base_dir_data,"Data")                            # path to the data folder
str_dir_output_path = os.path.join(base_dir_output,"Output",str_name_project)    # path to the output folder
str_dir_plots_path = os.path.join(str_dir_output_path,"Plots")  # path to the plots folder

# GTFS
str_name_dataset_gtfs  = "extraurbano_invernale"                                    # name of the dataset: referring to the GTFS file
str_name_file_gtfs_zip = "google_transit_extraurbano_tte.zip"                       # name of the GTFS file: referring to the GTFS zip file

# DataLake Variables
dtypes_locId = {
    "locId": Utf8                                                                # Read the locId column as a string
}
infer_schema_length = 1000

str_user_profile_vodafone_col = "userProfile"                                       # name of the column for the user profile in df_attendences

# Geometries
str_name_gdf_transport = "gdf_transport"                                            # name of the transport network saved as a gdf -> geometry: LineString  
str_name_graph_transport = "graph_transport"                                        # name of the transport network saved as a graph -> geometry: LineString
str_name_gdf_stops = "gdf_stops"                                                    # name of the gdf for stops -> geometry: Point
str_name_grid = "grid"                                                              # name of the grid gdf -> geometry: Polygon
str_name_shape_city = "shape_city"                                                  # name of the shape gdf -> geometry: Polygon
str_name_centroid_city = "centroid_city"                                            # name of the centroid gdf -> geometry: Point


# Column names: NOTE: they must retain the same values among different objects.
str_route_idx = "route_id"                                                       # name of the column for the route id -> it is about the bus routes
str_trip_idx = "trip_id"                                                         # name of the column for the trip id -> it is about the bus trips
str_stop_idx = "stop_id"                                                         # name of the column for the stop id -> it is about the bus stops
str_transport_idx = "route_graph_id"                                             # name of the column for the transport id -> it is the roads in the road network
str_grid_idx = "grid_id"                                                         # name of the column for the grid id -> it is about the grid cells
str_i_name = "i"                                                                 # name of the column for the i coordinate in the grid                
str_j_name = "j"                                                                 # name of the column for the j coordinate in the grid   
str_name_stop_id = "stop_name"                                                   # name of the column for gdf stops -> it is about the bus stops NOTE: it is going to be useful to associate routes to OD (associate the stops to the routes)
# Column City
str_city_name_idx = "city_name"                                                  # name of the column for the cities_gdf -> idx

# Grid cols after join with city gdf
str_area_city = "area_city"                                                      # name of the column for the area of the city   
str_area_grid = "area_grid"                                                      # name of the column for the area of the grid cell  
str_area_intersection = "area_intersection_grid_city"                            # name of the column for the area of the intersection between the grid cell and the city                       
str_fraction_intersection_area_city = "intersection_fraction_area_city"          # name of the column for the fraction of the intersection area between the grid cell and the city
str_fraction_intersection_area_grid = "intersection_fraction_area_grid"          # name of the column for the fraction of the intersection area between the grid cell and the city


str_col_n_stops = "n_stops"                                                      # name of number of stops in the column of the grid 
str_col_is_droppable = "is_roads_inside_droppable"                               # name of the column for the droppable roads, it is associated to grid cells : if the n_stops is bigger then 2.
str_col_is_inside = "is_inside"                                                  # name of the column for grid, inside the perimeter of zones.

# Types
type_route_idx = str
type_trip_idx = str
type_stop_idx = str
type_name_stop_id = str
type_transport_idx = int
type_grid_idx = int
type_str_i = int
type_str_j = int

# crs
crs = "EPSG:4326"                                                                  # NOTE: crs for the gdf -> UTM 32N
crs_proj = "EPSG:3857"                                                             # NOTE: crs projection tangent space
int_crs = 4326                                                                     # NOTE: crs projection UTM int
int_crs_proj = 3857                                                                # NOTE: crs projection tangent space int



# centroid grid 
str_centroid_grid_x = "centroid_grid_x"                                             # NOTE: name of the column for the grid centroid x coordinate
str_centroid_grid_y = "centroid_grid_y"                                             # NOTE: name of the column for the grid centroid y coordinate
str_centroid_lat = "centroid_lat"                                                   # NOTE: name of the column for the grid centroid latitude coordinate
str_centroid_lon = "centroid_lon"                                                   # NOTE: name of the column for the grid centroid longitude coordinate


# Dictionaries for different geometries id
str_name_stop_2_trip = "stop_2_trip"                                                # NOTE: name of the dictionary for the stops id 2 trip id
str_name_stop_2_route = "stop_2_route"                                              # NOTE: name of the dictionary for the routes id 2 route id
str_name_grid_2_stop = "grid_2_stop"                                                # NOTE: name of the dictionary for the grid id 2 stop id
str_name_stop_2_grid = "stop_2_grid"                                                # NOTE: name of the dictionary for the stop id 2 grid id
str_name_name_stop_2_grid = "name_stop_2_grid"                                      # NOTE: name of the dictionary for the name stop id 2 grid id NOTE: name stop id: Trento. Autostazione -> they are used to get the direction of the origin destination of buses.
str_name_grid_2_trip = "grid_2_trip"                                                # NOTE: name of the dictionary for the grid id 2 trip id
str_name_grid_2_route = "grid_2_route"                                              # NOTE: name of the dictionary for the grid id 2 routes id
str_name_graph_2_route = "graph_2_route"                                            # NOTE: name of the dictionary for the transport id 2 routes id
str_name_route_2_graph = "route_2_graph"                                            # NOTE: name of the dictionary for the routes id 2 transport id
str_name_grid_2_city = "grid_2_city"                                                # NOTE: name of the dictionary for the grid id 2 city id
str_name_distance_matrix = "distance_matrix"                                        # NOTE: name of the dictionary for the distance matrix
str_name_lattice = "lattice"                                                        # NOTE: name of the dictionary for the lattice
str_name_vector_field = "vector_field"                                              # NOTE: name of the dictionary for the vector field
str_name_potential = "potential"                                                    # NOTE: name of the dictionary for the potential

# Distance/Lattice/Potential/VF names
str_i_col = "i"                                                                     # NOTE: DISTANCE MATRIX DF -> name of the column for the i coordinate                                     
str_j_col = "j"                                                                     # NOTE: DISTANCE MATRIX DF -> name of the column for the j coordinate
str_dir_vector_col = "dir_vector"                                                   # NOTE: DISTANCE MATRIX DF -> name of the column for the direction vector                              
str_distance_col = "distance"                                                       # NOTE: DISTANCE MATRIX DF -> name of the column for the distance   

str_flux_column = 'number_people'                                                   # NOTE: ORIGIN DESTINATION IN GRID -> name of the column for the flux   
str_index_fluxes_O_col = '(i,j)O'                                                   # NOTE: ORIGIN DESTINATION IN GRID -> name of the column for the i,j coordinates of the origin
str_index_fluxes_D_col = '(i,j)D'                                                   # NOTE: ORIGIN DESTINATION IN GRID -> name of the column for the i,j coordinates of the destination 
str_Ti = 'Ti'                                                                       # NOTE: ORIGIN DESTINATION IN GRID -> name of the column for the incoming flux in origin                      
str_Tj = 'Tj'                                                                       # NOTE: ORIGIN DESTINATION IN GRID -> name of the column for the outgoing flux in destination                                  
                                                                                    #
str_index_vector_field = '(i,j)'                                                    # NOTE: VECTOR FIELD -> name of the column for the i,j coordinates of the vector field    

str_potential_in = 'V_in'                                                           # NOTE: POTENTIAL -> name of the column for the potential of the incoming flux (Ti)                 
str_potential_out = 'V_out'                                                         # NOTE: POTENTIAL -> name of the column for the potential out of the outgoing flux (Tj)
str_rotor_z_in = 'rotor_z_in'                                                       # NOTE: ROTOR -> name of the column for the rotor incoming flux (Ti)
str_rotor_z_out = 'rotor_z_out'                                                     # NOTE: ROTOR -> name of the column for the rotor outgoing flux (Tj)                

str_population = 'population'                                                       # NOTE: Grid_Population -> name of the column for the population in the grid cell


# Istat data
str_name_istat_data_file = "POSAS_2024_it_022_Trento.csv"
complete_path_Istat_population = os.path.join(str_dir_data_path,str_name_istat_data_file)               # complete path to the Istat data file



str_col_comuni_istat = "Comune"
str_hotspot_prefix = "hotspot_level"
str_col_origin = "i"
str_col_destination = "j"
str_centroid_lat = "centroid_lat"
str_centroid_lon = "centroid_lon"
str_col_comuni_name= "AREA_LABEL"                                #"city_name" NOTE: case download from OSM
str_colormap= 'YlOrRd'
str_population_col_grid = "Popolazione_Totale"                   # NOTE: for grid (creation fluxes via gravity) in the distance matrix -> df_fluxes 
str_population_i = "population_i"
str_population_j = "population_j"
str_distance_column = "distance"                                 # NOTE: for grid (creation fluxes via gravity) in the distance matrix -> df_fluxes


# Population New Dataset Vodafone
str_col_area = 'area'
str_col_tot_area = 'total_area_by_name'
str_col_fraction = 'fraction_area'
str_area_code = "AREA_CODE"                                      # NOTE: area code (ITA.<code>)



# Presences Columns  (raw data)
str_period_id_presenze = "PERIOD_ID"                                # NOTE: yyyymmdd (presenze), yyyymmdd [Feriale, Prefestive, Festive] (od)
str_area_id_presenze = "AREA_ID"                                    # NOTE: id of the area (ITA.<code>) 
str_time_block_layer_presenze = "TIME_BLOCK_LAYER"                  # NOTE: 1,2 (1st half august, 2nd half august)
str_time_block_id_presenze = "TIME_BLOCK_ID"                        # NOTE: 7,8, ecc.. represent the hour in integer of the day 
str_nationality_class_id_presenze = "NATIONALITY_CLASS_ID"          # NOTE: It is a unique string that represnt the nation
str_visitor_class_id_presenze = "VISITOR_CLASS_ID"                  # NOTE: It is a unique string that represnt the user profile [INHABITANT, COMMUTER, VISITOR, TOURIST]
str_country_presenze = "COUNTRY"                                    # NOTE: 
str_cod_reg_night_home_presenze = "COD_REG_NIGHT_HOME"
str_cod_pro_night_home_presenze = "COD_PRO_NIGHT_HOME"
str_presences_presenze = "PRESENCES"                                # NOTE: Presences computed by Vodafone

ImportantColumnsPresenze = [str_period_id_presenze, str_time_block_layer_presenze,
                            str_time_block_id_presenze, str_nationality_class_id_presenze, str_visitor_class_id_presenze,
                            str_country_presenze, str_cod_reg_night_home_presenze, str_cod_pro_night_home_presenze,
                            str_presences_presenze]

# OD Columns (raw data)
str_departure_hour_od = "DEPARTURE_HOUR"                            # NOTE: departure hour of the trip 
str_trip_type_od = "TRIP_TYPE"                                      # NOTE: 1,2 (1st half august, 2nd half august)  
str_origin_od = "O"                                                 # NOTE: origin area (ITA.<code>)
str_destination_od = "D"                                            # NOTE: destination area (ITA.<code>)              
str_nationality_class_id_od = "NATIONALITY_CLASS_ID"                # NOTE: id (1 ITA, -1 OTHER)
str_origin_visitor_class_id_od = "O_VISITOR_CLASS_ID"               # NOTE: id of the visitor class {"INHABITANT": 1,"COMMUTER": 2,"TOURIST": 3,"VISITOR": 4,"AGGREGATED": 5}     
str_destination_visitor_class_id_od = "D_VISITOR_CLASS_ID"          # NOTE: id of the visitor class {"INHABITANT": 1,"COMMUTER": 2,"TOURIST": 3,"VISITOR": 4,"AGGREGATED": 5}
str_trips_od = "TRIPS"                                              # NOTE: number of trips between origin and destination
str_area_code_origin_col="AREA_CODE_ORIGIN"                         # NOTE: area code of the origin area (ITA.<code>) Used to associate trips to the OD
str_area_code_destination_col="AREA_CODE_DESTINATION"               # NOTE: area code of the destination area (ITA.<code>) 
col_str_day_od = "str_day"                                          # NOTE: day of the trip (yyyy-mm-dd) Used to associate trips to the OD      
col_str_is_week = "is_weekday"                                      # NOTE: is the day a weekday? Used to associate trips to the OD   
str_col_O_vodafone = str_origin_od
str_col_D_vodafone = str_destination_od
# TYPE USERS PROFILES
UserProfiles = ["INHABITANT","COMMUTER","TOURIST","VISITOR"]#,"AGGREGATED"]
UserProfile2IndexVodafone = {"INHABITANT": 1,
                            "COMMUTER": 2,
                            "TOURIST": 3,
                            "VISITOR": 4}#,
#                            "AGGREGATED": 5}                                                                                                                         # NOTE: here we define the
IndexVodafone2UserProfile = {v: k for k, v in UserProfile2IndexVodafone.items()}     

# TYPES OF POSSIBLE AGGREGATIONS
############# CASES ANALYSIS #############
name_keys_pipeline_2_columns_aggregation_diffusione_1_2 = {"day":col_str_day_od,                     # NOTE: in [2024-07-01, ..., 2024-08-31]
                                                           "hour":str_departure_hour_od,                # NOTE: in [0,1,...,23]
                                                           "user":str_origin_visitor_class_id_od,       # NOTE: 1,2,3,4,5
                                                           "weekday":col_str_is_week,                   # NOTE: True, False}
                                                            }



conditioning_2_columns_to_hold_when_aggregating = {"day_hour_user_weekday":[str_origin_od, str_destination_od, str_col_origin, str_col_destination,col_str_day_od, str_departure_hour_od, str_origin_visitor_class_id_od, col_str_is_week],
                                                   "hour_user_weekday":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_departure_hour_od, str_origin_visitor_class_id_od, col_str_is_week],
                                                   "user_weekday":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_origin_visitor_class_id_od, col_str_is_week],
                                                   "user":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_origin_visitor_class_id_od],
                                                   "hour_weekday":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_departure_hour_od, col_str_is_week],
                                                   "hour":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_departure_hour_od],
                                                   "weekday":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, col_str_is_week],
                                                   "_":[str_origin_od, str_destination_od, str_col_origin, str_col_destination],
                                                   "day_hour_weekday":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, col_str_day_od, str_departure_hour_od, col_str_is_week],
                                                   "hour_user_weekday":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_departure_hour_od, str_origin_visitor_class_id_od, col_str_is_week],
                                                   }

conditioning_2_columns_to_hold_when_aggregating_baseline = {"day_hour_user_weekday":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_departure_hour_od, str_origin_visitor_class_id_od, col_str_is_week],
                                                            "hour_user_weekday":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_departure_hour_od, str_origin_visitor_class_id_od, col_str_is_week],
                                                            "user_weekday":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_origin_visitor_class_id_od, col_str_is_week],
                                                            "user":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_origin_visitor_class_id_od],
                                                            "hour_weekday":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_departure_hour_od, col_str_is_week],
                                                            "hour":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_departure_hour_od],
                                                            "weekday":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, col_str_is_week],
                                                            "_":[str_origin_od, str_destination_od, str_col_origin, str_col_destination],
                                                            "day_hour_weekday":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_departure_hour_od, col_str_is_week],
                                                            "hour_user_weekday":[str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_departure_hour_od, str_origin_visitor_class_id_od, col_str_is_week],
                                                            }
# TYPES AGGREGATIONS MARKOWItZ NOTE: the columns that are there, are those that are going to be used as conditions for the 
conditioning_2_columns_to_hold_when_aggregating_markowitz = {"day_hour":[str_area_id_presenze, str_time_block_id_presenze, str_time_block_layer_presenze],
                                                             "day": [str_area_id_presenze, col_str_day_od],
                                                             "hour": [str_area_id_presenze, str_time_block_id_presenze],
                                                             "day_hour_nationality":[str_area_id_presenze, str_time_block_id_presenze, col_str_day_od,str_nationality_class_id_presenze],
                                                             }




# NOTE: This is the name_base for diffusione 3


#########################################################
############### NEW PIPELINE DICTIONARIES ###############
#########################################################

# Flows = Pipeline 1 and 2
AGGREGATION_NAMES_FLOWS = ["day", "hour", "user", "weekday"]

AGGREGATION_NAMES_2_COLUMNS_AGGREGATION_FLOWS = {"day":col_str_day_od,                     # NOTE: in [2024-07-01, ..., 2024-08-31]
                                                "hour":str_departure_hour_od,                # NOTE: in [0,1,...,23]
                                                "user":str_origin_visitor_class_id_od,       # NOTE: 1,2,3,4,5
                                                "weekday":col_str_is_week,                   # NOTE: True, False}
                                                }

DICT_NAME_OUTPUT_KEY_2_DEFAULT_INIT_PIPELINE_1_2 = {"dict_columns_flows": {"str_col_n_trips": [],
                                                                        "str_col_n_trips_baseline": [],
                                                                        "str_caption_colormap_flows": "",
                                                                        "str_col_difference_baseline": []
                                                                        },
                                                "dict_columns_grid": {"str_col_hotspot": [],
                                                                      "str_col_total_flows_grid_hierachical_routine": []
                                                                      },
                                                "dict_output_hotspot_analysis": {"hotspot_2_origin_idx_2_crit_dest_idx": {},
                                                                                "list_indices_all_fluxes_for_colormap": [],
                                                                                "hotspot_levels": {}
                                                                                }
                                                }


# Presences = Pipeline 3
AGGREGATION_NAMES_PRESENCES = ["time", "visitor", "country", "weekday"]

AGGREGATION_NAMES_2_COLUMNS_AGGREGATION_PRESENCES = {"time":str_time_block_id_presenze,                     # NOTE: in [7,8,10,16,18]
                                                        "visitor":str_visitor_class_id_presenze,            # NOTE: 1,2,3,4,5
                                                        "country":str_country_presenze,
                                                        "weekday":col_str_is_week,
                                                        }

DICT_NAME_OUTPUT_KEY_2_DEFAULT_INIT_PIPELINE_3 = {"column_presences_no_baseline": "",
                                                "column_presences_baseline": "",
                                                "column_total_diff_october_mean_0": "",
                                                "column_total_diff_october_mean_0_var_1": "",
                                                "column_total_diff_october_var_1": "",
                                                "column_total_diff_oct": "",
                                                "column_std": "",
                                                "column_expected_return": "",
                                                "column_cov": "",
                                                "column_portfolio": ""
                                                }

LIST_NAME_VARIABLES_OUTPUT_PRESENCES_ANALYSIS = list(DICT_NAME_OUTPUT_KEY_2_DEFAULT_INIT_PIPELINE_3.keys())


## IN and OUT FLOWS
case_2_is_in_flow = {"in":True,"out":False}                                                 # NOTE: We associate the strings "in", "out" to True, False to differentiate the case of studying in and out flows

######### MARKOWITZ ########
col_str_average_presences_null_day = "avg_presences_october_2024"                           # NOTE: This column is used to compute the average presence computed for the null days (average presences over october)
col_std = "std_day"                                                                           # NOTE: This column is used to compute the standard deviation of the presence computed for the null days


## NOTE that this part of the code tells what are the cases that we implemented for the post-processing and visualization of the flows in the grid and hotspot analysis

CASE_PIPELINE_AGGREGATION_WEEKDAY = "weekday"
CASE_PIPELINE_AGGREGATION_DAY_HOUR_USER_WEEKDAY = "day_hour_user_weekday"




