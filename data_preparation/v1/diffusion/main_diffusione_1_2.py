from data_preparation.diffusion.global_import import *
import itertools

from data_preparation.utils import init_s3, BASE_DIR

def get_Gtfs_data(config, str_prefix_complete_path, str_name_dataset_gtfs):
    """
    Load GTFS data from the specified path.
        Returns:
            gdf_transport: GeoDataFrame containing transport data
            graph_transport: Graph object representing the transport network
    """
    if os.path.exists(config[f"{str_prefix_complete_path}_{str_name_dataset_gtfs}"]):                                             # NOTE: check if the gtfs file exists
        print("GTFS file exists, loading it")                                                                                     # NOTE: load gtfs file
        feed = Preprocessing_gtfs(config[f"{str_prefix_complete_path}_{str_name_dataset_gtfs}"])                                  # NOTE: load gtfs file from the directory set -> feed object is typical of gtfs_kit
        is_gtfs_available = False
    else:
        print("GTFS file does not exist, downloading it")                                                                         # NOTE: download gtfs file
        is_gtfs_available = False
        feed = None
    return feed, is_gtfs_available

def initialize_geodataframe_polygons(config, complete_path_Istat_population = complete_path_Istat_population,
                                    str_prefix_complete_path = str_prefix_complete_path, str_name_shape_city = str_name_shape_city, str_name_centroid_city = str_name_centroid_city):
    # ------------------  Extract Cities of interest from Vodafone ------------------ #                                                                                 # NOTE: here you can define what is the list of comuni you want to consider
    print("Compute comuni polygons...")

    #attendences_foreigners = data_handler.vodafone_attendences_df.join(data_handler.vodafone_aree_df, on='locId', how='left',coalesce=True)                                                 # joining dataframes (just to have the needed columns)
    #names_zones_to_consider = attendences_foreigners.filter(pl.col("locName").is_in(["comune"])).unique("locDescr")["locDescr"].to_list()                               # pick the comune
    complete_path_shape_gdf = config[f"{str_prefix_complete_path}_{str_name_shape_city}"]                                                                               # path to the shape file of the cities
    complete_path_centroid_gdf = config[f"{str_prefix_complete_path}_{str_name_centroid_city}"]                                                                         # path to the centroids associated to the cities
    #centroids_gdf,cities_gdf = pipeline_extract_boundary_and_centroid_gdf_from_name_comuni(names_zones_to_consider,                                                     # list of the comuni to consider        
    #                                                                                       complete_path_shape_gdf,                                                     #
    #                                                                                       complete_path_centroid_gdf)

    # ---------------- Extrct Population From Istat ------------------ #
    print("Upload Istat data...")
    Istat_obj = Istat_population_data(complete_path_Istat_population)

    # NOTE: Read geometries from the shapefile of the cities
    cities_gdf = gpd.read_file(os.path.join(BASE_DIR,"Data","mavfa-fbk_AIxPA_tourism-delivery_2025.08.22-zoning","fbk-aixpa-turismo.shp"))
    #cities_gdf = gpd.read_file(os.path.join(BASE_DIR,"Data","shapefile_fbk_2025.05.21","fbk.shp"))

    # NOTE: Join the informations of the population (from Istat) with the geometries of the city
    cities_gdf = simple_join_cities_with_population(cities_gdf, 
                                        Istat_obj.population_by_comune,
                                        str_col_comuni_istat = str_col_comuni_istat,
                                        str_col_popolazione_totale = str_population_col_grid,
                                        str_col_city_name = str_col_comuni_name,
                                        is_Vodafone_Trento_ZDT = True)                                                                                        # NOTE: here we join the cities with the population data from Istat
    # NOTE: When the city appears in subdivisions (like Trento, Rovereto, etc.) we need to know how much of the population is in each diivision

    cities_gdf = add_column_area_and_fraction(cities_gdf, 
                                    str_col_comuni_name,
                                    str_col_area = str_col_area,
                                    str_col_tot_area = str_col_tot_area,
                                    str_col_fraction = str_col_fraction,
                                    crs_proj = 3857, 
                                    crs_geographic = 4326)
    # NOTE: When there are multiple subdivisions we add an integer suffix

    cities_gdf = add_suffix_to_repeated_values(cities_gdf, str_col_comuni_name)

    # NOTE: We associate population as the fraction of the area of that sub-region times the total population of the city
    cities_gdf = redistribute_population_by_fraction(cities_gdf, 
                                        str_col_popolazione_totale = str_population_col_grid, 
                                        str_col_fraction = str_col_fraction,
                                        str_col_comuni_name = str_col_comuni_name,
                                        conserve_total=True)

    # ------- Users Profiles ------- #                                                                                                                                  # NOTE: here you can define what is the list of user profiles you want to consider
    #UserProfiles = attendences_foreigners[str_user_profile_vodafone_col].unique().to_list()                                                                             # list of the user profiles ['VISITOR', 'TOURIST', 'COMMUTER', 'INHABITANT']
    #UserProfiles.append("AGGREGATED")                                                                                                                                   # add the aggregated user profile -> NOTE: the analysis for fluxes will be done on all these.

    return cities_gdf, Istat_obj

