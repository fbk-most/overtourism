"""
    Description:
        This module allows to choose apply differentiated aggregations to the flow dataframe T_ij_dist depending on the case analysis.
    1) prepare_flow_dataframe_for_hierarchical_prcedure: function that applies the differentiated aggregations to the flow dataframe T_ij_dist depending on the case analysis.
    The cases are:
        - day_hour_user_weekday: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
        - hour_user_weekday: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
        - user_weekday: T_{origin}_{destination}_{user_profile}_{is_weekday}
        - user: T_{origin}_{destination}_{user_profile}
        - hour_weekday: T_{origin}_{destination}_{hour}_{is_weekday}
        - hour: T_{origin}_{destination}_{hour}
        - weekday: T_{origin}_{destination}_{is_weekday}
        - day_hour_weekday: T_{origin}_{destination}_{hour}_{is_weekday}
    The function gets in input AGGREGATED of user profile (that can be either "" or the classes that Vodafone provides) and the case analysis.
    If it is AGGREGATED then the function applies first the aggregation over user profile and then the aggregation over the case analysis.
    2) filter_flows_by_conditions: function that filters the flow dataframe T_ij_dist by applying the filters in input.

"""
from data_preparation.diffusion.constant_names_variables import UserProfile2IndexVodafone
from data_preparation.diffusion.constant_names_variables import *
from data_preparation.diffusion.default_parameters import *
import polars as pl
from data_preparation.diffusion.OD import *
from data_preparation.diffusion.OD_pipeline import *
from data_preparation.diffusion.set_config import *
from data_preparation.diffusion.VodafoneData import *





### DEFAULT INITIAL CONFIGURATION FLOW DATAFRAME ###
def default_initial_preparation_common_to_all_cases_df_flows_not_baseline(df_od: pl.DataFrame,
                                                                          df_distance_matrix: pl.DataFrame,
                                                                          str_origin_od: str,
                                                                          str_destination_od: str,
                                                                          str_area_code_origin_col: str,
                                                                          str_area_code_destination_col: str,
                                                                          str_trip_type_od: str,
                                                                          str_col_trip: str = "TRIPS") -> pl.DataFrame:
    """
    Prepare the initial flow dataframe by joining with the distance matrix and filtering trips.
    Args:
        df_od (pl.DataFrame): The input flow dataframe containing trip data.
        df_distance_matrix (pl.DataFrame): The distance matrix dataframe for joining.
        str_origin_od (str): The column name for the origin area in df_od.
        str_destination_od (str): The column name for the destination area in df_od.
        str_area_code_origin_col (str): The column name for the origin area code in df_distance_matrix.
        str_area_code_destination_col (str): The column name for the destination area code in df_distance_matrix.
        str_trip_type_od (str): The column name indicating the type of trip in df_od.
        str_col_trip (str): The column name for the trip counts in df_od. Default is "TRIPS".
    Returns:    
        pl.DataFrame: The prepared flow dataframe with joined distance and filtered trips.
    """
    df_od = join_Tij_Vodafone_with_distance_matrix(df_od = df_od,
                                                    df_distance_matrix = df_distance_matrix,
                                                    str_origin_od = str_origin_od,                                   # NOTE: origin area (ITA.<code>)
                                                    str_destination_od = str_destination_od,                              # NOTE: destination area (ITA.<code>)    
                                                    str_area_code_origin_col = str_area_code_origin_col,
                                                    str_area_code_destination_col = str_area_code_destination_col)


    # NOTE: Initialize the dataframe flows to the form where the trips are the sum over all observations ut still are conditioned to the day, hour, user profile and weekday/weekend
    df_od_with_just_in_in_out_in_trips = pipeline_initial_df_flows_aggregation_on_dat_hour_user_weekday(df = df_od,
                                                                            tuple_filters = (pl.col(str_trip_type_od) != "out-out",
                                                                                                pl.col(str_trip_type_od) != "in-out"),
                                                                            message_filters = (f"{str_trip_type_od} != out-out",
                                                                                                f"{str_trip_type_od} != in-out"),
                                                                            list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["day_hour_user_weekday"],            # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{str_day}_{is_weekday}
                                                                            str_col_trips_to_be_aggregated = str_col_trip,
                                                                            str_col_name_aggregated = str_col_trip,
                                                                            method_aggregation="sum"
                                                                                )
    return df_od_with_just_in_in_out_in_trips







