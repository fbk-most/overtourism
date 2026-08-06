from data_preparation.diffusion.global_import import *
import os

# NOTE: Digital Hub configuration
PROJECT = os.environ.get("PROJECT_NAME", "overtourism1")
BUCKET_NAME = os.environ.get("S3_BUCKET", "datalake")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL", "http://minio:9000")
DATA_PREFIX = os.environ.get("DATA_PREFIX", "projects/tourism/_origin/")
BASE_DIR = os.environ.get("BASE_DIR", os.getcwd())

project_tourism = dh.get_or_create_project(PROJECT)
endpoint_url=AWS_ENDPOINT_URL
s3 = boto3.resource('s3',endpoint_url=endpoint_url)
bucket = s3.Bucket(BUCKET_NAME)
# NOTE: Set up configuration
config = set_config(str_name_project, str_dir_data_path, str_dir_output_path, complete_path_Istat_population, str_prefix_complete_path, str_start_time_window_interest, str_end_time_window_interest, int_number_people_per_bus, str_name_file_gtfs_zip, str_name_dataset_gtfs, str_name_gdf_transport, str_name_graph_transport, str_name_grid, str_name_grid_2_city, str_name_shape_city, str_name_centroid_city, str_route_idx, str_trip_idx, str_stop_idx, str_transport_idx, str_grid_idx, str_name_stop_2_trip, str_name_stop_2_route, str_name_grid_2_stop, str_name_grid_2_route, str_name_graph_2_route, str_name_route_2_graph, str_dir_plots_path, int_hour_start_window_interest, int_hour_end_window_interest, int_min_aggregation_OD, Lx, Ly)

# For now, create empty data_handler for memory efficiency
data_handler = None  # Replace with actual DataHandler when dataframes are available
gc.collect()  # Force garbage collection after setup


# NOTE: Gtfs Data
if os.path.exists(config[f"{str_prefix_complete_path}_{str_name_dataset_gtfs}"]):
    print("GTFS file exists, loading it")
    feed = Preprocessing_gtfs(config[f"{str_prefix_complete_path}_{str_name_dataset_gtfs}"])
    is_gtfs_available = False
else:
    print("GTFS file does not exist, downloading it")
    is_gtfs_available = False
    feed = None

print("Define paths...")
complete_path_shape_gdf = config[f"{str_prefix_complete_path}_{str_name_shape_city}"]
complete_path_centroid_gdf = config[f"{str_prefix_complete_path}_{str_name_centroid_city}"]
config[str_name_distance_matrix] = os.path.join(config[str_dir_output],f"{str_name_distance_matrix}.parquet")
complete_path_direction_distance_df = config[str_name_distance_matrix]

# NOTE: Comuni -> Shape file + Istat (Gravity Model)
print("Upload Istat data...")
Istat_obj = Istat_population_data(complete_path_Istat_population)
cities_gdf = gpd.read_file(os.path.join(BASE_DIR,"Data","mavfa-fbk_AIxPA_tourism-delivery_2025.08.22-zoning","fbk-aixpa-turismo.shp"))
cities_gdf = simple_join_cities_with_population(cities_gdf, Istat_obj.population_by_comune, str_col_comuni_istat = str_col_comuni_istat, str_col_popolazione_totale = str_population_col_grid, str_col_city_name = str_col_comuni_name, is_Vodafone_Trento_ZDT = True)
cities_gdf = add_column_area_and_fraction(cities_gdf, str_col_comuni_name, str_col_area = str_col_area, str_col_tot_area = str_col_tot_area, str_col_fraction = str_col_fraction, crs_proj = 3857, crs_geographic = 4326)
cities_gdf = add_suffix_to_repeated_values(cities_gdf, str_col_comuni_name)
cities_gdf = redistribute_population_by_fraction(cities_gdf, str_col_popolazione_totale = str_population_col_grid, str_col_fraction = str_col_fraction, str_col_comuni_name = str_col_comuni_name, conserve_total=True)

# NOTE: Distance Matrix
print(f"Compute distance and direction matrix: {complete_path_direction_distance_df}")
direction_matrix,distance_matrix = compute_direction_matrix_optimized(cities_gdf, str_centroid_x_col = str_centroid_lat, str_centroid_y_col = str_centroid_lon, complete_path_direction_distance_df = complete_path_direction_distance_df)
df_distance_matrix = direction_distance_2_df(direction_matrix, distance_matrix, complete_path_direction_distance_df)




# NOTE: The list of files depends on the files shared by Vodafone: [od-mask_01_202407, od-mask_01_202408, od-mask_01_202410, ...]
# For each of these files we extract the dates
print("Extract list of files from bucket...")
list_files_od, list_files_presenze, list_str_dates_yyyymm = extract_filenames_and_date_from_bucket(bucket)
date_in_file_2_skip = {DATA_PREFIX + 'vodafone-aixpa/od-mask_202407.parquet':"2024-08-08",
                       DATA_PREFIX + 'vodafone-aixpa/od-mask_202408.parquet':"2024-07-23"}

print("Extract list of files from bucket...")
list_files_od, list_files_presenze, list_str_dates_yyyymm = extract_filenames_and_date_from_bucket(bucket)
print("Extract days available for analysis flows...")
list_all_avaliable_days_flows = extract_all_days_available_analysis_flows_from_raw_dataset(list_files_od,col_str_day_od,str_period_id_presenze,col_str_is_week,s3)                             # NOTE: Needed to create dict_column_flows,grid for post-processing 
print("Preparing list columns to plot grid and flows...")
print("flows post-processing...")
dict_column_flows = {str_day: 
                        {time_interval[0]: 
                            {user_profile:
                                {is_weekday: {suffix_in:{"str_col_n_trips": "",                                                                                             # str_col_hotspot
                                                        "str_col_n_trips_baseline": "", 
                                                        "str_caption_colormap_flows": "",
                                                        "str_col_difference_baseline": ""                                                                                                                                                                                                                                  # str_col_n_trips_baseline
                                                        }                                                                                                                                                                  
                                              for suffix_in in case_2_is_in_flow.keys()
                                              }                                 
                                for is_weekday in week_days
                                } 
                             for user_profile in UserProfiles
                            }
                        for time_interval in list_time_intervals
                        } 
                    for str_day in list_all_avaliable_days_flows
                    }

print("grid post-processing...")
dict_column_grid = {str_day: 
                        {time_interval[0]: 
                            {user_profile:
                                {is_weekday: {suffix_in:{"str_col_hotspot": "",                                                                                             # str_col_hotspot
                                                         "str_col_total_flows_grid_hierachical_routine": "",                                                                # NOTE: Column holding info about the total number of people that have passed through that grid cell
                                                        }                                                                                                                                                                  
                                              for suffix_in in case_2_is_in_flow.keys()
                                              }
                                 for is_weekday in week_days
                                } 
                             for user_profile in UserProfiles
                             }
                        for time_interval in list_time_intervals
                        } 
                    for str_day in list_all_avaliable_days_flows
                    }
print("hotspot analysis post-processing...")
dict_output_hotspot_analysis = {str_day: 
                        {time_interval[0]: 
                            {user_profile:
                                {is_weekday: {suffix_in:{"hotspot_2_origin_idx_2_crit_dest_idx": "",                                                                                             # str_col_hotspot
                                                         "list_indices_all_fluxes_for_colormap": "",
                                                         "hotspot_levels":{}                                                                                                                                # NOTE: Column holding info about the total number of people that have passed through that grid cell
                                                        }                                                                                                                                                                  
                                              for suffix_in in case_2_is_in_flow.keys()
                                              }
                                 for is_weekday in week_days
                                } 
                             for user_profile in UserProfiles
                             }
                        for time_interval in list_time_intervals
                        } 
                    for str_day in list_all_avaliable_days_flows
                    }

