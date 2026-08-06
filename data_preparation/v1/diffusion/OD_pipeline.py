from data_preparation.diffusion.OD import *
from data_preparation.diffusion.constant_names_variables import *
from data_preparation.diffusion.dictionary_handles import _nested_get, _nested_set    
import polars as pl
from typing import Any, Dict, List, Tuple




# ================================================================
# Helper: unified schema (list of nesting keys) for each pipeline
# ================================================================

def _get_case_schema(str_day: str,
                     time_interval: list,
                     user_profile: str,
                     is_weekday: bool,
                     suffix_in: str) -> Dict[str, List[Any]]:
    """
    Returns a mapping: case_pipeline -> list of nested keys (in order).
    Use 'suffix_in' as the canonical flow-type key (this corresponds to the
    values of your case_2_is_in_flow dict).
    """
    return {
        # schema: [str_day?, time_interval[0]?, user_profile?, is_weekday?, suffix_in?]
        "day_hour_user_weekday": [str_day, time_interval[0], user_profile, is_weekday, suffix_in],
        "hour_user_weekday":     [time_interval[0], user_profile, is_weekday, suffix_in],
        "user_weekday":          [user_profile, is_weekday, suffix_in],
        "user":                  [user_profile, suffix_in],
        "hour_weekday":          [time_interval[0], is_weekday, suffix_in],
        "hour":                  [time_interval[0], suffix_in],
        "weekday":               [is_weekday, suffix_in],
        "_":                     [suffix_in],
        "day_hour_weekday":      [str_day, time_interval[0], is_weekday, suffix_in],
    }