def prepare_flow_dataframe_for_hierarchical_prcedure(df_od_with_just_in_in_out_in_trips: pl.DataFrame,
                                                     Tij_dist_baseline_init: pl.DataFrame,
                                                    case:str,
                                                    user_profile: str) -> (pl.DataFrame, pl.DataFrame):
    """
    Prepare the flow dataframe T_ij_dist for hierarchical procedure by applying differentiated aggregations based on the case analysis starting df_od_with_just_in_in_out_in_trips that contains all informations about Vodafone dataset.
    Args:
        df_od_with_just_in_in_out_in_trips (pl.DataFrame): The input flow dataframe containing trip data.
        Tij_dist_baseline_init (pl.DataFrame): The baseline flow dataframe for comparison.
        case (str): The case analysis type, which determines the aggregation method.
                    Possible values include day_hour_user_weekday, hour_user_weekday, user_weekday, user, hour_weekday, hour, weekday, day_hour_weekday.
    Returns:
        pl.DataFrame: The aggregated flow dataframe ready for hierarchical analysis.
    """
    # NOTE: Here I am giving a specific dataframe -> the one that is coming from the VodaFone dataset with filters just in TYPE_TRIP == in-in or out-in
    if case not in conditioning_2_columns_to_hold_when_aggregating:
        raise ValueError(f"Unknown case aggregation: {case}")
    columns_that_must_be_present_in_dataframes = conditioning_2_columns_to_hold_when_aggregating[case]
    for col in columns_that_must_be_present_in_dataframes:
        if col not in df_od_with_just_in_in_out_in_trips.columns:
            raise ValueError(f"Column {col} not present in df_od_with_just_in_in_out_in_trips")
        if col not in Tij_dist_baseline_init.columns:
            raise ValueError(f"Column {col} not present in Tij_dist_baseline_init")
    
    # NOTE: Aggregate by average over days is Default -> this level of resolution is the most grain that we allow.  
    Tij_dist_init = aggregate_flows(df = df_od_with_just_in_in_out_in_trips,
                            list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["day_hour_user_weekday"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                            str_col_trips_to_be_aggregated = "TRIPS",
                            str_col_name_aggregated = "TRIPS",
                            method_aggregation="sum")

    Tij_dist_baseline_init = aggregate_flows(df = Tij_dist_baseline_init,
                            list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating_baseline["day_hour_user_weekday"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                            str_col_trips_to_be_aggregated = "TRIPS",
                            str_col_name_aggregated = "TRIPS",
                            method_aggregation="sum")

    if case == "day_hour_user_weekday":
        return Tij_dist_init, Tij_dist_baseline_init
    elif case == "day_hour_weekday":
        # NOTE: Aggregate by average over days  
        Tij_dist_init = aggregate_flows(df = Tij_dist_init,
                                list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["day_hour_weekday"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                                str_col_trips_to_be_aggregated = "TRIPS",
                                str_col_name_aggregated = "TRIPS",
                                method_aggregation="average")

        Tij_dist_baseline_init = aggregate_flows(df = Tij_dist_baseline_init,
                                list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating_baseline["day_hour_weekday"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                                str_col_trips_to_be_aggregated = "TRIPS",
                                str_col_name_aggregated = "TRIPS",
                                method_aggregation="average")
        return Tij_dist_init, Tij_dist_baseline_init
    elif case == "hour_user_weekday":
        # NOTE: Aggregate by average over days  
        Tij_dist_init = aggregate_flows(df = Tij_dist_init,
                                list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["hour_user_weekday"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                                str_col_trips_to_be_aggregated = "TRIPS",
                                str_col_name_aggregated = "TRIPS",
                                method_aggregation="average")

        Tij_dist_baseline_init = aggregate_flows(df = Tij_dist_baseline_init,
                                list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["hour_user_weekday"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                                str_col_trips_to_be_aggregated = "TRIPS",
                                str_col_name_aggregated = "TRIPS",
                                method_aggregation="average")
        return Tij_dist_init, Tij_dist_baseline_init
    elif case == "user_weekday":
        # NOTE: Aggregate by average over days and hours  
        Tij_dist_init = aggregate_flows(df = Tij_dist_init,
                                list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["user_weekday"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                                str_col_trips_to_be_aggregated = "TRIPS",
                                str_col_name_aggregated = "TRIPS",
                                method_aggregation="average")

        Tij_dist_baseline_init = aggregate_flows(df = Tij_dist_baseline_init,
                                list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["user_weekday"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                                str_col_trips_to_be_aggregated = "TRIPS",
                                str_col_name_aggregated = "TRIPS",
                                method_aggregation="average")
        return Tij_dist_init, Tij_dist_baseline_init
    elif case == "user":
        # NOTE: Aggregate by average over days and hours  
        Tij_dist_init = aggregate_flows(df = Tij_dist_init,
                                list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["user"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                                str_col_trips_to_be_aggregated = "TRIPS",
                                str_col_name_aggregated = "TRIPS",
                                method_aggregation="average")

        Tij_dist_baseline_init = aggregate_flows(df = Tij_dist_baseline_init,
                                list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["user"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                                str_col_trips_to_be_aggregated = "TRIPS",
                                str_col_name_aggregated = "TRIPS",
                                method_aggregation="average")
        return Tij_dist_init, Tij_dist_baseline_init
    elif case == "hour_weekday":
        # NOTE: Aggregate by average over days and user profile  
        Tij_dist_init = aggregate_flows(df = Tij_dist_init,
                                list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["hour_weekday"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                                str_col_trips_to_be_aggregated = "TRIPS",
                                str_col_name_aggregated = "TRIPS",
                                method_aggregation="average")

        Tij_dist_baseline_init = aggregate_flows(df = Tij_dist_baseline_init,
                                list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating_baseline["hour_weekday"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                                str_col_trips_to_be_aggregated = "TRIPS",
                                str_col_name_aggregated = "TRIPS",
                                method_aggregation="average")
        return Tij_dist_init, Tij_dist_baseline_init
    elif case == "hour":
        # NOTE: Aggregate by average over days and user profile  
        Tij_dist_init = aggregate_flows(df = Tij_dist_init,
                                list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["hour"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                                str_col_trips_to_be_aggregated = "TRIPS",
                                str_col_name_aggregated = "TRIPS",
                                method_aggregation="average")

        Tij_dist_baseline_init = aggregate_flows(df = Tij_dist_baseline_init,
                                list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating_baseline["hour"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                                str_col_trips_to_be_aggregated = "TRIPS",
                                str_col_name_aggregated = "TRIPS",
                                method_aggregation="average")
        return Tij_dist_init, Tij_dist_baseline_init
    elif case == "weekday":
        # NOTE: Aggregate by average over days  
        Tij_dist_init = aggregate_flows(df = Tij_dist_init,
                                list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating["weekday"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                                str_col_trips_to_be_aggregated = "TRIPS",
                                str_col_name_aggregated = "TRIPS",
                                method_aggregation="average")

        Tij_dist_baseline_init = aggregate_flows(df = Tij_dist_baseline_init,
                                list_columns_groupby = conditioning_2_columns_to_hold_when_aggregating_baseline["weekday"],                       # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
                                str_col_trips_to_be_aggregated = "TRIPS",
                                str_col_name_aggregated = "TRIPS",
                                method_aggregation="average")
        return Tij_dist_init,Tij_dist_baseline_init
    elif case == "_":
        Tij_dist_init = aggregate_flows(
            df=Tij_dist_init,
            list_columns_groupby=conditioning_2_columns_to_hold_when_aggregating[
                "day_hour_weekday"
            ],  # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
            str_col_trips_to_be_aggregated="TRIPS",
            str_col_name_aggregated="TRIPS",
            method_aggregation="sum",
        )
        Tij_dist_baseline_init = aggregate_flows(
            df=Tij_dist_baseline_init,
            list_columns_groupby=conditioning_2_columns_to_hold_when_aggregating_baseline[
                "hour_weekday"
            ],  # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
            str_col_trips_to_be_aggregated="TRIPS",
            str_col_name_aggregated="TRIPS",
            method_aggregation="sum",
        )
        Tij_dist_init = aggregate_flows(
            df=Tij_dist_init,
            list_columns_groupby=conditioning_2_columns_to_hold_when_aggregating["_"],  # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
            str_col_trips_to_be_aggregated="TRIPS",
            str_col_name_aggregated="TRIPS",
            method_aggregation="average",
        )

        Tij_dist_baseline_init = aggregate_flows(
            df=Tij_dist_baseline_init,
            list_columns_groupby=conditioning_2_columns_to_hold_when_aggregating_baseline["_"],  # NOTE: T_{origin}_{destination}_{hour}_{user_profile}_{is_weekday}
            str_col_trips_to_be_aggregated="TRIPS",
            str_col_name_aggregated="TRIPS",
            method_aggregation="average",
        )
        return Tij_dist_init, Tij_dist_baseline_init
    else:
        raise ValueError(f"Unknown case aggregation: {case}")
    
def compute_filters_and_messages_for_case_analysis(day_id_of_interest: int,
                                                  hour_id_of_interest: int,
                                                  user_profile: str,
                                                  is_weekday: bool):

    try:
        int_user_profile = UserProfile2IndexVodafone[user_profile]
    except:
        int_user_profile = -1
        pass

    dict_case_2_tuple_filters = {
        "day_hour_user_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(col_str_day_od) == day_id_of_interest,
            pl.col(str_departure_hour_od) == hour_id_of_interest,
            pl.col(str_origin_visitor_class_id_od) == int_user_profile
        ),
        "day_hour_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(col_str_day_od) == day_id_of_interest,
            pl.col(str_departure_hour_od) == hour_id_of_interest
        ),
        "hour_user_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(str_departure_hour_od) == hour_id_of_interest,
            pl.col(str_origin_visitor_class_id_od) == int_user_profile
        ),
        "user_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(str_origin_visitor_class_id_od) == int_user_profile
        ),
        "user": (
            pl.col(str_origin_visitor_class_id_od) == int_user_profile,
        ),
        "hour_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(str_departure_hour_od) == hour_id_of_interest
        ),
        "hour": (
            pl.col(str_departure_hour_od) == hour_id_of_interest,
        ),
        "weekday": (
            pl.col(col_str_is_week) == is_weekday,
        ),
        "_": (
        ),
    }

    dict_case_2_filters_baseline = {
        "day_hour_user_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(str_departure_hour_od) == hour_id_of_interest,
            pl.col(str_origin_visitor_class_id_od) == int_user_profile
        ),
        "day_hour_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(str_departure_hour_od) == hour_id_of_interest
        ),
        "hour_user_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(str_departure_hour_od) == hour_id_of_interest,
            pl.col(str_origin_visitor_class_id_od) == int_user_profile
        ),
        "user_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(str_origin_visitor_class_id_od) == int_user_profile
        ),
        "user": (
            pl.col(str_origin_visitor_class_id_od) == int_user_profile,
        ),
        "hour_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(str_departure_hour_od) == hour_id_of_interest
        ),
        "hour": (
            pl.col(str_departure_hour_od) == hour_id_of_interest,
        ),
        "weekday": (
            pl.col(col_str_is_week) == is_weekday,
        ),
        "_": (
        ),
    }

    dict_case_message = {
        "day_hour_user_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{col_str_day_od} == {day_id_of_interest}",
            f"{str_departure_hour_od} == {hour_id_of_interest}",
            f"{str_origin_visitor_class_id_od} == {user_profile}"
        ),
        "day_hour_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{col_str_day_od} == {day_id_of_interest}",
            f"{str_departure_hour_od} == {hour_id_of_interest}"
        ),
        "hour_user_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{str_departure_hour_od} == {hour_id_of_interest}",
            f"{str_origin_visitor_class_id_od} == {user_profile}"
        ),
        "user_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{str_origin_visitor_class_id_od} == {user_profile}"
        ),
        "user": (
            f"{str_origin_visitor_class_id_od} == {user_profile}",
        ),
        "hour_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{str_departure_hour_od} == {hour_id_of_interest}"
        ),
        "hour": (
            f"{str_departure_hour_od} == {hour_id_of_interest}",
        ),
        "weekday": (
            f"{col_str_is_week} == {is_weekday}",
        ),
        "_": (
        ),
    }

    dict_case_message_baseline = {
        "day_hour_user_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{str_departure_hour_od} == {hour_id_of_interest}",
            f"{str_origin_visitor_class_id_od} == {user_profile}"
        ),
        "day_hour_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{str_departure_hour_od} == {hour_id_of_interest}"
        ),
        "hour_user_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{str_departure_hour_od} == {hour_id_of_interest}",
            f"{str_origin_visitor_class_id_od} == {user_profile}"
        ),
        "user_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{str_origin_visitor_class_id_od} == {user_profile}"
        ),
        "user": (
            f"{str_origin_visitor_class_id_od} == {user_profile}",
        ),
        "hour_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{str_departure_hour_od} == {hour_id_of_interest}"
        ),
        "hour": (
            f"{str_departure_hour_od} == {hour_id_of_interest}",
        ),
        "weekday": (
            f"{col_str_is_week} == {is_weekday}",
        ),
        "_": (
        ),
    }

    return dict_case_2_tuple_filters, dict_case_2_filters_baseline, dict_case_message, dict_case_message_baseline