def init_distance_matrix_associated_to_polygons(cities_gdf, config, str_name_distance_matrix = str_name_distance_matrix, str_centroid_lat = str_centroid_lat, str_centroid_lon = str_centroid_lon,str_dir_output = str_dir_output):
    """
    Initialize the distance matrix associated to the polygons of the cities.
        Returns:
            df_distance_matrix: DataFrame containing the distance matrix
            config: Updated configuration dictionary with distance matrix path
    NOTE: The naming of the string of the directory is not completely consistent, pay attention at how you structure it. 
    """
    # ---------- Distance and Direction Matrix ------------ #
    config[str_name_distance_matrix] = os.path.join(config[str_dir_output],f"{str_name_distance_matrix}.parquet")      # path to the distance matrix file
    complete_path_direction_distance_df = config[str_name_distance_matrix]                                                                                          # path to the distance matrix file
    print(f"Compute distance and direction matrix: {complete_path_direction_distance_df}")                                                                          # path to the distance matrix file
    direction_matrix,distance_matrix = compute_direction_matrix_optimized(cities_gdf,                                                                                #
                                        str_centroid_x_col = str_centroid_lat,                                                                                                        #
                                        str_centroid_y_col = str_centroid_lon,                                                                                                        #
                                        complete_path_direction_distance_df = complete_path_direction_distance_df
                                        )                                                                                        # compute the distance and direction matrix, save it in the output folder
    df_distance_matrix = direction_distance_2_df(direction_matrix,                                                                                                  #                               
                                                distance_matrix,                                                                                                   #
                                                complete_path_direction_distance_df
                                                )   


    return df_distance_matrix, config

def get_informations_about_available_dates_from_files(bucket, s3, col_str_day_od, str_period_id_presenze, col_str_is_week):
    """
    Extract filenames and available dates from the S3 bucket.
        Returns:
            list_files_od: List of OD files in the bucket 
            list_files_presenze: List of presence files in the bucket
            list_str_dates_yyyymm: List of available dates in 'YYYYMM' format
            list_all_avaliable_days_flows: List of all available days for analysis flows
    """
    print("Extract list of files from bucket...")
    list_files_od, list_files_presenze, list_str_dates_yyyymm = extract_filenames_and_date_from_bucket(bucket)
    print("Extract days available for analysis flows...")
    list_all_avaliable_days_flows = extract_all_days_available_analysis_flows_from_raw_dataset(list_files_od,col_str_day_od,str_period_id_presenze,col_str_is_week,s3)                             # NOTE: Needed to create dict_column_flows,grid for post-processing 
    return list_files_od, list_files_presenze, list_str_dates_yyyymm, list_all_avaliable_days_flows

def initialize_df_null_day_dataframe(cities_gdf, df_distance_matrix, s3, list_files_presenze, list_files_od,str_col_origin = str_col_origin, str_col_destination = str_col_destination,
                                    str_area_code_origin_col = str_area_code_origin_col, str_area_code_destination_col = str_area_code_destination_col,
                                    str_area_id_presenze = str_area_id_presenze, str_period_id_presenze = str_period_id_presenze,
                                    col_str_day_od = col_str_day_od, col_str_is_week = col_str_is_week,
                                    str_origin_od = str_origin_od, str_destination_od = str_destination_od):
    """
    Initialize dataframes for null day analysis.
        Returns:
            df_od_null_days: DataFrame containing OD data for null days
            df_presenze_null_days: DataFrame containing presence data for null days
            df_distance_matrix: Updated distance matrix with area codes
    Description:
    - get the dictionary that maps the integer index [from 0 to N-1 for N cities (numpy,jax, torch, numerical needs)]
    - add the area code to the distance matrix (since the distance matrix is initialized with numerical needs in mind)
    - extract the null day presences and OD data from the bucket (NOTE: it is the last file in list_files_presenze, no check is done, it is just empirical, it may break if something changes)
    - add the columns for the day of the week and if it is a week or not (needed for the hierarchical classification of flows)
    - join the OD data with the distance matrix to have the distances and directions
    Returns:
        df_od_null_days: DataFrame containing OD data for null days (with level of aggregation: hourly, weekly, user) -> that is sum-aggregated over nationalities 
        df_presenze_null_days: DataFrame containing presence data for null days, (with level of aggregation: hourly, daily, weekly, user) -> that is sum-aggregated over nationalities
        df_distance_matrix: Updated distance matrix with area codes
    """
    print("Add area codes to distance matrix...")
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


    df_od_null_days = join_Tij_Vodafone_with_distance_matrix(df_od=df_od_null_days,
                                                    df_distance_matrix = df_distance_matrix,
                                                    str_origin_od = str_origin_od,                                   # NOTE: origin area (ITA.<code>)
                                                    str_destination_od = str_destination_od,                              # NOTE: destination area (ITA.<code>)    
                                                    str_area_code_origin_col = str_area_code_origin_col,
                                                    str_area_code_destination_col = str_area_code_destination_col)


    return df_od_null_days, df_presenze_null_days, df_distance_matrix