# ================================================================
# Function: initialize dictionaries (keeps original signature)
# returns: dict_column_flows, dict_column_grid, dict_output_hotspot_analysis
# ================================================================
def initialize_dicts_that_hold_grid_flows_columns_and_hotspot_analysis(list_all_avaliable_days_flows: list, 
                                                                       list_time_intervals: list,
                                                                       UserProfiles: list,
                                                                       week_days: list,
                                                                       case_2_is_in_flow: dict,
                                                                       case_pipeline: str):
    """
    Initialize the dictionaries that will hold the names of the columns for the flows, grid and hotspot analysis
    for the post-processing and visualization.

    IMPORTANT:
    - This function uses a single nested key schema for each case_pipeline (see _get_case_schema).
    - If you add/remove cases in conditioning_2_columns..., update both this function
      and get_values_from_case_pipeline_OD_analysis accordingly.
    """

    print(f"[INIT] Case pipeline = {case_pipeline}")
    # For all initializations we will build nested dicts according to the schema
    dict_column_flows = {}
    dict_column_grid = {}
    dict_output_hotspot_analysis = {}

    # helper to fill "leaf" nested structures for the three dict types
    def _init_leaves_for_keys(keys: List[Any]):
        # flows leaf keys
        _nested_set(dict_column_flows, keys, "str_col_n_trips", "")
        _nested_set(dict_column_flows, keys, "str_col_n_trips_baseline", "")
        _nested_set(dict_column_flows, keys, "str_caption_colormap_flows", "")
        _nested_set(dict_column_flows, keys, "str_col_difference_baseline", "")

        # grid leaf keys
        _nested_set(dict_column_grid, keys, "str_col_hotspot", "")
        _nested_set(dict_column_grid, keys, "str_col_total_flows_grid_hierachical_routine", "")

        # hotspot analysis leaf keys
        _nested_set(dict_output_hotspot_analysis, keys, "hotspot_2_origin_idx_2_crit_dest_idx", "")
        _nested_set(dict_output_hotspot_analysis, keys, "list_indices_all_fluxes_for_colormap", "")
        _nested_set(dict_output_hotspot_analysis, keys, "hotspot_levels", {})

    # We'll iterate and initialize only the keys relevant to the requested case_pipeline
    # Use schema generator with example placeholders - we must iterate over actual values:
    if case_pipeline == "day_hour_user_weekday":
        print("[INIT] building day_hour_user_weekday structure...")
        for str_day in list_all_avaliable_days_flows:
            for time_interval in list_time_intervals:
                for user_profile in UserProfiles:
                    for is_weekday in week_days:
                        for suffix_in in case_2_is_in_flow.keys():
                            keys = _get_case_schema(str_day, time_interval, user_profile, is_weekday, suffix_in)["day_hour_user_weekday"]
                            _init_leaves_for_keys(keys)
        return dict_column_flows, dict_column_grid, dict_output_hotspot_analysis

    elif case_pipeline == "hour_user_weekday":
        print("[INIT] building hour_user_weekday structure...")
        for time_interval in list_time_intervals:
            for user_profile in UserProfiles:
                for is_weekday in week_days:
                    for suffix_in in case_2_is_in_flow.keys():
                        keys = _get_case_schema("", time_interval, user_profile, is_weekday, suffix_in)["hour_user_weekday"]
                        _init_leaves_for_keys(keys)
        return dict_column_flows, dict_column_grid, dict_output_hotspot_analysis

    elif case_pipeline == "user_weekday":
        print("[INIT] building user_weekday structure...")
        for user_profile in UserProfiles:
            for is_weekday in week_days:
                for suffix_in in case_2_is_in_flow.keys():
                    keys = _get_case_schema("", [None], user_profile, is_weekday, suffix_in)["user_weekday"]
                    _init_leaves_for_keys(keys)
        return dict_column_flows, dict_column_grid, dict_output_hotspot_analysis

    elif case_pipeline == "user":
        print("[INIT] building user structure...")
        for user_profile in UserProfiles:
            for suffix_in in case_2_is_in_flow.keys():
                keys = _get_case_schema("", [None], user_profile, False, suffix_in)["user"]
                _init_leaves_for_keys(keys)
        return dict_column_flows, dict_column_grid, dict_output_hotspot_analysis

    elif case_pipeline == "hour_weekday":
        print("[INIT] building hour_weekday structure...")
        for time_interval in list_time_intervals:
            for is_weekday in week_days:
                for suffix_in in case_2_is_in_flow.keys():
                    keys = _get_case_schema("", time_interval, "", is_weekday, suffix_in)["hour_weekday"]
                    _init_leaves_for_keys(keys)
        return dict_column_flows, dict_column_grid, dict_output_hotspot_analysis

    elif case_pipeline == "hour":
        print("[INIT] building hour structure...")
        for time_interval in list_time_intervals:
            for suffix_in in case_2_is_in_flow.keys():
                keys = _get_case_schema("", time_interval, "", False, suffix_in)["hour"]
                _init_leaves_for_keys(keys)
        return dict_column_flows, dict_column_grid, dict_output_hotspot_analysis

    elif case_pipeline == "weekday":
        print("[INIT] building weekday structure...")
        for is_weekday in week_days:
            for suffix_in in case_2_is_in_flow.keys():
                keys = _get_case_schema("", [None], "", is_weekday, suffix_in)["weekday"]
                _init_leaves_for_keys(keys)
        return dict_column_flows, dict_column_grid, dict_output_hotspot_analysis

    elif case_pipeline == "_":
        print("[INIT] building aggregated structure...")
        for suffix_in in case_2_is_in_flow.keys():
            keys = _get_case_schema("", [None], "", False, suffix_in)["_"]
            _init_leaves_for_keys(keys)
        return dict_column_flows, dict_column_grid, dict_output_hotspot_analysis

    elif case_pipeline == "day_hour_weekday":
        print("[INIT] building day_hour_weekday structure...")
        for str_day in list_all_avaliable_days_flows:
            for time_interval in list_time_intervals:
                for is_weekday in week_days:
                    for suffix_in in case_2_is_in_flow.keys():
                        keys = _get_case_schema(str_day, time_interval, "", is_weekday, suffix_in)["day_hour_weekday"]
                        _init_leaves_for_keys(keys)
        return dict_column_flows, dict_column_grid, dict_output_hotspot_analysis

    else:
        raise ValueError(f"case_pipeline {case_pipeline} not recognized. "
                         f"Choose between {list(conditioning_2_columns_to_hold_when_aggregating.keys())}")