# NOTE: Extract the null day
map_idx_cities_gdf_2_area_code = dict(zip(cities_gdf.index, cities_gdf[str_area_id_presenze]))  # create a map from the index of the cities gdf to the area code
# NOTE: Add column indices from AREA_CODE that is the one characteristic of df_presenze, df_od, but not to the case of generated  by gravity flows
df_distance_matrix = add_column_area_code_OD_df_distance(df_distance_matrix,
                                                        map_idx_cities_gdf_2_area_code,
                                                        str_col_origin=str_col_origin,
                                                        str_col_destination=str_col_destination,
                                                        str_area_code_origin_col=str_area_code_origin_col,
                                                        str_area_code_destination_col=str_area_code_destination_col
                                                        )  # add the area code to the origin and destination columns of the distance matrix

# NOTE: Extract the null day
print("Initialize null day OD-presenze...")
df_presenze_null_days = extract_presences_vodafone_from_bucket(s3,list_files_presenze, 2)                                                                                                      # NOTE: download the file from the bucket
# NOTE: Extract OD
df_od_null_days = extract_od_vodafone_from_bucket(s3,list_files_od, 2) 
df_od_null_days = add_column_is_week_and_str_day(df_od = df_od_null_days,
                                str_period_id_presenze = str_period_id_presenze,
                                col_str_day_od = col_str_day_od,
                                col_str_is_week = col_str_is_week,
                                is_null_day = True)

Tij_dist_baseline_init = join_Tij_Vodafone_with_distance_matrix(df_od=df_od_null_days,
                                                df_distance_matrix = df_distance_matrix,
                                                str_origin_od = str_origin_od,                                   # NOTE: origin area (ITA.<code>)
                                                str_destination_od = str_destination_od,                              # NOTE: destination area (ITA.<code>)    
                                                str_area_code_origin_col = str_area_code_origin_col,
                                                str_area_code_destination_col = str_area_code_destination_col)


Tij_dist_baseline_init = pipeline_initial_df_flows_aggregation_on_dat_hour_user_weekday(df = Tij_dist_baseline_init,
                                                                                    tuple_filters = (pl.col(str_trip_type_od) != "out-out",
                                                                                                        pl.col(str_trip_type_od) != "in-out"),
                                                                                    message_filters = (f"{str_trip_type_od} != out-out",
                                                                                                        f"{str_trip_type_od} != in-out"),
                                                                                    list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["hour_user_weekday"],            # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{str_day}_{is_weekday}
                                                                                    str_col_trips_to_be_aggregated = "TRIPS",
                                                                                    str_col_name_aggregated = "TRIPS",
                                                                                    method_aggregation="sum"
                                                                                    )

# Memory management: Force garbage collection after loading large datasets
gc.collect()   
# NOTE: Starting the pipeline from the dataset we have: presences and flows are those that will tell
# us the days of interest -> 2024-07-08,2024-08-23 ecc. A single file contains multiple weeks
# NOTE: Starting the pipeline from the dataset we have: presences and flows are those that will tell
# us the days of interest -> 2024-07-08,2024-08-23 ecc. A single file contains multiple weeks


for i,file in tqdm(enumerate(list_files_od),desc="Files OD Vodafone"):                                                                                           # for each file in the list of files
    print("Processing file: ", file,f" iter: {i}")                                                                                                                                          # print the file name
    # NOTE: Define the null day being october 2024 -> Avoid the analysis on it since we are considering just the summer days in relation to it.
    if file ==  DATA_PREFIX + 'vodafone-aixpa/od-mask_202410.parquet':
        is_null_day = True
    else:
        is_null_day = False
    if is_null_day:
        continue
    else:
        # NOTE: Extract the presenze and OD data from the bucket -> otherwise generate the flows from gravitational model
        if not is_generate_fluxes:
            # NOTE: Extract presenze
            df_presenze = extract_presences_vodafone_from_bucket(s3,list_files_presenze, i)                                                                                                      # NOTE: download the file from the bucket
            # NOTE: Extract OD
            df_od = extract_od_vodafone_from_bucket(s3,list_files_od, i) 
            # Add the column
            if "202410" in file:
                is_null_day = True
            else:
                is_null_day = False

            # NOTE: Fill info geodataframe with presences 
#            df_presenze_pd = df_presenze.to_pandas()  # Convert to pandas first: add -> AREA_CODE
#            df_presenze_unique = df_presenze_pd.drop_duplicates(subset=[str_area_id_presenze], keep='first')
#            cities_gdf = cities_gdf.merge(df_presenze_unique[str_area_id_presenze], left_on=str_area_id_presenze,right_on=str_area_id_presenze,how="left")
            # NOTE: Add the column is_week and str_day to the df_od
            df_od = add_column_is_week_and_str_day(df_od = df_od,
                                                    str_period_id_presenze = str_period_id_presenze,
                                                    col_str_day_od = col_str_day_od,
                                                    col_str_is_week = col_str_is_week,
                                                    is_null_day = is_null_day)  
            list_unique_days_od = df_od[col_str_day_od].unique().to_list()
            print(f"Extracted dates analysis: {list_unique_days_od}")            
            # NOTE: Join the distance matrix with the flows -> add the columns that hold information about the unit vector and the distance between O-D
            Tij_dist_init = join_Tij_Vodafone_with_distance_matrix(df_od=df_od,
                                                            df_distance_matrix = df_distance_matrix,
                                                            str_origin_od = str_origin_od,                                   # NOTE: origin area (ITA.<code>)
                                                            str_destination_od = str_destination_od,                              # NOTE: destination area (ITA.<code>)    
                                                            str_area_code_origin_col = str_area_code_origin_col,
                                                            str_area_code_destination_col = str_area_code_destination_col)
                        
            # NOTE: Initialize the dataframe flows to the form where the trips are the sum over all observations ut still are conditioned to the day, hour, user profile and weekday/weekend
            Tij_dist_init = pipeline_initial_df_flows_aggregation_on_dat_hour_user_weekday(df = Tij_dist_init,
                                                                                      tuple_filters = (pl.col(str_trip_type_od) != "out-out",
                                                                                                        pl.col(str_trip_type_od) != "in-out"),
                                                                                      message_filters = (f"{str_trip_type_od} != out-out",
                                                                                                         f"{str_trip_type_od} != in-out"),
                                                                                      list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["day_hour_user_weekday"],            # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{str_day}_{is_weekday}
                                                                                      str_col_trips_to_be_aggregated = "TRIPS",
                                                                                      str_col_name_aggregated = "TRIPS",
                                                                                      method_aggregation="sum"
                                                                                     )

            # Memory management: Delete intermediate dataframes after processing