def save_geodafeame_in_directory_output_and_init_global_geodata_and_global_geo_flows(cities_gdf, config, str_grid_idx, columns_2_hold_geopandas_base, str_dir_output = str_dir_output):
    """
    Save the GeoDataFrame in the output directory and initialize global variables.
        Description:
        - Save the GeoDataFrame with base columns to a GeoJSON file in the output directory
        - Initialize global variables for holding all columns of flows and the GeoDataFrame
    """ 
    # Save the output at the base level of
    cities_gdf[str_grid_idx] = cities_gdf.index  # add the grid idx as a column
    cities_gdf[columns_2_hold_geopandas_base].to_file(os.path.join(config[str_dir_output],f"cities_gdf_base_columns.geojson"),driver="GeoJSON")  # save the base columns of the cities gdf
    global_Tij_holding_all_columns_flows = None 
    global_cities_gdf_holding_all_columns_flows = cities_gdf
    return global_Tij_holding_all_columns_flows, global_cities_gdf_holding_all_columns_flows


def initialize_concatenated_od_dataframe(list_files_od, s3, str_period_id_presenze, col_str_day_od, col_str_is_week,
                                        df_distance_matrix, str_origin_od = str_origin_od, str_destination_od = str_destination_od,
                                        str_area_code_origin_col = str_area_code_origin_col, str_area_code_destination_col = str_area_code_destination_col,
                                        str_trip_type_od = str_trip_type_od,):
    """
    Initialize concatenated OD dataframe 
        Returns:
            df_concat: Concatenated OD DataFrame with additional columns
            df_od_with_just_in_in_out_in_trips: DataFrame filtered for in-in and out-in trips
    Description:
    - concatenate all OD files from the list of files
    - add columns for day of the week and whether it is a week or not
    - join with the distance matrix to get distances and directions
    - filter for in-in and out-in trips only
    """
    df_concat = concat_df_od_and_add_columns(list_files_od, 
                                            s3, 
                                            str_period_id_presenze, 
                                            col_str_day_od, 
                                            col_str_is_week)  

    # NOTE: Prepare the dataframe to give to the prepare_flow_dataframe_for_hierarchical_prcedure: essentially here it considers just the in-in and out-in trips, and joins with the distance matrix -> i,j col are given
    df_od_with_just_in_in_out_in_trips = default_initial_preparation_common_to_all_cases_df_flows_not_baseline(df_od = df_concat,
                                                                            df_distance_matrix = df_distance_matrix,
                                                                            str_origin_od = str_origin_od,
                                                                            str_destination_od = str_destination_od,
                                                                            str_area_code_origin_col = str_area_code_origin_col,
                                                                            str_area_code_destination_col = str_area_code_destination_col,
                                                                            str_trip_type_od = str_trip_type_od)
    return df_od_with_just_in_in_out_in_trips


def level_aggregation_concat_od_dataframe_and_null_days(list_all_avaliable_days_flows, list_time_intervals, user_profile, UserProfiles, week_days, case_2_is_in_flow, case_pipeline,
                                                        df_od_with_just_in_in_out_in_trips, df_od_null_days):
    """
    Level aggregation for concatenated OD dataframe and null days.
    Description:
    - Initialize dictionaries to hold grid flows, columns, and hotspot analysis
    - Aggregate the dataframe at the required level together via prepare_flow_dataframe_for_hierarchical_prcedure
    Returns:
        dict_column_flows_aggregation_weekday: Dictionary for flows aggregation by weekday
        dict_column_grid_aggregation_weekday: Dictionary for grid aggregation by weekday
        dict_output_hotspot_analysis_aggregation_weekday: Dictionary for hotspot analysis aggregation by weekday
        Tij_dist_init: Initial flow distribution DataFrame
        Tij_dist_baseline_init: Baseline flow distribution DataFrame
    NOTE: This prepares the daaframe with the level of aggregation wanted 
    NOTE: The level of aggregation is given by the case_pipeline variable (if the name holds a variable then the average-sum is not computed over that variable)
    NOTE: user profile is given to differentiate the AGGREGATED case from the others
    """
    dict_column_flows_aggregation_weekday, dict_column_grid_aggregation_weekday, dict_output_hotspot_analysis_aggregation_weekday = initialize_dicts_that_hold_grid_flows_columns_and_hotspot_analysis(list_all_avaliable_days_flows = list_all_avaliable_days_flows, 
                                                                                                                                                                                                        list_time_intervals = list_time_intervals,
                                                                                                                                                                                                        UserProfiles = UserProfiles,
                                                                                                                                                                                                        week_days = week_days,
                                                                                                                                                                                                        case_2_is_in_flow = case_2_is_in_flow,
                                                                                                                                                                                                        case_pipeline = case_pipeline)


    print("[DEBUG] Check the case pipeline and user profile: ", case_pipeline, user_profile,df_od_null_days.shape, df_od_with_just_in_in_out_in_trips.shape)
    # NOTE: Aggregate the dataframe at the level you need
    Tij_dist_init, Tij_dist_baseline_init = prepare_flow_dataframe_for_hierarchical_prcedure(df_od_with_just_in_in_out_in_trips = df_od_with_just_in_in_out_in_trips,
                                                                                            Tij_dist_baseline_init = df_od_null_days ,
                                                                                            case = case_pipeline ,
                                                                                            user_profile = user_profile)
    return dict_column_flows_aggregation_weekday, dict_column_grid_aggregation_weekday, dict_output_hotspot_analysis_aggregation_weekday, Tij_dist_init, Tij_dist_baseline_init