# ================================================================
# Function: compute filters and messages (keeps signature + returns)
# ================================================================
def compute_filters_and_messages_for_case_analysis(day_id_of_interest: str,
                                                  hour_id_of_interest: int,
                                                  user_profile: str,
                                                  is_weekday: bool):
    """
    Compute filters and messages for case analysis based on day, hour, user profile, and weekday/weekend status.

    Returns:
        dict_case_2_tuple_filters,
        dict_case_2_filters_baseline,
        dict_case_message,
        dict_case_message_baseline
    """
    try:
        print("[FILTERS] Building filters/messages with inputs:",
            f"day={day_id_of_interest}, hour={hour_id_of_interest}, user={user_profile}, is_weekday={is_weekday}, int_user_profile={UserProfile2IndexVodafone.get(user_profile, 'N/A')}")
        int_user_profile = UserProfile2IndexVodafone[user_profile]
    except:
        int_user_profile = -1
        print("We are computing the filters and messages in a case where we do not need info about users. That is not logically clean, but no big overhead in space and time, so no effort to fix it.")
        pass

    dict_case_2_tuple_filters = {
        "day_hour_user_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(col_str_day_od) == day_id_of_interest,
            pl.col(str_departure_hour_od) == hour_id_of_interest,
            pl.col(str_origin_visitor_class_id_od) == int_user_profile,
        ),
        "hour_user_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(str_departure_hour_od) == hour_id_of_interest,
            pl.col(str_origin_visitor_class_id_od) == int_user_profile,
        ),
        "user_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(str_origin_visitor_class_id_od) == int_user_profile,
        ),
        "user": (
            pl.col(str_origin_visitor_class_id_od) == int_user_profile,
        ),
        "hour_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(str_departure_hour_od) == hour_id_of_interest,
        ),
        "hour": (
            pl.col(str_departure_hour_od) == hour_id_of_interest,
        ),
        "weekday": (
            pl.col(col_str_is_week) == is_weekday,
        ),
        "day_hour_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(col_str_day_od) == day_id_of_interest,
            pl.col(str_departure_hour_od) == hour_id_of_interest,
        ),
        "_": (),
    }

    dict_case_2_filters_baseline = {
        # baseline conditions should match messages length (keeps same keys as above)
        "day_hour_user_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(col_str_day_od) == day_id_of_interest,
            pl.col(str_departure_hour_od) == hour_id_of_interest,
            pl.col(str_origin_visitor_class_id_od) == int_user_profile,
        ),
        "hour_user_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(str_departure_hour_od) == hour_id_of_interest,
            pl.col(str_origin_visitor_class_id_od) == int_user_profile,
        ),
        "user_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(str_origin_visitor_class_id_od) == int_user_profile,
        ),
        "user": (
            pl.col(str_origin_visitor_class_id_od) == int_user_profile,
        ),
        "hour_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(str_departure_hour_od) == hour_id_of_interest,
        ),
        "hour": (
            pl.col(str_departure_hour_od) == hour_id_of_interest,
        ),
        "weekday": (
            pl.col(col_str_is_week) == is_weekday,
        ),
        "day_hour_weekday": (
            pl.col(col_str_is_week) == is_weekday,
            pl.col(col_str_day_od) == day_id_of_interest,
            pl.col(str_departure_hour_od) == hour_id_of_interest,
        ),
        "_": (),
    }

    dict_case_message = {
        "day_hour_user_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{col_str_day_od} == {day_id_of_interest}",
            f"{str_departure_hour_od} == {hour_id_of_interest}",
            f"{str_origin_visitor_class_id_od} == {user_profile}",
        ),
        "hour_user_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{str_departure_hour_od} == {hour_id_of_interest}",
            f"{str_origin_visitor_class_id_od} == {user_profile}",
        ),
        "user_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{str_origin_visitor_class_id_od} == {user_profile}",
        ),
        "user": (
            f"{str_origin_visitor_class_id_od} == {user_profile}",
        ),
        "hour_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{str_departure_hour_od} == {hour_id_of_interest}",
        ),
        "hour": (
            f"{str_departure_hour_od} == {hour_id_of_interest}",
        ),
        "weekday": (
            f"{col_str_is_week} == {is_weekday}",
        ),
        "day_hour_weekday": (
            f"{col_str_is_week} == {is_weekday}",
            f"{col_str_day_od} == {day_id_of_interest}",
            f"{str_departure_hour_od} == {hour_id_of_interest}",
        ),
        "_": ("already everything aggregated",),
    }

    # baseline messages mirror dict_case_message (keeps lengths consistent)
    dict_case_message_baseline = dict_case_message.copy()

    # Debug prints
    print("[FILTERS] Filters keys:", list(dict_case_2_tuple_filters.keys()))
    for k in dict_case_2_tuple_filters:
        print(f"[FILTERS] {k} -> {len(dict_case_2_tuple_filters[k])} filters, messages len={len(dict_case_message[k])}")

    return dict_case_2_tuple_filters, dict_case_2_filters_baseline, dict_case_message, dict_case_message_baseline