#            del df_presenze_pd, df_presenze_unique
            gc.collect()
        else:
            list_unique_days_od = ["2024-09-09"]                                                                                                                                              # NOTE: the days of interest -> string format
            pass
        
        if not list_unique_days_od:
            print(f"Warning: No days found for file {file}. Skipping...")
            continue
        for str_day in list_unique_days_od:
            print("Begin Analysis: ",str_day)                                                                                                                                               # for each day
            is_skip = date_in_file_2_skip.get(list_files_od[i]) == str_day
            if is_skip:
                print(f"Skipping processing for file {list_files_od[i]} and day {str_day} as per skip list.")
                continue
            else:        
                datetime_day = pd.to_datetime(str_day)     
                # NOTE: Time intervals of interest
                # NOTE: Time intervals
                for time_interval in list_time_intervals:
                    print("Time interval: ", time_interval)                                                                                                                               # for each time interval
                    int_hour_start_window_interest = time_interval[0]                                                                                                                   # start time window of interest
                    int_hour_end_window_interest = time_interval[1]                                                                                                                     # end time window of interest
                    str_t = str(int_hour_start_window_interest)
                    str_t1 = str(int_hour_end_window_interest)
                    if int_hour_start_window_interest != 25:                                                                                                                   # for each user profile                                   
                        # NOTE: chnge the time according to the source                                                                                                                  
                        is_fluxes_hourly = True                                                                                                                         # NOTE: if the fluxes are generated hourly
                    else:
                        is_fluxes_hourly = False                                                                                                                         # NOTE: if the fluxes are generated hourly
                    for is_weekday in week_days:                                                                                                                                            # for each day type (weekday/weekend)
                        print(f"Processing {is_weekday}")                                                                                                                                              # print the day type
                        # NOTE: Days of interest
                        # NOTE: Profile user
                        print("Initialize flows and cities that will hold all columns analysis...")
                        global_cities_gdf_holding_all_columns_flows = cities_gdf.copy()                                                                                                                                # Create a global copy of cities_gdf to hold all columns: name_file_system: flows_all_analysis.parquet
                        global_Tij_holding_all_columns_flows = None                                                                                                                                                    # Create a global variable to hold Tij_dist with all columns:                         
                        for user_profile in UserProfiles:
                            Tij_dist = Tij_dist_init
                            Tij_dist_baseline = Tij_dist_baseline_init

                            if user_profile != "AGGREGATED":
                                filters_flows = (pl.col(col_str_day_od) == str_day,
                                                    pl.col(str_departure_hour_od) == int_hour_start_window_interest,
                                                    pl.col(str_origin_visitor_class_id_od) == UserProfile2IndexVodafone[user_profile],
                                                    pl.col(col_str_is_week) == is_weekday                                                         
                                                    )      
                                filters_flows_baseline = (                                                                                   # NOTE: Define the null day being 2024-10-01
                                                        pl.col(str_departure_hour_od) == int_hour_start_window_interest,
                                                        pl.col(str_origin_visitor_class_id_od) == UserProfile2IndexVodafone[user_profile],
                                                        pl.col(col_str_is_week) == is_weekday                                                         
                                                        )
                                message_filters = (f"{col_str_day_od} == {str_day}",
                                                    f"{str_departure_hour_od} == {int_hour_start_window_interest}",
                                                    f"{str_origin_visitor_class_id_od} == {user_profile}",
                                                    f"{col_str_is_week} == {is_weekday}")
                                message_filters_baseline = (                                                                                   # NOTE: Define the null day being 2024-10-01
                                                            f"{str_departure_hour_od} == {int_hour_start_window_interest}",
                                                            f"{str_origin_visitor_class_id_od} == {user_profile}",
                                                            f"{col_str_is_week} == {is_weekday}")                                        

                                pass                                                                                                                                                # if the user profile is not aggregated
                            else:
                                Tij_dist = pipeline_initial_df_flows_aggregation_on_dat_hour_user_weekday(df = Tij_dist_init,
                                                                            tuple_filters = (),
                                                                            message_filters = (),
                                                                            list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["day_hour_weekday"],            # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{str_day}_{is_weekday}
                                                                            str_col_trips_to_be_aggregated = "TRIPS",
                                                                            str_col_name_aggregated = "TRIPS",
                                                                            method_aggregation="sum"
                                                                            )
                                Tij_dist_baseline = pipeline_initial_df_flows_aggregation_on_dat_hour_user_weekday(df = Tij_dist_baseline_init,
                                                                                    tuple_filters = (),
                                                                                    message_filters = (),
                                                                                    list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["hour_weekday"],            # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{str_day}_{is_weekday}
                                                                                    str_col_trips_to_be_aggregated = "TRIPS",
                                                                                    str_col_name_aggregated = "TRIPS",
                                                                                    method_aggregation="sum"
                                                                                    )
                                # NOTE: We are summing over all the days as they are summed implicitly in Tij_dist_init (Vodafone gave us the sum over 15 days, here we sum over the user profiles)
                                Tij_dist_baseline = Tij_dist_baseline.with_columns((pl.col("TRIPS")/2).floor().alias("TRIPS"))  # Divide by two the trips since we are considering both nationalities
                                 
                                filters_flows = (pl.col(col_str_day_od) == str_day,
                                                    pl.col(str_departure_hour_od) == int_hour_start_window_interest,
                                                    pl.col(col_str_is_week) == is_weekday                                                         
                                                    )      
                                filters_flows_baseline = (                                                                                   # NOTE: Define the null day being 2024-10-01
                                                        pl.col(str_departure_hour_od) == int_hour_start_window_interest,
                                                        pl.col(col_str_is_week) == is_weekday                                                         
                                                        )
                                message_filters = (f"{col_str_day_od} == {str_day}",
                                                    f"{str_departure_hour_od} == {int_hour_start_window_interest}",
                                                    f"{col_str_is_week} == {is_weekday}")
                                message_filters_baseline = (                                                                                   # NOTE: Define the null day being 2024-10-01
                                                            f"{str_departure_hour_od} == {int_hour_start_window_interest}",
                                                            f"{col_str_is_week} == {is_weekday}")                                        
                                
                            print("Processing user profile: ", user_profile)                                                                                                                   # for each user profile
                            # NOTE: This is used to filter the buses
                            # Initialize variables that are relevant for the time analysis (time and user profile)
                            name_week_day = is_weekday                                                                                                                                  # name of the day type
                            # NOTE: These are the columns that we hold in the plot of the hierarchy (These are the ones that are in 
                            # the geojson produced by the MobilityHierarchy that are going to be important for the output plots)
                            columns_2_hold_geopandas_base = [str_area_id_presenze,str_centroid_lat,str_centroid_lon,str_col_comuni_name,str_grid_idx,"geometry"]                        # base columns to hold in the geopandas
                            # NOTE: Directory to save the output
                            str_dir_output_date = os.path.join(config[str_dir_output],str_day,f"{str_t}_{str_t1}",name_week_day)                                                                      # NOTE: create a directory for the date
                            Path(str_dir_output_date).mkdir(parents=True, exist_ok=True)                                                                                                # create the directory if it does not exist                

                            idx_case = 0
                            if WORK_IN_PROGRESS and os.path.exists(os.path.join(str_dir_output_date, f"most_critical_directions_{user_profile}_{str_t}_{str_t1}_{str_day}.html")):
                                print(f"Skipping analysis for {str_day} {str_t}-{str_t1} {user_profile} as output already exists.")
                                continue
                            else:
                                for suffix_in,is_in_flows in case_2_is_in_flow.items():
                                    # NOTE: initialize the names of the columns that will be used in the analysis 
                                    dict_column_flows = set_dict_column_names_flows_OD_analysis(dict_column_flows = dict_column_flows,str_day = str_day,time_interval = time_interval,user_profile = user_profile,
                                                                                                is_weekday = is_weekday,suffix_in = suffix_in,str_t = str_t,str_t1 = str_t1)
                                    # NOTE: Initialize the names of the columns that will be used in the analysis for the grid
                                    dict_column_grid = set_dict_column_names_grid_OD_analysis(dict_column_grid = dict_column_grid,str_day = str_day,time_interval = time_interval,user_profile = user_profile,
                                                                                                is_weekday = is_weekday,suffix_in = suffix_in,str_t = str_t,str_t1 = str_t1)
                                    # NOTE: Set the extension columns to hold for the grid analysis
                                    extension_columns_2_hold = set_columns_to_hold_for_OD_analysis(dict_column_grid = dict_column_grid,str_day = str_day,time_interval = time_interval,user_profile = user_profile,
                                                                                                    is_weekday = is_weekday,suffix_in = suffix_in)
                                    columns_2_hold_geopandas_for_flows_plot, columns_flows_2_be_merged_2_keep, on_colums_flows_2_join, on_columns_grid_2_join = define_columns_to_hold_and_merge_both_for_grid_and_flows_OD_analysis(columns_2_hold_geopandas_base = columns_2_hold_geopandas_base,
                                                                                                                                                                                                                                    extension_columns_2_hold = extension_columns_2_hold,str_col_origin = str_col_origin,
                                                                                                                                                                                                                                    str_col_destination = str_col_destination,str_grid_idx = str_grid_idx,dict_column_flows = dict_column_flows,str_day = str_day,
                                                                                                                                                                                                                                    time_interval = time_interval,user_profile = user_profile,is_weekday = is_weekday,suffix_in = suffix_in)
                                    # NOTE: Columns that are held by the final geopandas -> The one used for all plots
                                    # Generation Fluxes                                                                                                                                           #
                                    if is_generate_fluxes:                                                                                                                         # if the fluxes are generated
                                        Tij_dist, Tij_dist_baseline = routine_generation_flows(df_distance_matrix,
                                                                                                cities_gdf,
                                                                                                str_col_i = str_col_origin,
                                                                                                str_col_j = str_col_destination,
                                                                                                str_population_col = str_population_col_grid,
                                                                                                str_population_i_col = str_population_i,
                                                                                                str_population_j_col = str_population_j)
                                        gc.collect()
                                    else:
                                        # NOTE: Process vodafone data to match the format of generated fluxes
                                        # NOTE: The analysis is unique for (df_od,df_presenze,str_col_n_trips,str_day) -> other variables are needed for
                                        # functions and filtering but these steps are needed for the comparison of the baseline and the day of analysis.
                                        Tij_dist = filter_flows_by_conditions(df = Tij_dist,                                                                                                          # NOTE: DataFrame coming from Vodafone with OD data
                                                                              tuple_filters = filters_flows,
                                                                              message = message_filters
                                                                              )
                                        Tij_dist_baseline = filter_flows_by_conditions(df = Tij_dist_baseline,                                                                                                          # NOTE: DataFrame coming from Vodafone with OD data 
                                                                                tuple_filters = filters_flows_baseline,
                                                                                message = message_filters_baseline
                                                                                )
                                        Tij_dist = Tij_dist.with_columns(pl.col("TRIPS").alias(dict_column_flows[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]["str_col_n_trips"]))                                  # NOTE: rename the column with the trips to the one needed for the analysis
                                        Tij_dist_baseline = Tij_dist_baseline.with_columns((pl.col("TRIPS")/2).floor().alias("TRIPS"))  # Divide by two the trips since we are considering both nationalities
                                        Tij_dist_baseline = Tij_dist_baseline.with_columns(pl.col("TRIPS").alias(dict_column_flows[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]["str_col_n_trips_baseline"]))                # NOTE: rename the column with the trips to the one needed for the analysis
                                        print(f"Resulting flows to analyze:  {Tij_dist.shape} & baseline: {Tij_dist_baseline.shape} ")
                                        print(f"Total number trips recorded: {Tij_dist[dict_column_flows[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]['str_col_n_trips']].sum()}, & baseline: {Tij_dist_baseline[dict_column_flows[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]['str_col_n_trips_baseline']].sum()}")                                                                                                            # print the shape of the resulting dataframe
                                        print(f"Total number missing values: {Tij_dist.select(pl.col(dict_column_flows[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]['str_col_n_trips']).is_null().sum()).item()}, & baseline: {Tij_dist_baseline.select(pl.col(dict_column_flows[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]['str_col_n_trips_baseline']).is_null().sum()).item()}")                                                                                   # print the shape of the resulting dataframe
                                        # NOTE: Step 1 End
                                        
                                        # NOTE: Process vodafone data to match the format of generated fluxes - for null days
                                        # NOTE: Define null day being 2024-10-01 ->
                                        # NOTE: Compute it for every user profile and day and time interval
                                        # NOTE: Merge current flows with baseline for comparison (Step 2 Start)
                                        print(f"Compare Tij_dist to Tij_dist_baseline: {str_t}-{str_t1}, {user_profile}, {suffix_in}")
                                        Tij_dist = compute_difference_trips_col_day_baseline(Tij_dist = Tij_dist,
                                                                                            Tij_dist_baseline = Tij_dist_baseline,
                                                                                            str_col_n_trips = dict_column_flows[str_day][time_interval[0]][user_profile][is_weekday][suffix_in][f"str_col_n_trips"],
                                                                                            str_col_n_trips_baseline = dict_column_flows[str_day][time_interval[0]][user_profile][is_weekday][suffix_in][f"str_col_n_trips_baseline"],
                                                                                            str_col_difference_baseline = dict_column_flows[str_day][time_interval[0]][user_profile][is_weekday][suffix_in][f"str_col_difference_baseline"],
                                                                                            str_col_origin = str_col_origin,
                                                                                            str_col_destination = str_col_destination,
                                                                                            on_colums_flows_2_join = on_colums_flows_2_join
                                                                                            )
                                        
                                        # NOTE: Step 1 Start the Hierarchical Analysis
                                        if idx_case == 0:
                                            geojson_input_hierarchy = cities_gdf
                                        else:
                                            geojson_input_hierarchy = mh.grid
                                        # NOTE: Mobility Hierarchy Analysis - Inflows and Outflows -> Reformat Input and choose outside what it is going to be (Either in or out)
                                        mh, hotspot_2_origin_idx_2_crit_dest_idx, hotspot_flows, list_indices_all_fluxes_for_colormap = pipeline_mobility_hierarchy_time_day_type_trips(cities_gdf = geojson_input_hierarchy,
                                                                                                                                                                                        Tij_dist_fit_gravity = Tij_dist,
                                                                                                                                                                                        str_population_col_grid = str_population_col_grid,
                                                                                                                                                                                        str_col_comuni_name = str_col_comuni_name,
                                                                                                                                                                                        str_col_origin = str_col_origin,
                                                                                                                                                                                        str_col_destination = str_col_destination,
                                                                                                                                                                                        str_col_n_trips = dict_column_flows[str_day][time_interval[0]][user_profile][is_weekday][suffix_in][f"str_col_n_trips"],
                                                                                                                                                                                        str_col_total_flows_grid = dict_column_grid[str_day][time_interval[0]][user_profile][is_weekday][suffix_in][f"str_col_total_flows_grid_hierachical_routine"],
                                                                                                                                                                                        str_hotspot_prefix = str_hotspot_prefix,
                                                                                                                                                                                        str_centroid_lat = str_centroid_lat,
                                                                                                                                                                                        str_centroid_lon = str_centroid_lon,
                                                                                                                                                                                        str_grid_idx = str_grid_idx,
                                                                                                                                                                                        user_profile = user_profile,
                                                                                                                                                                                        str_t = str_t,
                                                                                                                                                                                        str_t1 = str_t1,
                                                                                                                                                                                        is_in_flows = is_in_flows,                                                                                                  # NOTE: is_in_flows = True means that we are considering the incoming fluxes to the hotspot
                                                                                                                                                                                        columns_2_hold_geopandas = None,
                                                                                                                                                                                        int_levels = 7)
                                        # NOTE: Save the important output of the Hierarchical analysis
                                        dict_output_hotspot_analysis[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]["hotspot_2_origin_idx_2_crit_dest_idx"] = hotspot_2_origin_idx_2_crit_dest_idx
                                        dict_output_hotspot_analysis[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]["list_indices_all_fluxes_for_colormap"] = list_indices_all_fluxes_for_colormap
                                        dict_output_hotspot_analysis[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]["hotspot_levels"] = hotspot_flows                                                                                                                                # NOTE: Column holding info about the total number of people that have passed through that grid cell
                                        print(f"Map flux generated for {str_t}-{str_t1}, {user_profile}, {suffix_in} flows")
                                        # NOTE: Save the maps for incoming fluxes -> NOTE: The str_output_dir_date is unique 
                                        save_output_mobility_hierarchy_dependent_is_in_fluxes(
                                                                                            str_dir_output_date = str_dir_output_date,
                                                                                            map_hierarchy = mh.fmap,
                                                                                            user_profile = user_profile,
                                                                                            hotspot_levels = dict_output_hotspot_analysis[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]["hotspot_levels"],
                                                                                            hotspot_2_origin_idx_2_crit_dest_idx = hotspot_2_origin_idx_2_crit_dest_idx,
                                                                                            str_t = str_t,
                                                                                            str_t1 = str_t1,
                                                                                            is_in_flows = is_in_flows                                                                                                  # NOTE: is_in_flows = True means that we are considering the incoming fluxes to the hotspot
                                                                                                )                                                                                                             # show the map in the browser
                                        # Memory management: Clear map_flux after saving
                                        gc.collect()                                        
                                        # NOTE: Global save the flows and cities_gdf by merging the str_day, str_t, str_t1, user_profile
                                        print(f"Day: {str_day}, Time: {str_t}-{str_t1}, User Profile: {user_profile}, Case: {suffix_in} - mh.flows: {mh.flows.columns}\nflows merged: {Tij_dist.columns}\nmh.grid: {mh.grid.columns}")
                                        
                                        # Ensure AREA_ID has the same type before merging
                                        if str_area_id_presenze in global_cities_gdf_holding_all_columns_flows.columns:
                                            global_cities_gdf_holding_all_columns_flows[str_area_id_presenze] = global_cities_gdf_holding_all_columns_flows[str_area_id_presenze].astype(str)
                                        if str_area_id_presenze in mh.grid.columns:
                                            mh.grid[str_area_id_presenze] = mh.grid[str_area_id_presenze].astype(str)

                                        global_Tij_holding_all_columns_flows, global_cities_gdf_holding_all_columns_flows = merge_flows_and_grid_with_global_to_obtain_unique_dfs(global_Tij_holding_all_columns_flows = global_Tij_holding_all_columns_flows,
                                                                                                                                                                                    flows_2_be_merged = Tij_dist,
                                                                                                                                                                                    global_cities_gdf_holding_all_columns_flows = global_cities_gdf_holding_all_columns_flows,
                                                                                                                                                                                    grid_single_case_2_be_merged = mh.grid,
                                                                                                                                                                                    columns_join_global_geopandas = columns_2_hold_geopandas_for_flows_plot,
                                                                                                                                                                                    columns_flows_2_be_merged_2_keep = columns_flows_2_be_merged_2_keep,
                                                                                                                                                                                    on_columns_flows_2_join = on_colums_flows_2_join,
                                                                                                                                                                                    on_columns_grid_2_join = on_columns_grid_2_join,
                                                                                                                                                                                    message_geojson = f"{str_day} {str_t}-{str_t1} {user_profile}",
                                                                                                                                                                                    message_flows = f"{str_day} {str_t}-{str_t1} {user_profile}"
                                                                                                                                                                                    )                                    
                                        # Memory management: Clear baseline analysis variables
                                        gc.collect()
                                        idx_case += 1
                                        print(f"Number columns global flows after join {str_t}-{str_t1} {user_profile}: ",len(global_Tij_holding_all_columns_flows.columns),f" cities: ",len(global_cities_gdf_holding_all_columns_flows.columns))
                                # NOTE: Visualize All Outputs
                                for suffix_in,is_in_flows in case_2_is_in_flow.items():                                                   
                                    # NOTE: TODO: filter flows and grid so to hold the feriale, day and hour

                                    map_flux = visualize_critical_fluxes_with_lines(grid = global_cities_gdf_holding_all_columns_flows,
                                                                                    df_flows = global_Tij_holding_all_columns_flows,
                                                                                    hotspot_2_origin_idx_2_crit_dest_idx = dict_output_hotspot_analysis[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]["hotspot_2_origin_idx_2_crit_dest_idx"],                        # NOTE:
                                                                                    str_col_total_flows_grid = dict_column_grid[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]["str_col_total_flows_grid_hierachical_routine"],
                                                                                    str_col_hotspot = dict_column_grid[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]["str_col_hotspot"],
                                                                                    str_col_n_trips = dict_column_flows[str_day][time_interval[0]][user_profile][is_weekday][suffix_in][f"str_col_n_trips"],
                                                                                    is_in_flows = is_in_flows,
                                                                                    str_col_origin = str_col_origin,
                                                                                    str_col_destination = str_col_destination,
                                                                                    str_centroid_lat = str_centroid_lat,
                                                                                    str_centroid_lon = str_centroid_lon,
                                                                                    str_col_comuni_name= str_col_comuni_name,
                                                                                    str_grid_idx = str_grid_idx,
                                                                                    str_caption_colormap = dict_column_flows[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]["str_caption_colormap_flows"],
                                                                                    str_colormap= 'YlOrRd'
                                                    )
                                    complete_path_map = os.path.join(str_dir_output_date,f"map_fluxes_{user_profile}_t_{str_t}_{str_t1}_{suffix_in}.html")                                                # path to the map file
                                    
                                    try:
                                        map_flux.save(complete_path_map)                                                                                                                         # save the map to the output folder
                                    except Exception as e:
                                        print(f"Error saving map_flux: {e}")
                                    print(f"Map critical flows:  {str_t}-{str_t1}, {user_profile}")
                                    
                                    # Plot
                                    fmap_baseline = plot_negative_differences_interactive(
                                                                                grid = geojson_input_hierarchy, 
                                                                                flows_negative = global_Tij_holding_all_columns_flows, 
                                                                                str_col_i = str_col_origin, 
                                                                                str_col_j = str_col_destination, 
                                                                                str_col_difference = dict_column_flows[str_day][time_interval[0]][user_profile][is_weekday][suffix_in]["str_col_difference_baseline"],
                                                                                str_centroid_lat = str_centroid_lat, 
                                                                                str_centroid_lon = str_centroid_lon, 
                                                                                caption_colorbar = f"Excess in tourism with respect to baseline {user_profile}"
                                                                                )
                                    with open(os.path.join(str_dir_output_date,"dict_output_hotspot_analysis.json"), "w") as f:
                                        json.dump(dict_output_hotspot_analysis, f, indent=4)                                                                                     # save the config file with the current configuration
                                    with open(os.path.join(str_dir_output_date, f"dict_column_flows.json"), "w") as f:
                                        json.dump(dict_column_flows, f, indent=4)                                                                                     # save the config file with the current configuration
                                    with open(os.path.join(str_dir_output_date, f"dict_column_grid.json"), "w") as f:
                                        json.dump(dict_column_grid, f, indent=4)                                                                                     # save the config file with the current configuration
                                    fmap_baseline.save(os.path.join(str_dir_output_date, f"most_critical_directions_{user_profile}_{str_t}_{str_t1}_{str_day}.html"))                                                                                     # save the map in the output folder                            
                                    del map_flux,fmap_baseline
                                    gc.collect()
                            
                            
                            
                            # NOTE: Initialize Pipeline for GTFS data
                            if is_gtfs_available:                                                                                                                         # if the gtfs is available
                                time_vector_OD = pd.timedelta_range(start = f"{int_hour_start_window_interest}h",end = f"{int_hour_end_window_interest}h",freq = f"{int_min_aggregation_OD}min")
                                str_col_n_trips_bus = f"n_trips_bus_{str_t}_{str_t1}"
                                columns_2_hold_geopandas_in_bus = [str_col_n_trips_bus, str_centroid_lat, str_centroid_lon,
                                                                    str_col_comuni_name, str_grid_idx, "geometry", str_col_hotspot_level_in]
                                str_col_n_users_bus = f"n_users_bus_{str_t}_{str_t1}"                                                                                                 # column name for the number of users bus
                                int_number_people_per_bus = 50                                                                                                                         # number of people per bus
                                str_col_difference_bus = f"difference_bus_{str_t}_{str_t1}"                            
                                idx_case_bus = 0
                                for suffix_in,is_in_flow_buses in case_2_is_in_flow.items():                                                   
                                    # ------------ Initialize Analysis of the Gtfs Data ------------- # 
                                    # NOTE: Init GTFS analysis
                                    config[f"{str_prefix_complete_path}_{str_name_gdf_stops}"] = os.path.join(str_dir_output_date,f"{str_name_gdf_stops}_{str_t}_{str_t1}.geojson")             # full path stops (gdf): NOTE: it changes from date to date
                                    print(f"Initializing gdf stops: ",config[f"{str_prefix_complete_path}_{str_name_gdf_stops}"])
                                    gdf_stops, trips_in_time_interval, stop_times_in_time_interval = compute_routes_trips(feed, str_day, time_vector_OD, config,
                                                                                                                           str_prefix_complete_path,str_name_gdf_stops,str_trip_idx)
                                    gc.collect()                                
                                    # NOTE: Associate Gtfs trips available in the Grid (shape of the city) -> helps estimate the number of trips that go from O -> D
                                    geojson_input_hierarchy, config, grid_idx_2_route_idx, stop_id_2_trip_id, stop_id_2_route_id, grid_idx_2_stop_idx, stop_idx_2_grid_idx, name_stop_idx_2_grid_idx = pipeline_associate_stops_trips_routes_2_grid(config,
                                                                                                                                                                                                                                    stop_times_in_time_interval,
                                                                                                                                                                                                                                    trips_in_time_interval,
                                                                                                                                                                                                                                    gdf_stops,
                                                                                                                                                                                                                                    geojson_input_hierarchy,
                                                                                                                                                                                                                                    str_grid_idx, str_stop_idx, str_trip_idx, str_route_idx,
                                                                                                                                                                                                                                    str_name_stop_id,
                                                                                                                                                                                                                                    type_grid_idx = type_grid_idx,
                                                                                                                                                                                                                                    type_stop_idx = type_stop_idx,
                                                                                                                                                                                                                                    type_trip_idx = type_trip_idx,
                                                                                                                                                                                                                                    type_route_idx = type_route_idx,                                                                                                                                                                                                                    
                                                                                                                                                                                                                                    str_col_n_stops = f"{str_col_n_stops}_{str_t}_{str_t1}",
                                                                                                                                                                                                                                    str_prefix_complete_path = str_prefix_complete_path,
                                                                                                                                                                                                                                    str_dir_output_date = str_dir_output_date,
                                                                                                                                                                                                                                    str_name_stop_2_trip = str_name_stop_2_trip,
                                                                                                                                                                                                                                    str_name_stop_2_route = str_name_stop_2_route,
                                                                                                                                                                                                                                    str_name_grid_2_stop = str_name_grid_2_stop,
                                                                                                                                                                                                                                    str_name_stop_2_grid = str_name_stop_2_grid,
                                                                                                                                                                                                                                    str_name_name_stop_2_grid = str_name_name_stop_2_grid,
                                                                                                                                                                                                                                    str_name_grid_2_route = str_name_grid_2_route,)                
                                    
                                    # NOTE: Add columns bus trip -> differ from OD fluxes
                                    mh.flows = pipeline_associate_route_trips_2_flows(mh.flows,
                                                                                    grid_idx_2_route_idx,
                                                                                    str_col_origin,
                                                                                    str_col_destination,
                                                                                    str_col_n_trips_bus)
                                    # NOTE: Mobility Hierarchy Analysis - Inflows and Outflows for Bus Trips
                                    mh_bus, map_flux_bus,hotspot_2_origin_idx_2_crit_dest_idx_bus, hotspot_in_flows_bus,list_indices_all_fluxes_for_colormap = pipeline_mobility_hierarchy_time_day_type_trips(geojson_input_hierarchy,
                                                                                                                                                    pl.DataFrame(mh.flows),
                                                                                                                                                    str_population_col_grid,
                                                                                                                                                    str_col_comuni_name,                                    # NOTE: Must be present in flows -> index geometry name: str   
                                                                                                                                                    str_col_origin,                                         # NOTE: Must be present in flows -> index geometry origin: int  
                                                                                                                                                    str_col_destination,                                    # NOTE: Must be present in flows -> index geometry destination: int
                                                                                                                                                    str_col_n_trips_bus,                                    # NOTE: Must be present in flows -> numer of trips: int
                                                                                                                                                    str_col_total_in_flows_grid,                            # NOTE: This column is created inside the function
                                                                                                                                                    str_col_total_out_flows_grid,                           # NOTE: This column is created inside the function
                                                                                                                                                    str_hotspot_prefix,
                                                                                                                                                    str_centroid_lat,
                                                                                                                                                    str_centroid_lon,
                                                                                                                                                    str_grid_idx,
                                                                                                                                                    "bus",
                                                                                                                                                    str_t,
                                                                                                                                                    str_t1,
                                                                                                                                                    is_in_flows = is_in_flow_buses,                                                                                                  # NOTE: is_in_flows = True means that we are considering the incoming fluxes to the hotspot
                                                                                                                                                    columns_2_hold_geopandas = columns_2_hold_geopandas_in_bus,
                                                                                                                                                    int_levels = 5)                                
                                    # NOTE: Save the output of the bus hierarchy analysis for Buses
                                    save_output_mobility_hierarchy_dependent_is_in_fluxes(                                   
                                                                                            str_dir_output_date = str_dir_output_date,
                                                                                            map_flux = map_flux_bus,
                                                                                            map_hierarchy = mh_bus.fmap,
                                                                                            user_profile = "bus",
                                                                                            hotspot_levels = hotspot_in_flows_bus,
                                                                                            hotspot_2_origin_idx_2_crit_dest_idx = hotspot_2_origin_idx_2_crit_dest_idx_bus,
                                                                                            str_t = str_t,
                                                                                            str_t1 = str_t1,
                                                                                            is_in_flows = is_in_flow_buses                                                                                                  # NOTE: is_in_flows = True means that we are considering the incoming fluxes to the hotspot
                                                                                                )  
                   
                                    if SAVE_SINGLE_GEOSPATIAL_FILES:
                                        save_output_hierarchy_analysis(config = config,
                                                                    str_dir_output_date = str_dir_output_date,
                                                                    flows = mh_bus.flows,
                                                                    grid = mh_bus.grid[columns_2_hold_geopandas],
                                                                    user_profile = "bus",
                                                                    str_t = str_t,
                                                                    str_t1 = str_t1,
                                                                        )                


                                    # NOTE: Here compute the difference between the number of trips bus and 
                                    # the number of trips in the flows                                    
                                    mh_bus.flows = mh_bus.flows.with_columns((pl.col(str_col_n_trips_bus)* int_number_people_per_bus).alias(str_col_n_users_bus))                                                                 # compute the number of users bus
                                    # Compute difference and filter
                                    # If mh.flows and mh_bus.flows are Pandas DataFrames:
                                    flows_merged_bus = mh.flows.merge(
                                                                mh_bus.flows.to_pandas()[[str_col_origin, str_col_destination, str_col_n_users_bus]],
                                                                on=[str_col_origin, str_col_destination],
                                                                how="left"
                                                            )
                                    flows_merged_bus = pl.DataFrame(flows_merged_bus)
                                    # NOTE: Compute the difference between the number of users bus and the number of trips (from OD) in the flows
                                    flows_merged_bus = flows_merged_bus.with_columns(
                                        (pl.col(str_col_n_users_bus) - pl.col(str_col_n_trips)).alias(str_col_difference_bus)
                                    )
                                    # NOTE: Filter the flows with negative differences (The buses fail to cover the demand at least of 10 people)
                                    flows_negative_bus = flows_merged_bus.filter(pl.col(str_col_difference_bus) < - 10)

                                    # Plot
                                    fmap = plot_negative_differences_interactive(
                                                                                mh.grid, 
                                                                                flows_negative_bus, 
                                                                                str_col_origin, 
                                                                                str_col_destination, 
                                                                                str_col_difference_bus,
                                                                                str_centroid_lat, 
                                                                                str_centroid_lon, 
                                                                                title="Direction with need for Bus Supply"
                                                                                )
                                    fmap.save(os.path.join(str_dir_output_date, f"need_for_bus_{str_t}_{str_t1}_{str_day}.html"))                                                                                     # save the map in the output folder
                                    # Save the map                                  
                                    with open(os.path.join(str_dir_output_date, f"config_{str_t}_{str_t1}.json"), "w") as f:
                                        json.dump(config, f, indent=4)                                                                                     # save the config file with the current configuration
                                    idx_case_bus += 1
                                    global_Tij_holding_all_columns_flows, global_cities_gdf_holding_all_columns_flows = merge_flows_and_grid_with_global_to_obtain_unique_dfs(global_Tij_holding_all_columns_flows = global_Tij_holding_all_columns_flows,
                                                                                                                                                                                flows_2_be_merged = flows_merged,
                                                                                                                                                                                global_cities_gdf_holding_all_columns_flows = global_cities_gdf_holding_all_columns_flows,
                                                                                                                                                                                grid_single_case_2_be_merged = mh.grid,
                                                                                                                                                                                columns_join_global_geopandas = columns_join_global_geopandas,
                                                                                                                                                                                columns_flows_2_be_merged_2_keep = columns_flows_2_be_merged_2_keep,
                                                                                                                                                                                on_columns_flows_2_join = on_colums_flows_2_join,
                                                                                                                                                                                on_columns_grid_2_join = [str_grid_idx],
                                                                                                                                                                                message_geojson = f"{str_day} {str_t}-{str_t1} {user_profile}",
                                                                                                                                                                                message_flows = f"{str_day} {str_t}-{str_t1} {user_profile}",
                                                                                                                                                                                is_join_flows = True,
                                                                                                                                                                                is_join_grid = True
                                                                                                                                                                                )
                                    print(f"Number columns global flows after join {str_t}-{str_t1} bus: ",len(global_Tij_holding_all_columns_flows.columns),f" cities: ",len(global_cities_gdf_holding_all_columns_flows.columns))                                    
                                    
                                    # Memory management: Clear bus analysis variables
                                    del flows_merged_bus, flows_negative_bus, fmap, str_col_difference_bus
                                    del gdf_stops, trips_in_time_interval, stop_times_in_time_interval
                                    del grid_idx_2_route_idx, stop_id_2_trip_id, stop_id_2_route_id
                                    del grid_idx_2_stop_idx, stop_idx_2_grid_idx, name_stop_idx_2_grid_idx
                                    del mh_bus, map_flux_bus
                                    del hotspot_2_origin_idx_2_crit_dest_idx_bus, hotspot_in_flows_bus
                                    gc.collect()

                                    # TODO: Save the routes that needs to be empowered from this criterion
                                    # NOTE: use grid_2_route_idx to get the routes to choose them and create a dictionary with the number of trips to be added.
                                    # NOTE: The number of trips to be added is the absolute value of the difference, so we can use the negative values to understand how many trips are needed.
                            
                            # Memory management: Clear large objects at the end of time interval processing
                            if 'mh' in locals(): 
                                del mh
                            if 'Tij_dist' in locals():
                                del Tij_dist
                            if 'Tij_dist_baseline' in locals():
                                del Tij_dist_baseline
                            if 'hotspot_2_origin_idx_2_crit_dest_idx' in locals():
                                del hotspot_2_origin_idx_2_crit_dest_idx
                            if 'hotspot_in_flows' in locals():
                                del hotspot_in_flows
                            
                            # Close any remaining matplotlib figures
                            safe_close_figures()
                            gc.collect()

                        global_cities_gdf_holding_all_columns_flows.to_file(os.path.join(str_dir_output_date, f"global_cities_gdf_holding_all_columns_flows_{str_day}.geojson"))
                        global_Tij_holding_all_columns_flows.write_parquet(os.path.join(str_dir_output_date, f"global_Tij_holding_all_columns_flows_{str_day}.parquet"))
                    # Memory management: Clear user profile specific variables
                    safe_close_figures()  # Close any figures from visualization
                    gc.collect()
            
                # Memory management: Clear time interval variables  
                if 'time_vector_OD' in locals() and time_vector_OD is not None:
                    del time_vector_OD
                if 'str_time_vector' in locals() and str_time_vector is not None:
                    del str_time_vector
                gc.collect()
                
                # Memory management: Clear day-specific variables
            gc.collect()
        
        # Memory management: Clear file processing variables
        if 'df_presenze' in locals() and df_presenze is not None:
            del df_presenze
        if 'df_od' in locals() and df_od is not None:
            del df_od  
        gc.collect()