def filter_flows_by_conditions_from_cases(
        Tij_dist_init: pl.DataFrame,
        Tij_dist_baseline_init: pl.DataFrame,
        case_analysis: str,
        is_weekday: bool,
        day_id_of_interest: int,
        hour_id_of_interest: int,
        user_profile: str
    ) -> tuple[pl.DataFrame, pl.DataFrame]:
    """
    Filter the flow dataframe T_ij_dist based on specified conditions for case analysis.
    """    
    dict_case_2_tuple_filters, dict_case_2_filters_baseline, dict_case_message, dict_case_message_baseline = compute_filters_and_messages_for_case_analysis(
        day_id_of_interest=day_id_of_interest,
        hour_id_of_interest=hour_id_of_interest,
        user_profile=user_profile,
        is_weekday=is_weekday
    )        

    filters_flows = dict_case_2_tuple_filters[case_analysis]      
    filters_flows_baseline = dict_case_2_filters_baseline[case_analysis]
    message_filters = dict_case_message[case_analysis]
    message_filters_baseline = dict_case_message_baseline[case_analysis]
    print(f"Filters to be applied to the flow dataframe for case {case_analysis}: {message_filters}")
    print(f"Filters to be applied to the baseline flow dataframe for case {case_analysis}: {message_filters_baseline}")
    # ✅ Use the helper instead of recursively calling this function
    Tij_dist = filter_flows_by_conditions(
        df=Tij_dist_init,
        tuple_filters=filters_flows,
        message=message_filters
    )

    Tij_dist_baseline = filter_flows_by_conditions(
        df=Tij_dist_baseline_init,
        tuple_filters=filters_flows_baseline,
        message=message_filters_baseline
    )

    return Tij_dist, Tij_dist_baseline