# ================================================================
# Function: get values from dicts (keeps name & signature)
# ================================================================
def get_values_from_case_pipeline_OD_analysis(dict_column_flows: dict,
                                              dict_column_grid: dict,
                                              dict_output_hotspot_analysis: dict,
                                              str_day: str,
                                              time_interval: list,
                                              user_profile: str,
                                              is_weekday: bool,
                                              is_in_flows: str,
                                              suffix_in: str,
                                              name_dict: str,
                                              name_key: str,
                                              case_pipeline: str):
    """
    Retrieve a value from one of the three dicts using the unified schema.
    - Accepts both `is_in_flows` and `suffix_in` arguments; `suffix_in` is used
      as the canonical flow key. If suffix_in is falsy, fallback to is_in_flows.
    """

    if not suffix_in:
        suffix_in = is_in_flows
        print(f"[get_values] suffix_in not provided, falling back to is_in_flows: {suffix_in}")

#    print(f"[get_values] name_dict={name_dict}, name_key={name_key}, case_pipeline={case_pipeline}")
    schema = _get_case_schema(str_day, time_interval, user_profile, is_weekday, suffix_in)

    if case_pipeline not in schema:
        raise ValueError(f"[get_values] Unknown case_pipeline {case_pipeline}")

    keys = schema[case_pipeline]

    dict_map = {
        "dict_column_flows": dict_column_flows,
        "dict_column_grid": dict_column_grid,
        "dict_output_hotspot_analysis": dict_output_hotspot_analysis,
    }

    if name_dict not in dict_map:
        raise ValueError(f"[get_values] Unknown name_dict {name_dict}")

    return _nested_get(dict_map[name_dict], keys, name_key)

# ================================================================
# Function: fill output hotspot analysis (keeps name & signature)
# ================================================================
def fill_dict_output_hotspot_analysis_OD_analysis_from_case_pipeline(
        dict_output_hotspot_analysis: dict,
        str_day: str,
        time_interval: list,
        user_profile: str,
        is_weekday: bool,
        is_in_flows: str,
        suffix_in: str,
        case_pipeline: str,
        hotspot_2_origin_idx_2_crit_dest_idx: dict,
        list_indices_all_fluxes_for_colormap: list,
        hotspot_flows: list
):
    """
    Save hierarchical analysis results into dict_output_hotspot_analysis
    at the correct nested path based on case_pipeline (unified schema).
    """

    if not suffix_in:
        suffix_in = is_in_flows
        print(f"[fill_hotspot] suffix_in not provided, using is_in_flows={suffix_in}")