def main_diffusione_1_2_by_case_pipeline(global_Tij_holding_all_columns_flows, global_cities_gdf_holding_all_columns_flows, dict_column_flows_aggregation_weekday, dict_column_grid_aggregation_weekday, dict_output_hotspot_analysis_aggregation_weekday, # Global variables that will contain the output
                                         Tij_dist_init, Tij_dist_baseline_init ,                                                                                            # Dataframes with the flows at the level of aggregation needed that will be used for in-out analysis
                                         case_2_is_in_flow,                                                                                                                 # Dictionary that holds if we are considering in or out flows for the analysis                  
                                         case_pipeline, user_profile, is_weekday, str_day, int_hour_start_window_interest, time_interval, str_t, str_t1,                    # Variables aggregation
                                         columns_2_hold_geopandas_base, str_col_origin, str_col_destination, str_grid_idx,                                                  # Variables needed to be there as various columns for the analysis                 
                                         str_population_col_grid, str_col_comuni_name, str_hotspot_prefix, str_centroid_lat, str_centroid_lon,                              # Variables needed for the hierarchical analysis   
                                         cities_gdf, str_dir_output_date):
    idx_case = 0
    for suffix_in,is_in_flows in case_2_is_in_flow.items():                                                   
        # NOTE: Pick the selected columns for the analysis
        Tij_dist,Tij_dist_baseline = filter_flows_by_conditions_from_cases(Tij_dist_init = Tij_dist_init,
                                                                Tij_dist_baseline_init = Tij_dist_baseline_init,
                                                                case_analysis = case_pipeline,
                                                                is_weekday = is_weekday,
                                                                day_id_of_interest = str_day,
                                                                hour_id_of_interest = int_hour_start_window_interest,
                                                                user_profile = user_profile
                                                                )
        dict_column_flows_aggregation_weekday, dict_column_grid_aggregation_weekday, extension_columns_2_hold, columns_2_hold_geopandas_for_flows_plot, columns_flows_2_be_merged_2_keep, on_colums_flows_2_join, on_columns_grid_2_join = define_columns_to_hold_and_merge_both_for_grid_and_flows_OD_analysis(columns_2_hold_geopandas_base = columns_2_hold_geopandas_base,
                                                                                                                                                                                                                                                                        str_col_origin = str_col_origin,
                                                                                                                                                                                                                                                                        str_col_destination = str_col_destination,
                                                                                                                                                                                                                                                                        str_grid_idx = str_grid_idx,
                                                                                                                                                                                                                                                                        dict_column_flows = dict_column_flows_aggregation_weekday,
                                                                                                                                                                                                                                                                        dict_column_grid = dict_column_grid_aggregation_weekday,
                                                                                                                                                                                                                                                                        str_day = str_day,
                                                                                                                                                                                                                                                                        time_interval = time_interval,
                                                                                                                                                                                                                                                                        user_profile = user_profile,
                                                                                                                                                                                                                                                                        is_weekday = is_weekday,
                                                                                                                                                                                                                                                                        suffix_in = suffix_in,
                                                                                                                                                                                                                                                                        str_t = str_t,
                                                                                                                                                                                                                                                                        str_t1 = str_t1,
                                                                                                                                                                                                                                                                        case_pipeline = case_pipeline)
        

        # NOTE: Extract columns that are for the analysis
        str_col_n_trips, str_col_n_trips_baseline, str_col_difference_baseline, str_col_total_flows_grid = extract_name_columns_for_difference_pipeline(dict_column_flows = dict_column_flows_aggregation_weekday,
                                                                                                                                                        dict_column_grid = dict_column_grid_aggregation_weekday,str_day = str_day,time_interval = time_interval,
                                                                                                                                                        user_profile = user_profile,is_weekday = is_weekday,
                                                                                                                                                        is_in_flows = is_in_flows,suffix_in = suffix_in,case_pipeline = case_pipeline)
        Tij_dist = Tij_dist.with_columns((pl.col("TRIPS")).alias(str_col_n_trips))  # Divide by two the trips since we are considering both nationalities
        Tij_dist_baseline = Tij_dist_baseline.with_columns(pl.col("TRIPS").alias(str_col_n_trips_baseline))                # NOTE: rename the column with the trips to the one needed for the analysis
        print(f"Compare Tij_dist to Tij_dist_baseline: {suffix_in}")
        Tij_dist = compute_difference_trips_col_day_baseline(Tij_dist = Tij_dist,
                                                            Tij_dist_baseline = Tij_dist_baseline,
                                                            str_col_n_trips = str_col_n_trips,
                                                            str_col_n_trips_baseline = str_col_n_trips_baseline,
                                                            str_col_difference_baseline = str_col_difference_baseline,
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
        mh, hotspot_2_origin_idx_2_crit_dest_idx, hotspot_flows, list_indices_all_fluxes_for_colormap = pipeline_mobility_hierarchy_time_day_type_trips(cities_gdf = geojson_input_hierarchy,Tij_dist_fit_gravity = Tij_dist,str_population_col_grid = str_population_col_grid,
                                                                                                                                                        str_col_comuni_name = str_col_comuni_name,str_col_origin = str_col_origin,str_col_destination = str_col_destination,
                                                                                                                                                        str_col_n_trips = str_col_n_trips,
                                                                                                                                                        str_col_total_flows_grid = str_col_total_flows_grid,
                                                                                                                                                        str_hotspot_prefix = str_hotspot_prefix,str_centroid_lat = str_centroid_lat,str_centroid_lon = str_centroid_lon,
                                                                                                                                                        str_grid_idx = str_grid_idx,user_profile = user_profile,str_t = str_t,str_t1 = str_t1,is_in_flows = is_in_flows,                                                                                                  # NOTE: is_in_flows = True means that we are considering the incoming fluxes to the hotspot
                                                                                                                                                        columns_2_hold_geopandas = columns_2_hold_geopandas_for_flows_plot,int_levels = 7)
        
        dict_output_hotspot_analysis_aggregation_weekday = fill_dict_output_hotspot_analysis_OD_analysis_from_case_pipeline(
                                                                                                                            dict_output_hotspot_analysis = dict_output_hotspot_analysis_aggregation_weekday,
                                                                                                                            str_day = str_day,
                                                                                                                            time_interval = time_interval,
                                                                                                                            user_profile = user_profile,
                                                                                                                            is_weekday = is_weekday,
                                                                                                                            is_in_flows = is_in_flows,
                                                                                                                            suffix_in = suffix_in,
                                                                                                                            case_pipeline = case_pipeline,
                                                                                                                            hotspot_2_origin_idx_2_crit_dest_idx = hotspot_2_origin_idx_2_crit_dest_idx,
                                                                                                                            list_indices_all_fluxes_for_colormap = list_indices_all_fluxes_for_colormap,
                                                                                                                            hotspot_flows = hotspot_flows
                                                                                                                            )   
        hotspot_levels = get_values_from_case_pipeline_OD_analysis(dict_column_flows = None,dict_column_grid = None,dict_output_hotspot_analysis = dict_output_hotspot_analysis_aggregation_weekday,str_day = str_day,time_interval = time_interval,user_profile = user_profile,is_weekday = is_weekday,is_in_flows = is_in_flows,suffix_in = suffix_in,name_dict = "dict_output_hotspot_analysis",name_key = "hotspot_levels",case_pipeline = case_pipeline)
        print(f"Map flux generated for {suffix_in} flows")
        # NOTE: Save the maps for incoming fluxes -> NOTE: The str_output_dir_date is unique 
        save_output_mobility_hierarchy_dependent_is_in_fluxes(
                                                            str_dir_output_date = str_dir_output_date,
                                                            map_hierarchy = mh.fmap,
                                                            user_profile = user_profile,
                                                            hotspot_levels = hotspot_levels,
                                                            hotspot_2_origin_idx_2_crit_dest_idx = hotspot_2_origin_idx_2_crit_dest_idx,
                                                            str_t = str_t,
                                                            str_t1 = str_t1,
                                                            is_in_flows = is_in_flows                                                                                                  # NOTE: is_in_flows = True means that we are considering the incoming fluxes to the hotspot
                                                                )                                                                                                             # show the map in the browser
        # Memory management: Clear map_flux after saving
        gc.collect()                                        
        # NOTE: Global save the flows and cities_gdf by merging the str_day, str_t, str_t1, user_profile
        print(f"Case: {suffix_in} - mh.flows: {mh.flows.columns}\nflows merged: {Tij_dist.columns}\nmh.grid: {mh.grid.columns}")
        
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
                                                                                                                                                    message_geojson = f"average {suffix_in} grid",
                                                                                                                                                    message_flows = f"average {suffix_in} flows",
                                                                                                                                                    )     
        grid_global = pl.from_pandas(global_cities_gdf_holding_all_columns_flows.copy().drop("geometry", axis=1))                               
        # Memory management: Clear baseline analysis variables
        gc.collect()
        idx_case += 1
        print(f"Number columns global flows after join: ",len(global_Tij_holding_all_columns_flows.columns),f" cities: ",len(global_cities_gdf_holding_all_columns_flows.columns))
    # NOTE: Visualize All Outputs
    for suffix_in,is_in_flows in case_2_is_in_flow.items():                                                   
        hotspot_2_origin_idx_2_crit_dest_idx, str_col_total_flows_grid, str_col_hotspot_level, str_col_n_trips, str_caption_colormap, str_col_difference = extract_name_columns_for_hierarchical_plot(dict_column_flows = dict_column_flows_aggregation_weekday,dict_column_grid = dict_column_grid_aggregation_weekday,
                                                                                                                                                                                                      dict_output_hotspot_analysis = dict_output_hotspot_analysis_aggregation_weekday,
                                                                                                                                                                                                    str_day = str_day,time_interval = time_interval,user_profile = user_profile,is_weekday = is_weekday,is_in_flows = is_in_flows,
                                                                                                                                                                                                    suffix_in = suffix_in,case_pipeline = case_pipeline)
        
        map_flux = visualize_critical_fluxes_with_lines(grid = global_cities_gdf_holding_all_columns_flows,
                                                        df_flows = global_Tij_holding_all_columns_flows,
                                                        hotspot_2_origin_idx_2_crit_dest_idx = hotspot_2_origin_idx_2_crit_dest_idx,                        # NOTE:
                                                        str_col_total_flows_grid = str_col_total_flows_grid,
                                                        str_col_hotspot = str_col_hotspot_level,
                                                        str_col_n_trips = str_col_n_trips,
                                                        is_in_flows = is_in_flows,
                                                        str_col_origin = str_col_origin,
                                                        str_col_destination = str_col_destination,
                                                        str_centroid_lat = str_centroid_lat,
                                                        str_centroid_lon = str_centroid_lon,
                                                        str_col_comuni_name= str_col_comuni_name,
                                                        str_grid_idx = str_grid_idx,
                                                        str_caption_colormap = str_caption_colormap,
                                                        str_colormap= 'YlOrRd'
                        )
        # NOTE: This gives us the unique path to save the map -> it is in the directory that is created outside
        complete_path_map = os.path.join(str_dir_output_date,f"map_fluxes_{user_profile}_{suffix_in}_{str_day}_{str_t}_{str_t1}_{str_day}.html")                                                # path to the map file
        with open(os.path.join(str_dir_output_date,f"dict_column_flows_aggregation_weekday_{user_profile}_{suffix_in}_t_{str_t}_{str_t1}_d_{str_day}.json"), 'w') as f:
            json.dump(dict_column_flows_aggregation_weekday, f, indent=4)
        with open(os.path.join(str_dir_output_date,f"dict_column_grid_aggregation_weekday_{user_profile}_{suffix_in}_t_{str_t}_{str_t1}_d_{str_day}.json"), 'w') as f:
            json.dump(dict_column_grid_aggregation_weekday, f, indent=4)
        with open(os.path.join(str_dir_output_date,f"dict_output_hotspot_analysis_aggregation_weekday_{user_profile}_{suffix_in}_t_{str_t}_{str_t1}_d_{str_day}.json"), 'w') as f:
            json.dump(dict_output_hotspot_analysis_aggregation_weekday, f, indent=4)
        try:
            map_flux.save(complete_path_map)                                                                                                                         # save the map to the output folder
        except Exception as e:
            print(f"Error saving map_flux: {e}")
    return global_Tij_holding_all_columns_flows, grid_global, global_cities_gdf_holding_all_columns_flows