def define_columns_to_hold_and_merge_both_for_grid_and_flows_OD_analysis(columns_2_hold_geopandas_base: list,
                                                                        str_col_origin: str,
                                                                        str_col_destination: str,
                                                                        str_grid_idx: str,
                                                                        dict_column_flows: dict,
                                                                        dict_column_grid: dict,
                                                                        str_day: int,
                                                                        time_interval: list,
                                                                        user_profile: str,
                                                                        is_weekday: bool,
                                                                        suffix_in: str,
                                                                        str_t: str,
                                                                        str_t1: str,
                                                                        case_pipeline: str):
    """
    Define columns to hold and merge for both grid and flows in OD analysis.
    """ 
    
    dict_column_flows = set_dict_column_names_flows_OD_analysis(dict_column_flows = dict_column_flows,
                                                                str_day = str_day,
                                                                time_interval = time_interval,
                                                                user_profile = user_profile,
                                                                is_weekday = is_weekday,
                                                                suffix_in = suffix_in,
                                                                str_t = str_t,
                                                                str_t1 = str_t1,
                                                                case_pipeline =case_pipeline)
#    print(f"Columns for the flow dataframe in the OD analysis: {dict_column_flows}")
    # NOTE: Initialize the names of the columns that will be used in the analysis for the grid
    dict_column_grid = set_dict_column_names_grid_OD_analysis(dict_column_grid = dict_column_grid,
                                                              str_day = str_day,
                                                              time_interval = time_interval,
                                                              user_profile = user_profile,
                                                              is_weekday = is_weekday,
                                                              suffix_in = suffix_in,
                                                              str_t = str_t,
                                                              str_t1 = str_t1,
                                                              case_pipeline =case_pipeline)