#    print(f"[fill_hotspot] case_pipeline={case_pipeline} str_day={str_day} time_interval={time_interval} user_profile={user_profile} is_weekday={is_weekday} suffix_in={suffix_in}")

    schema = _get_case_schema(str_day, time_interval, user_profile, is_weekday, suffix_in)
    if case_pipeline not in schema:
        raise ValueError(f"[fill_hotspot] Unknown case_pipeline {case_pipeline}")

    keys = schema[case_pipeline]

    _nested_set(dict_output_hotspot_analysis, keys, "hotspot_2_origin_idx_2_crit_dest_idx", hotspot_2_origin_idx_2_crit_dest_idx)
    _nested_set(dict_output_hotspot_analysis, keys, "list_indices_all_fluxes_for_colormap", list_indices_all_fluxes_for_colormap)
    _nested_set(dict_output_hotspot_analysis, keys, "hotspot_levels", hotspot_flows)

#    print(f"[fill_hotspot] Stored hotspot results at path {keys}")
    return dict_output_hotspot_analysis

# ================================================================
# Function: set column names for flows (keeps name & signature + return)
# ================================================================
def set_dict_column_names_flows_OD_analysis(dict_column_flows: dict,
                                            str_day: str,
                                            time_interval: list,
                                            user_profile: str,
                                            is_weekday: str,
                                            suffix_in: str,
                                            str_t: str,
                                            str_t1: str,
                                            case_pipeline: str):
    """
    Set the four flow-related column name strings at the correct nested path.
    """

#    print(f"[set_col_flows] case_pipeline={case_pipeline} str_day={str_day} time_interval={time_interval} user_profile={user_profile} is_weekday={is_weekday} suffix_in={suffix_in}")

    schema = _get_case_schema(str_day, time_interval, user_profile, is_weekday, suffix_in)
    if case_pipeline not in schema:
        raise ValueError(f"[set_col_flows] Unknown case_pipeline {case_pipeline}")

    keys = schema[case_pipeline]

    # Compose column names similarly to your previous formatting
    # Use nested_set to set the four keys
    name_n_trips = f"n_trips_{user_profile}_t_{str_t}_{str_t1}_{suffix_in}_w_{is_weekday}_d_{str_day}" if user_profile else f"n_trips_t_{str_t}_{str_t1}_{suffix_in}_w_{is_weekday}_d_{str_day}"
    name_baseline = f"n_trips_{user_profile}_t_{str_t}_{str_t1}_baseline_{suffix_in}_w_{is_weekday}_d_{str_day}" if user_profile else f"n_trips_t_{str_t}_{str_t1}_baseline_{suffix_in}_w_{is_weekday}_d_{str_day}"
    name_diff = f"difference_baseline_{user_profile}_t_{str_t}_{str_t1}_baseline_{suffix_in}_w_{is_weekday}_d_{str_day}" if user_profile else f"difference_baseline_t_{str_t}_{str_t1}_baseline_{suffix_in}_w_{is_weekday}_d_{str_day}"
    caption = f"Flow Intensity {user_profile} - {str_t} to {str_t1}_{suffix_in}_w_{is_weekday}_d_{str_day}" if user_profile else f"Flow Intensity - {str_t} to {str_t1}_{suffix_in}_w_{is_weekday}_d_{str_day}"

    _nested_set(dict_column_flows, keys, "str_col_n_trips", name_n_trips)
    _nested_set(dict_column_flows, keys, "str_col_n_trips_baseline", name_baseline)
    _nested_set(dict_column_flows, keys, "str_col_difference_baseline", name_diff)
    _nested_set(dict_column_flows, keys, "str_caption_colormap_flows", caption)

#    print(f"[set_col_flows] Set flow column names at {keys}: n_trips={name_n_trips}, baseline={name_baseline}, diff={name_diff}")
    return dict_column_flows