# Final memory management: Clear remaining global variables
print("Performing final memory cleanup...")
if 'cities_gdf' in locals():
    del cities_gdf
if 'df_distance_matrix' in locals():
    del df_distance_matrix
if 'direction_matrix' in locals():
    del direction_matrix
if 'distance_matrix' in locals():
    del distance_matrix
if 'Istat_obj' in locals():
    del Istat_obj
if 'feed' in locals():
    del feed
if 'df_presenze_null_days' in locals():
    del df_presenze_null_days
if 'df_od_null_days' in locals():
    del df_od_null_days
if 'data_handler' in locals():
    del data_handler

# Final garbage collection
gc.collect()
print("Memory cleanup completed.")
## MARKOWITZ APPROACH FOR DIFFUSIONE 3 ###
cities_gdf = gpd.read_file(os.path.join(BASE_DIR,"Data","mavfa-fbk_AIxPA_tourism-delivery_2025.08.22-zoning","fbk-aixpa-turismo.shp"))

print("Extract list of files from bucket...")
list_files_od, list_files_presenze, list_str_dates_yyyymm = extract_filenames_and_date_from_bucket(bucket)
date_in_file_2_skip = {DATA_PREFIX + 'vodafone-aixpa/od-mask_202407.parquet':"2024-08-08",
                       DATA_PREFIX + 'vodafone-aixpa/od-mask_202408.parquet':"2024-07-23"}