#    print(f"Columns for the flow dataframe in the OD analysis: {dict_column_flows}")
    # NOTE: Set the extension columns to hold for the grid analysis
    extension_columns_2_hold = set_columns_to_hold_for_OD_analysis(dict_column_grid = dict_column_grid,
                                                                   str_day = str_day,
                                                                   time_interval = time_interval,
                                                                   user_profile = user_profile,
                                                                   is_weekday = is_weekday,
                                                                   suffix_in = suffix_in,
                                                                   case_pipeline =case_pipeline)
    print(f"Extension columns to hold for the grid analysis: {extension_columns_2_hold}")
    columns_2_hold_geopandas_for_flows_plot, columns_flows_2_be_merged_2_keep, on_colums_flows_2_join, on_columns_grid_2_join = define_columns_to_hold_OD_analysis(columns_2_hold_geopandas_base,
                                                                                                                                                                    extension_columns_2_hold,
                                                                                                                                                                    str_col_origin,
                                                                                                                                                                    str_col_destination,
                                                                                                                                                                    str_grid_idx,        
                                                                                                                                                                    dict_column_flows,
                                                                                                                                                                    str_day,
                                                                                                                                                                    time_interval,
                                                                                                                                                                    user_profile,
                                                                                                                                                                    is_weekday,
                                                                                                                                                                    suffix_in,
                                                                                                                                                                    case_pipeline)    
    
    return dict_column_flows, dict_column_grid, extension_columns_2_hold, columns_2_hold_geopandas_for_flows_plot, columns_flows_2_be_merged_2_keep, on_colums_flows_2_join, on_columns_grid_2_join