# ================================================================
# Function: set column names for grid (keeps name & signature + return)
# ================================================================
def set_dict_column_names_grid_OD_analysis(dict_column_grid,
                                           str_day,
                                           time_interval,
                                           user_profile,
                                           is_weekday,
                                           suffix_in,
                                           str_t,
                                           str_t1,
                                           case_pipeline: str):
    """
    Set the grid-related column name strings at the correct nested path.
    """

#    print(f"[set_col_grid] case_pipeline={case_pipeline} str_day={str_day} time_interval={time_interval} user_profile={user_profile} is_weekday={is_weekday} suffix_in={suffix_in}")

    schema = _get_case_schema(str_day, time_interval, user_profile, is_weekday, suffix_in)
    if case_pipeline not in schema:
        raise ValueError(f"[set_col_grid] Unknown case_pipeline {case_pipeline}")

    keys = schema[case_pipeline]

    name_hotspot = f"hotspot_level_tot_{suffix_in}_flows_{user_profile}_t_{str_t}_{str_t1}_w_{is_weekday}_d_{str_day}" if user_profile else f"hotspot_level_tot_{suffix_in}_flows_t_{str_t}_{str_t1}_w_{is_weekday}_d_{str_day}"
    name_tot = f"tot_{suffix_in}_flows_{user_profile}_t_{str_t}_{str_t1}_w_{is_weekday}_d_{str_day}" if user_profile else f"tot_{suffix_in}_flows_t_{str_t}_{str_t1}_w_{is_weekday}_d_{str_day}"

    _nested_set(dict_column_grid, keys, "str_col_hotspot", name_hotspot)
    _nested_set(dict_column_grid, keys, "str_col_total_flows_grid_hierachical_routine", name_tot)

#    print(f"[set_col_grid] Set grid column names at {keys}: hotspot={name_hotspot}, tot={name_tot}")
    return dict_column_grid

# ================================================================
# Function: set_columns_to_hold_for_OD_analysis (keeps name & return)
# ================================================================
def set_columns_to_hold_for_OD_analysis(dict_column_grid,
                                        str_day,
                                        time_interval,
                                        user_profile,
                                        is_weekday,
                                        suffix_in,
                                        case_pipeline):
    """
    Return the two extension columns from dict_column_grid for the given case.
    """
#    print(f"[set_cols_hold] case_pipeline={case_pipeline}, suffix_in={suffix_in}")
    schema = _get_case_schema(str_day, time_interval, user_profile, is_weekday, suffix_in)
    if case_pipeline not in schema:
        raise ValueError(f"[set_cols_hold] Unknown case_pipeline {case_pipeline}")

    keys = schema[case_pipeline]

    # retrieve hotspot and total-flows column names
    hotspot_col = _nested_get(dict_column_grid, keys, "str_col_hotspot")
    tot_col = _nested_get(dict_column_grid, keys, "str_col_total_flows_grid_hierachical_routine")

    extension_columns_2_hold = [hotspot_col, tot_col]
 #   print(f"[set_cols_hold] extension_columns_2_hold={extension_columns_2_hold} at path {keys}")
    return extension_columns_2_hold