# NOTE: Extract the null day
print("Initialize null day OD-presenze...")
df_presenze_null_days = extract_presences_vodafone_from_bucket(s3 = s3,
                                                            list_files_presenze = list_files_presenze, 
                                                            i = 2)                                                                                                      # NOTE: download the file from the bucket
df_presenze_null_days = add_is_weekday_from_period_presenze_null_days(df = df_presenze_null_days, 
                                                                      period_col= str_period_id_presenze, 
                                                                      is_weekday_col= col_str_is_week)


# NOTE: Extract the stack of presences -> the overtouristic dataframe for presences
print("Stacking the presences data...")
stack_df_presenze_original = concat_presences(list_files_presences = list_files_presenze, 
                                    s3 = s3, 
                                    col_str_day_od = col_str_day_od, 
                                    col_period_id = str_period_id_presenze)

# NOTE: Add holiday column
stack_df_presenze_original = add_holiday_columun_df_presenze(stack_df_presenze = stack_df_presenze_original, 
                                                    col_str_day_od = col_str_day_od,
                                                    public_holidays = public_holidays,
                                                    col_str_is_week = col_str_is_week)

is_covariance_standardized = False
for is_weekday in week_days:
    cities_gdf = gpd.read_file(os.path.join(BASE_DIR,"Data","mavfa-fbk_AIxPA_tourism-delivery_2025.08.22-zoning","fbk-aixpa-turismo.shp"))
    columns_portfolio = []
    for hour_id in hour_ids:
        # NOTE: Filter by weekday / holiday -> Doing every hour since compute average takes away all the columns (it is logically inconsistent)
        stack_df_presenze_week_day = stack_df_presenze_original.filter(pl.col(col_str_is_week) == is_weekday)    
        df_presenze_null_days_week_day = df_presenze_null_days.filter(pl.col(col_str_is_week) == is_weekday)
        # NOTE: in aggregate_presences                                                                        # None means all nations    
        col_total_presences_oct_no_hour = f"total_presences_oct_no_hour_{hour_id}"                          # total presences in October without filtering by hour
        col_total_presences_tour_no_hour = f"total_presences_no_hour_{hour_id}"                             # total presences (touristic months) without filtering by hour
        # NOTE: To insert inside loop in hours
        col_total_presences_tour = f"total_presences_{hour_id}"                                             # total presences at hour_id
        # NOTE: When starting Markowitz
        col_tot_diff_oct = f"total_diff_oct_{hour_id}"                                                      # total difference October                   
        col_tot_diff_october_mean_0 = f"total_diff_october_mean_0_{hour_id}"                                # total difference October - mean 0   
        col_tot_diff_october_mean_0_var_1 = f"total_diff_october_mean_0_var_1_{hour_id}"                    # total difference October - mean 0 - var 1  (For random matrix standardization)
        str_column_cov = f"cov_{hour_id}"
        str_col_portfolio = f"portfolio_{hour_id}"
        # NOTE: Add the colum for the portfolio associated to the hour
        columns_portfolio.append(str_col_portfolio)
        col_tot_diff_october_var_1 = f"total_diff_october_var_1_{hour_id}"
        col_expected_return = f"expected_return_{hour_id}"
        col_std = f"std_day_{hour_id}"



        ########################################################
        ############### NULL DAY INITIALIZATION ################
        ########################################################

        print("Compute the total number of presences for each AREA_ID...")
        df_presenze_null_days_week_day = compute_presences_average(
                                                        df_presenze_null_days = df_presenze_null_days_week_day,
                                                        str_area_id_presenze = str_area_id_presenze,
                                                        str_presences_presenze = str_presences_presenze,
                                                        col_out_presenze = col_total_presences_oct_no_hour,
                                                        is_group_by_hour = False,
                                                        col_hour_id = str_time_block_id_presenze,
                                                        hour_id = hour_id,
                                                        is_nationality_markowitz_considered = False,
                                                        nationality_col = str_country_presenze,
                                                        nation = nation        
                            )


        #############################################################
        ############ PREPROCESS RAW DATA TO MARKOWITZ ###############
        ############################################################# 
        # NOTE: Length time
        list_str_days = list(stack_df_presenze_original[col_str_day_od].unique())
        # NOTE: Aggregate by nation and different groups -> This defines the the dataframe that associate a count to each t in T. NOTE that without this you have more groups of presences for each day
        stack_df_presenze_week_day = aggregate_presences(
                                                        df_presenze = stack_df_presenze_week_day,
                                                        col_str_day = col_str_day_od,
                                                        str_area_id_presenze = str_area_id_presenze,
                                                        str_presences_presenze = str_presences_presenze,
                                                        col_out_presenze = col_total_presences_tour_no_hour,
                                                        is_group_by_hour = True,
                                                        col_hour_id = str_time_block_id_presenze,
                                                        hour_id = hour_id,
                                                        is_nationality_markowitz_considered = is_nationality_markowitz_considered,
                                                        nationality_col = str_country_presenze,
                                                        nation = nation
                                                    )
        # NOTE: Compute correlation matrix X^T X (Wishart) in df format 
        if is_covariance_standardized:
            column_return = col_tot_diff_oct +"_over_std"    
        else:
            column_return = col_tot_diff_oct

        # NOTE: Compute the normalized covariance -> It is not for testing but chooses the return from the expectation
        stack_df_presenze = compute_starting_risk_column_from_stack_df(df_presenze_null_days = df_presenze_null_days_week_day,
                                                    stack_df_presenze = stack_df_presenze_week_day,
                                                    str_area_id_presenze = str_area_id_presenze,
                                                    col_total_presences_tour_no_hour = col_total_presences_tour_no_hour,
                                                    col_total_presences_oct_no_hour = col_total_presences_oct_no_hour,
                                                    col_return = column_return
                                                    )        
        # NOTE: Compute the expected return -> It is not for testing but chooses the return from the expectation
        df_mean = compute_expected_return_from_stack_df(stack_df_presenze = stack_df_presenze,
                                                        col_return = column_return,                                      # NOTE: This is expected i markowitz to be: col_tot_diff_oct
                                                        col_expected_return = col_expected_return,
                                                        str_area_id_presenze = str_area_id_presenze,
                                                        is_return_standardized = is_covariance_standardized,
                                                        col_std = col_std
                                                        )
        # NOTE: We define here the expected return: -> other approaches could be inserted here.
        expected_return = df_mean[col_expected_return].to_numpy()
        # NOTE: Standardize the return time series
        stack_df_presenze_mean_var = standardize_return_stack_df(stack_df_presenze = stack_df_presenze,
                                                                df_mean = df_mean,
                                                                col_return = column_return,
                                                                str_area_id_presenze = str_area_id_presenze,
                                                                is_standardize_return = is_covariance_standardized,
                                                                col_std = col_std)

        correlation_df = compute_correlation_matrix_df_from_time_series(stack_df_presenze_mean_var = stack_df_presenze_mean_var,
                                                                        str_area_id_presenze = str_area_id_presenze,
                                                                        col_str_day_od = col_str_day_od,
                                                                        col_return = column_return,
                                                                        str_column_cov = str_column_cov)    
        # NOTE: Extract area_to_index and index_to_area
        area_to_index, index_to_area = get_area_id_to_idx_mapping(cov_df = correlation_df, 
                                                                str_area_id_presenze = str_area_id_presenze)

        ##############################################################
        ####################### RMT Clean Matrix #####################
        ##############################################################

        # NOTE: Compute q = T/N
        q = from_areas_and_times_to_q(area_to_index = area_to_index,
                                    list_str_days = list_str_days)

        
        # NOTE: Transform covariance DataFrame into numpy matrix and create area mapping
        cov_matrix_numpy = from_df_correlation_to_numpy_matrix(cov_df = correlation_df, 
                                                            str_area_id_presenze = str_area_id_presenze, 
                                                            str_column_cov = str_column_cov, 
                                                            area_to_index = area_to_index)
        # NOTE: Clean the correlation matrix using RMT
        C_clean, eigvals_clean, eigvecs = rmt_clean_correlation_matrix(C = cov_matrix_numpy, 
                                                                       q = q,
                                                                       is_bulk_mean = True)

        
        # NOTE: Compute MP limits and mask of significant eigenvalues
        if is_covariance_standardized:
            sigma = None
        else:
            sigma = np.mean(df_mean[col_std].to_numpy())
        lambda_minus, lambda_plus, mask_eigvals = compute_MP_limits_and_mask(eigvals_clean, 
                                                                            q, 
                                                                            is_covariance_standardized= is_covariance_standardized, 
                                                                            sigma = sigma)        
                                                                            
        plot_pastur(eigvals_clean)

        ##############################################################
        #################### Markowitz procedure #####################
        ##############################################################
        # NOTE: Extract portfolio weights from significant eigenpairs
        portfolio_weights = extract_portfolio_from_eigenpairs(C_clean = C_clean, 
                                                              eigvals_clean = eigvals_clean, 
                                                              eigvecs = eigvecs, 
                                                              expected_return = expected_return, 
                                                              sum_w = 1,
                                                              is_normalize_portfolio=True)
        # NOTE: Map portfolio weights to cities_gdf and plot -> compute the portoflio 
        cities_gdf = map_portfolio_numpy_to_cities_gdf(cities_gdf = cities_gdf,
                                        portfolio_weights = portfolio_weights,
                                        index_to_area = index_to_area,
                                        str_area_id_presenze = str_area_id_presenze,
                                        str_col_portfolio = str_col_portfolio)
        cities_gdf = cities_gdf.merge(df_mean.to_pandas(),on=str_area_id_presenze)