def main_diffusione_1_2(str_name_project = str_name_project, str_dir_data_path = str_dir_data_path, str_dir_output_path = str_dir_output_path, complete_path_Istat_population = complete_path_Istat_population,
                        str_prefix_complete_path = str_prefix_complete_path, str_start_time_window_interest = str_start_time_window_interest, str_end_time_window_interest = str_end_time_window_interest,
                        int_number_people_per_bus = int_number_people_per_bus, str_name_dataset_gtfs = str_name_dataset_gtfs, str_name_gdf_transport = str_name_gdf_transport,
                        str_name_graph_transport = str_name_graph_transport, str_name_grid = str_name_grid, str_name_grid_2_city = str_name_grid_2_city, str_name_shape_city = str_name_shape_city,
                        str_name_centroid_city = str_name_centroid_city, str_route_idx = str_route_idx, str_trip_idx = str_trip_idx, str_stop_idx = str_stop_idx, str_transport_idx = str_transport_idx,
                        str_grid_idx = str_grid_idx, str_name_stop_2_trip = str_name_stop_2_trip, str_name_stop_2_route = str_name_stop_2_route, str_name_grid_2_stop = str_name_grid_2_stop,
                        str_name_grid_2_route = str_name_grid_2_route, str_name_graph_2_route = str_name_graph_2_route, str_name_route_2_graph = str_name_route_2_graph, str_dir_plots_path = str_dir_plots_path,
                        int_hour_start_window_interest = 7, int_hour_end_window_interest = 8, int_min_aggregation_OD = int_min_aggregation_OD, Lx = Lx, Ly = Ly,
                        col_str_day_od = col_str_day_od, str_period_id_presenze = str_period_id_presenze, col_str_is_week = col_str_is_week,
                        list_time_intervals = list_time_intervals, UserProfiles = UserProfiles, week_days = week_days,
                        conditioning_2_columns_to_hold_when_aggregating = conditioning_2_columns_to_hold_when_aggregating
                        ):
    """
    Main function to perform overtourism analysis using hierarchical classification of flows.
    Steps:
    """
    # NOTE: Activate the project and connect to s3 bucket
    s3, bucket = init_s3()
    # NOTE: Set configuration parameters -> names and so on
    config = set_config(
    str_name_project=str_name_project, str_dir_data_path=str_dir_data_path, str_dir_output_path=str_dir_output_path, complete_path_Istat_population=complete_path_Istat_population, str_prefix_complete_path=str_prefix_complete_path, str_start_time_window_interest=str_start_time_window_interest,
    str_end_time_window_interest=str_end_time_window_interest, int_number_people_per_bus=int_number_people_per_bus, str_name_file_gtfs_zip=str_name_file_gtfs_zip, str_name_dataset_gtfs=str_name_dataset_gtfs, str_name_gdf_transport=str_name_gdf_transport, str_name_graph_transport=str_name_graph_transport,
    str_name_grid=str_name_grid, str_name_grid_2_city=str_name_grid_2_city, str_name_shape_city=str_name_shape_city, str_name_centroid_city=str_name_centroid_city, str_route_idx=str_route_idx, str_trip_idx=str_trip_idx, str_stop_idx=str_stop_idx, str_transport_idx=str_transport_idx,
    str_grid_idx=str_grid_idx, str_name_stop_2_trip=str_name_stop_2_trip, str_name_stop_2_route=str_name_stop_2_route, str_name_grid_2_stop=str_name_grid_2_stop, str_name_grid_2_route=str_name_grid_2_route, str_name_graph_2_route=str_name_graph_2_route, 
    str_name_route_2_graph=str_name_route_2_graph, str_dir_plots_path=str_dir_plots_path, int_hour_start_window_interest=int_hour_start_window_interest, int_hour_end_window_interest=int_hour_end_window_interest, int_min_aggregation_OD=int_min_aggregation_OD, Lx=Lx, Ly=Ly)
    # NOTE: Load GTFS data (bus data) -> by default now it is deactivated since the version for the study of buses is deprecated due to new versioning of the project (CAN BE RESTORED WITHOUT MANY PROBLEMS)
    feed, is_gtfs_available = get_Gtfs_data(config = config, str_prefix_complete_path = str_prefix_complete_path, str_name_dataset_gtfs = str_name_dataset_gtfs)
    # NOTE: Initialize the geodataframe of the cities and the population data from Istat
    cities_gdf, Istat_obj = initialize_geodataframe_polygons(config=config, complete_path_Istat_population = complete_path_Istat_population, str_prefix_complete_path = str_prefix_complete_path, str_name_shape_city = str_name_shape_city, str_name_centroid_city = str_name_centroid_city)
    # NOTE: Initialize distance matrix associated to the polygons of the cities
    df_distance_matrix, config = init_distance_matrix_associated_to_polygons(cities_gdf, config)
    # NOTE: Extract the list of files from the bucket and the available dates
    list_files_od, list_files_presenze, list_str_dates_yyyymm, list_all_avaliable_days_flows = get_informations_about_available_dates_from_files(bucket = bucket, s3 = s3, col_str_day_od = col_str_day_od, str_period_id_presenze = str_period_id_presenze, col_str_is_week = col_str_is_week)
    # NOTE: Initialize the dataframes for the null day analysis
    df_od_null_days, df_presenze_null_days, df_distance_matrix = initialize_df_null_day_dataframe(cities_gdf = cities_gdf, df_distance_matrix = df_distance_matrix, s3 = s3, list_files_presenze = list_files_presenze, list_files_od = list_files_od)
    # NOTE: Save the geodataframe in the output directory and initialize global variables
    columns_2_hold_geopandas_base = [str_area_id_presenze,str_centroid_lat,str_centroid_lon,str_col_comuni_name,str_grid_idx,"geometry"]                        # base columns to hold in the geopandas        
    # NOTE: Initialize the concatenated OD dataframe
    df_od_with_just_in_in_out_in_trips = initialize_concatenated_od_dataframe(list_files_od = list_files_od, s3 = s3, str_period_id_presenze = str_period_id_presenze, col_str_day_od = col_str_day_od, col_str_is_week = col_str_is_week, df_distance_matrix = df_distance_matrix)
    list_unique_days_od = df_od_with_just_in_in_out_in_trips[col_str_day_od].unique().to_list()
    # Example conditioning sets (replace with your real ones)
    conditioned_sets = {
        "day": list_unique_days_od,
        "hour": list_time_intervals,  # your definition of intervals
        "user": UserProfiles,
        "weekday": week_days
    }
    # NOTE: This should be changed to decide the level of aggregation.
    for case_pipeline in conditioning_2_columns_to_hold_when_aggregating.keys():
        # Parse case_pipeline string (e.g., "day_hour_user_weekday")
        pipeline_vars = list(filter(len, case_pipeline.split("_"))) # Remove empty strings
        global_Tij_holding_all_columns_flows, global_cities_gdf_holding_all_columns_flows = save_geodafeame_in_directory_output_and_init_global_geodata_and_global_geo_flows(cities_gdf = cities_gdf, config = config, str_grid_idx=str_grid_idx, columns_2_hold_geopandas_base= columns_2_hold_geopandas_base)
        # Build the cartesian product of the conditioning sets in order
        conditioning_values = [conditioned_sets[var] for var in pipeline_vars]
        if os.path.exists(os.path.join(config[str_dir_output],f"Tij_all_columns_{case_pipeline}.parquet")) and os.path.exists(os.path.join(config[str_dir_output],f"grid_all_columns_{case_pipeline}.parquet")):
            print(f"Skipping case_pipeline {case_pipeline} as output files already exist.")
            continue  # Skip to the next case_pipeline if files already exist
        else:
            for combo in itertools.product(*conditioning_values):
                # unpack according to order
                loop_context = dict(zip(pipeline_vars, combo))
                
                # Extract variables for readability
                str_day = loop_context.get("day", "")
                time_interval = loop_context.get("hour", [0,0])  # default
                user_profile = loop_context.get("user", "")
                is_weekday = loop_context.get("weekday", "all_days")
                str_t = str(time_interval[0])
                str_t1 = str(time_interval[1])
                int_hour_start_window_interest = time_interval[0]  # just to have a variable that is the start of the window interest
                # Build directory path components dynamically in the same order as case_pipeline
                dir_components = [str(loop_context[var]) if var != "hour" else str(int(loop_context[var][0]))+"_"+str(int(loop_context[var][1])) for var in pipeline_vars if var in loop_context]
                # Join them onto the base directory
                str_dir_output_date = os.path.join(config[str_dir_output], *dir_components)

                # Create the directory
                Path(str_dir_output_date).mkdir(parents=True, exist_ok=True)
                print("🔄 Iteration context:", loop_context)

                dict_column_flows_aggregation_weekday, dict_column_grid_aggregation_weekday, dict_output_hotspot_analysis_aggregation_weekday, Tij_dist_init, Tij_dist_baseline_init = level_aggregation_concat_od_dataframe_and_null_days(list_all_avaliable_days_flows = list_all_avaliable_days_flows, list_time_intervals = list_time_intervals,
                                                                                                                                                                                                                                            user_profile= user_profile, UserProfiles = UserProfiles, week_days = week_days, case_2_is_in_flow = case_2_is_in_flow, case_pipeline = case_pipeline,
                                                                                                                                                                                                                                            df_od_with_just_in_in_out_in_trips = df_od_with_just_in_in_out_in_trips, df_od_null_days = df_od_null_days)
                # main_diffusione_1_2_by_case_pipeline
                global_Tij_holding_all_columns_flows, grid_global, global_cities_gdf_holding_all_columns_flows = main_diffusione_1_2_by_case_pipeline(
                                                                                                                                                                                                                                                    global_Tij_holding_all_columns_flows=global_Tij_holding_all_columns_flows,
                                                                                                                                                                                                                                                    global_cities_gdf_holding_all_columns_flows=global_cities_gdf_holding_all_columns_flows,
                                                                                                                                                                                                                                                    dict_column_flows_aggregation_weekday=dict_column_flows_aggregation_weekday,
                                                                                                                                                                                                                                                    dict_column_grid_aggregation_weekday=dict_column_grid_aggregation_weekday,
                                                                                                                                                                                                                                                    dict_output_hotspot_analysis_aggregation_weekday=dict_output_hotspot_analysis_aggregation_weekday,
                                                                                                                                                                                                                                                    Tij_dist_init=Tij_dist_init,
                                                                                                                                                                                                                                                    Tij_dist_baseline_init=Tij_dist_baseline_init,
                                                                                                                                                                                                                                                    case_2_is_in_flow=case_2_is_in_flow,
                                                                                                                                                                                                                                                    case_pipeline=case_pipeline,
                                                                                                                                                                                                                                                    user_profile=user_profile,
                                                                                                                                                                                                                                                    is_weekday=is_weekday,
                                                                                                                                                                                                                                                    str_day=str_day,
                                                                                                                                                                                                                                                    int_hour_start_window_interest=int_hour_start_window_interest,
                                                                                                                                                                                                                                                    time_interval=time_interval,
                                                                                                                                                                                                                                                    str_t=str_t,
                                                                                                                                                                                                                                                    str_t1=str_t1,
                                                                                                                                                                                                                                                    columns_2_hold_geopandas_base=columns_2_hold_geopandas_base,
                                                                                                                                                                                                                                                    str_col_origin=str_col_origin,
                                                                                                                                                                                                                                                    str_col_destination=str_col_destination,
                                                                                                                                                                                                                                                    str_grid_idx=str_grid_idx,
                                                                                                                                                                                                                                                    str_population_col_grid=str_population_col_grid,
                                                                                                                                                                                                                                                    str_col_comuni_name=str_col_comuni_name,
                                                                                                                                                                                                                                                    str_hotspot_prefix=str_hotspot_prefix,
                                                                                                                                                                                                                                                    str_centroid_lat=str_centroid_lat,
                                                                                                                                                                                                                                                    str_centroid_lon=str_centroid_lon,
                                                                                                                                                                                                                                                    cities_gdf=cities_gdf,
                                                                                                                                                                                                                                                    str_dir_output_date=str_dir_output_date
                                                                                                                                                                                                                                                )
            global_Tij_holding_all_columns_flows.write_parquet(os.path.join(config[str_dir_output],f"Tij_all_columns_{case_pipeline}.parquet"))                                      # save the global flows
            grid_global.write_parquet(os.path.join(config[str_dir_output],f"grid_all_columns_{case_pipeline}.parquet"))  # save the global grid


if __name__ == "__main__":
    main_diffusione_1_2()