# ================================================================
# Function: define_columns_to_hold_OD_analysis (keeps name & return)
# ================================================================
def define_columns_to_hold_OD_analysis(columns_2_hold_geopandas_base,
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
                                      case_pipeline):
    """
    Compose and return:
    - columns_2_hold_geopandas_for_flows_plot,
    - columns_flows_2_be_merged_2_keep,
    - on_colums_flows_2_join,
    - on_columns_grid_2_join
    following the unified nested schema for dict_column_flows.
    """
    print(f"[define_columns] case_pipeline={case_pipeline} suffix_in={suffix_in} str_day={str_day} time_interval={time_interval} user_profile={user_profile} is_weekday={is_weekday}")
    # combine base and extension columns
    columns_2_hold_geopandas_for_flows_plot = columns_2_hold_geopandas_base + extension_columns_2_hold
    print(f"[define_columns] Columns to hold for geopandas plot: {columns_2_hold_geopandas_for_flows_plot}")

    # ensure suffix_in exists (it may be passed as is_in_flows in older code)
    schema = _get_case_schema(str_day, time_interval, user_profile, is_weekday, suffix_in)
    if case_pipeline not in schema:
        raise ValueError(f"[define_columns] Unknown case_pipeline {case_pipeline}")
    keys = schema[case_pipeline]

    # Get the column names for n_trips and difference_baseline from dict_column_flows
    n_trips_col = _nested_get(dict_column_flows, keys, "str_col_n_trips")
    diff_col = _nested_get(dict_column_flows, keys, "str_col_difference_baseline")

    columns_flows_2_be_merged_2_keep = [str_col_origin, str_col_destination, n_trips_col, diff_col]
    print(f"[define_columns] columns_flows_2_be_merged_2_keep: {columns_flows_2_be_merged_2_keep}")

    # join columns
    on_colums_flows_2_join = [str_col_origin, str_col_destination]
    on_columns_grid_2_join = [col for col in columns_2_hold_geopandas_base if col != str_grid_idx]

    print(f"[define_columns] on_colums_flows_2_join={on_colums_flows_2_join}")
    print(f"[define_columns] on_columns_grid_2_join={on_columns_grid_2_join}")

    return columns_2_hold_geopandas_for_flows_plot, columns_flows_2_be_merged_2_keep, on_colums_flows_2_join, on_columns_grid_2_join

## EXTRACT COLUMNS THAT ARE NECESSAY TO COMPUTE DIFFERENCE PIPELINE ##
def extract_name_columns_for_difference_pipeline(dict_column_flows: dict,
                                                 dict_column_grid: dict,
                                                 str_day: str,
                                                 time_interval: list,
                                                 user_profile: str,
                                                 is_weekday: bool, 
                                                 is_in_flows: bool,
                                                 suffix_in: str,
                                                 case_pipeline: str):
    """
        Pick the names of the columns that are of interest for the difference pipeline.
        It is an utility function that allows to shrink the length of the code in the main function
    """ 
    # Change the name of the columns of the flows
    str_col_n_trips = get_values_from_case_pipeline_OD_analysis(dict_column_flows = dict_column_flows,dict_column_grid = None,dict_output_hotspot_analysis = None,str_day = str_day,time_interval = time_interval,user_profile = user_profile,is_weekday = is_weekday,is_in_flows = is_in_flows,suffix_in = suffix_in,name_dict = "dict_column_flows",name_key = "str_col_n_trips",case_pipeline = case_pipeline) 
    str_col_n_trips_baseline = get_values_from_case_pipeline_OD_analysis(dict_column_flows = dict_column_flows,dict_column_grid = None,dict_output_hotspot_analysis = None,str_day = str_day,time_interval = time_interval,user_profile = user_profile,is_weekday = is_weekday,is_in_flows = is_in_flows,suffix_in = suffix_in,name_dict = "dict_column_flows",name_key = "str_col_n_trips_baseline",case_pipeline = case_pipeline) 
    str_col_difference_baseline = get_values_from_case_pipeline_OD_analysis(dict_column_flows = dict_column_flows,dict_column_grid = None,dict_output_hotspot_analysis = None,str_day = str_day,time_interval = time_interval,user_profile = user_profile,is_weekday = is_weekday,is_in_flows = is_in_flows,suffix_in = suffix_in,name_dict = "dict_column_flows",name_key = "str_col_difference_baseline",case_pipeline = case_pipeline)
    str_col_total_flows_grid = get_values_from_case_pipeline_OD_analysis(dict_column_flows = None,dict_column_grid = dict_column_grid,dict_output_hotspot_analysis = None,str_day = str_day,time_interval = time_interval,user_profile = user_profile,is_weekday = is_weekday,is_in_flows = is_in_flows,suffix_in = suffix_in,name_dict = "dict_column_grid",name_key = "str_col_total_flows_grid_hierachical_routine",case_pipeline = case_pipeline)
    return str_col_n_trips, str_col_n_trips_baseline, str_col_difference_baseline, str_col_total_flows_grid