#        fig,ax = plt.subplots(1,3, figsize = (10,10))
#        plot_polygons_and_with_scalar_field(cities_gdf,str_col_portfolio,ax[0],fig,title = f"portfolio {hour_id} {is_weekday}")        
#        plot_polygons_and_with_scalar_field(cities_gdf,col_expected_return,ax[1],fig,title = "<oct - day> ")
#        plot_polygons_and_with_scalar_field(cities_gdf,col_std,ax[2],fig,title = "standard deviation day")
#        plt.show(fig)
#        plt.close(fig)
    # NOTE: Plot portfolio map
    path_base_portfolio = os.path.join(BASE_DIR,"Output",f"{is_weekday}")
    path_save_portfolio = os.path.join(path_base_portfolio,f"portfolio_map_{hour_id}.html")
    os.makedirs(path_base_portfolio,exist_ok=True)
    plot_portforlio_map_multiple_layers(cities_gdf = cities_gdf,
                                    str_area_id_presenze = str_area_id_presenze,
                                    columns_to_plot = columns_portfolio,
                                    str_col_comuni_name = str_col_comuni_name,
                                    save_path = path_save_portfolio)
    cities_gdf.to_file(os.path.join(path_base_portfolio,"goedataframe_input_plots_markowitz.geojson"))
    informative_text_output = "Explicit description variables needed for plot: " + f"\nstr_area_id_presenze = {str_area_id_presenze}\n columns_to_plot: "
    for col in columns_portfolio:
        informative_text_output += col +", "
    informative_text_output += f"\nstr_col_comuni_name: {str_col_comuni_name}"
    with open(os.path.join(path_base_portfolio,"output_variable_description.txt"), "w") as f:
        f.write(informative_text_output)