## EXTRACT THE COLUMNS THAT ARE OF INTEREST FOR THE PLOT ##
def extract_name_columns_for_hierarchical_plot(dict_column_flows: dict,
                                               dict_column_grid: dict,
                                               dict_output_hotspot_analysis: dict,
                                               str_day: str,
                                               time_interval: list,
                                               user_profile: str,
                                               is_weekday: bool,
                                               is_in_flows: bool,
                                               suffix_in: str,
                                               case_pipeline: str):
    """
        Pick the names of the columns that are of interest for the hierarchical plot.
        It is an utility function that allows to shrink the length of the code in the main function.
    """
    hotspot_2_origin_idx_2_crit_dest_idx = get_values_from_case_pipeline_OD_analysis(dict_column_flows = None,dict_column_grid = None,dict_output_hotspot_analysis = dict_output_hotspot_analysis,str_day = str_day,time_interval = time_interval,user_profile = user_profile,is_weekday = is_weekday,is_in_flows = is_in_flows,suffix_in = suffix_in,name_dict = "dict_output_hotspot_analysis",name_key = "hotspot_2_origin_idx_2_crit_dest_idx",case_pipeline = case_pipeline)
    str_col_total_flows_grid = get_values_from_case_pipeline_OD_analysis(dict_column_flows = None,dict_column_grid = dict_column_grid,dict_output_hotspot_analysis = None,str_day = str_day,time_interval = time_interval,user_profile = user_profile,is_weekday = is_weekday,is_in_flows = is_in_flows,suffix_in = suffix_in,name_dict = "dict_column_grid",name_key = "str_col_total_flows_grid_hierachical_routine",case_pipeline = case_pipeline)
    str_col_hotspot_level = get_values_from_case_pipeline_OD_analysis(dict_column_flows = None,dict_column_grid = dict_column_grid,dict_output_hotspot_analysis = None,str_day = str_day,time_interval = time_interval,user_profile = user_profile,is_weekday = is_weekday,is_in_flows = is_in_flows,suffix_in = suffix_in,name_dict = "dict_column_grid",name_key = "str_col_hotspot",case_pipeline = case_pipeline)
    str_col_n_trips = get_values_from_case_pipeline_OD_analysis(dict_column_flows = dict_column_flows,dict_column_grid = None,dict_output_hotspot_analysis = None,str_day = str_day,time_interval = time_interval,user_profile = user_profile,is_weekday = is_weekday,is_in_flows = is_in_flows,suffix_in = suffix_in,name_dict = "dict_column_flows",name_key = "str_col_n_trips",case_pipeline = case_pipeline)
    str_caption_colormap = get_values_from_case_pipeline_OD_analysis(dict_column_flows = dict_column_flows,dict_column_grid = None,dict_output_hotspot_analysis = None,str_day = str_day,time_interval = time_interval,user_profile = user_profile,is_weekday = is_weekday,is_in_flows = is_in_flows,suffix_in = suffix_in,name_dict = "dict_column_flows",name_key = "str_caption_colormap_flows",case_pipeline = case_pipeline)
    str_col_difference = get_values_from_case_pipeline_OD_analysis(dict_column_flows = dict_column_flows,dict_column_grid = None,dict_output_hotspot_analysis = None,str_day = str_day,time_interval = time_interval,user_profile = user_profile,is_weekday = is_weekday,is_in_flows = is_in_flows,suffix_in = suffix_in,name_dict = "dict_column_flows",name_key = "str_col_difference_baseline",case_pipeline = case_pipeline)
    return hotspot_2_origin_idx_2_crit_dest_idx, str_col_total_flows_grid, str_col_hotspot_level, str_col_n_trips, str_caption_colormap, str_col_difference