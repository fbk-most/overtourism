from OD import *
from constant_names_variables import dict_name_output_key_2_default_init_pipeline12, str_origin_od, str_destination_od, str_col_origin, str_col_destination, str_departure_hour_od, str_origin_visitor_class_id_od, col_str_is_week, col_str_day_od
from constant_names_variables import UserProfile2IndexVodafone
from dictionary_handles import _nested_get, _nested_set
    
import polars as pl
from typing import Any, Dict, List, Tuple
from itertools import combinations


# ================================================================
# Ordered conditioning mapping (keeps original column lists)
# ================================================================

# Flows = Pipeline 1 and 2
aggregation_names_flows = ["day", "hour", "user", "weekday"]

aggregation_names_2_columns_aggregation_flows = {"day":col_str_day_od,                     # NOTE: in [2024-07-01, ..., 2024-08-31]
                                                "hour":str_departure_hour_od,                # NOTE: in [0,1,...,23]
                                                "user":str_origin_visitor_class_id_od,       # NOTE: 1,2,3,4,5
                                                "weekday":col_str_is_week,                   # NOTE: True, False}
                                                }

dict_name_output_key_2_default_init_pipeline12 = {"dict_columns_flows": {"str_col_n_trips": [],
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

def init_dict_case2column_names_diffusione_1_2(aggregation_names_2_columns_aggregation: Dict[str, str]):
    """
        Generates the dictionary of the conditioning that are available to aggregate the presences for 
        the Markowitz analysis. It generates all the possible combinations of the keys in the input dictionary.
        Returns a dictionary where the keys are the combinations of the input keys (joined by "_") and the values
        are lists of the corresponding variable names, always including the area id as the first element.
        i.e.:
{
    # Order here is important and mirrors the case_pipeline ordering used
    # in the initialization and accessor functions below.
    "day_hour_user_weekday": [
        str_origin_od, str_destination_od, str_col_origin, str_col_destination,
        col_str_day_od, str_departure_hour_od, str_origin_visitor_class_id_od, col_str_is_week
    ],
    "hour_user_weekday": [
        str_origin_od, str_destination_od, str_col_origin, str_col_destination,
        str_departure_hour_od, str_origin_visitor_class_id_od, col_str_is_week
    ],
    "user_weekday": [
        str_origin_od, str_destination_od, str_col_origin, str_col_destination,
        str_origin_visitor_class_id_od, col_str_is_week
    ],
    "user": [
        str_origin_od, str_destination_od, str_col_origin, str_col_destination,
        str_origin_visitor_class_id_od
    ],
    "hour_weekday": [
        str_origin_od, str_destination_od, str_col_origin, str_col_destination,
        str_departure_hour_od, col_str_is_week
    ],
    "hour": [
        str_origin_od, str_destination_od, str_col_origin, str_col_destination,
        str_departure_hour_od
    ],
    "weekday": [
        str_origin_od, str_destination_od, str_col_origin, str_col_destination,
        col_str_is_week
    ],
    "day_hour_weekday": [
        str_origin_od, str_destination_od, str_col_origin, str_col_destination,
        col_str_day_od, str_departure_hour_od, col_str_is_week
    ],
    }
    """
    # Initialize output
    conditioning_dict = {}
    conditioning_dict_just_aggregation = {}
    # Generate all non-empty combinations of the keys
    for r in range(1, len(aggregation_names_2_columns_aggregation) + 1):
        for comb in combinations(aggregation_names_2_columns_aggregation.keys(), r):
            # Create a name for this combination (e.g., "time_visitor_is_weekday")
            key_conditioning_dict = "_".join(comb)
            
            # Base list always includes the area id of the origin and destination
            list_values_comb = [str_origin_od, str_destination_od, str_col_origin, str_col_destination]
            list_values_comb_just_aggregation = []
            # Add corresponding variable names
            for key in comb:
                list_values_comb.append(aggregation_names_2_columns_aggregation[key])
                list_values_comb_just_aggregation.append(aggregation_names_2_columns_aggregation[key])
            conditioning_dict[key_conditioning_dict] = list_values_comb
            conditioning_dict_just_aggregation[key_conditioning_dict] = list_values_comb_just_aggregation
    conditioning_dict["_"] = []
    conditioning_dict_just_aggregation["_"] = []
    return conditioning_dict, conditioning_dict_just_aggregation



def _get_case_schema_diffusione_1_2(dict_case2column_names: Dict[str, Any],
                                    str_day: str,
                                    time_interval: list,
                                    user_profile: str,
                                    is_weekday: bool,
                                    suffix_in: str) -> Dict[str, List[Any]]:
    """
        Dynamically generate a case schema mapping based on dict_ keys.
        NOTE: Associates the value of the different variables in  input to the keys in the dict_case2column_names
        to the case_schema. In this way we have for exampe: {"day_hour_user_weekday": [str_day, time_interval[0], user_profile, is_weekday, suffix_in]}.
        
    """
    case_schema = {}

    # Generate all non-empty combinations of dict_ keys
    for case_pipeline in dict_case2column_names.keys():
        list_case_pipeline = []
        if "day" in case_pipeline:
            list_case_pipeline.append(str_day)
        if "time" in case_pipeline:
            list_case_pipeline.append(time_interval[0])
        if "user" in case_pipeline:
            list_case_pipeline.append(user_profile)
        if "weekday" in case_pipeline:
            list_case_pipeline.append(is_weekday)
        list_case_pipeline.append(suffix_in)
        case_schema[case_pipeline] = list_case_pipeline

    return case_schema

# ================================================================
# Function: initialize dictionaries (keeps original signature)
# returns: dict_column_flows, dict_column_grid, dict_output_hotspot_analysis
# ================================================================


def _init_leaves_for_keys_diffusione_1_2(dict_column_flows,
                                         dict_column_grid,
                                         dict_output_hotspot_analysis,
                                         dict_name_output_key_2_default_init_pipeline12,
                                         keys: List[Any]):
    """
        Initialize the leaves of a nested dictionary based on a list of keys and a mapping of default values.
        NOTE: keys are going to be dependent on the case_pipeline. The lack of explicit dependence here is kind of confusing
        Output:
        - dict_column_flows: {key0: {key1: {key2: ... {str_col_n_trips: [], str_col_n_trips_baseline: [], str_caption_colormap_flows: "", str_col_difference_baseline: []}}}}
        - dict_column_grid: {key0: {key1: {key2: ... {str_col_hotspot: [], str_col_total_flows_grid_hierachical_routine: []}}}}
        - dict_output_hotspot_analysis: {key0: {key1: {key2: ... {hotspot_2_origin_idx_2_crit_dest_idx: {}, list_indices_all_fluxes_for_colormap: [], hotspot_levels: {}}}}}

    """
    for key in dict_name_output_key_2_default_init_pipeline12.keys():
        if key == "dict_columns_flows":
            for subkey in dict_name_output_key_2_default_init_pipeline12[key].keys():
                _nested_set(dict_column_flows, keys, subkey, dict_name_output_key_2_default_init_pipeline12[key][subkey])
        elif key == "dict_columns_grid":
            for subkey in dict_name_output_key_2_default_init_pipeline12[key].keys():
                _nested_set(dict_column_grid, keys, subkey, dict_name_output_key_2_default_init_pipeline12[key][subkey])
        elif key == "dict_output_hotspot_analysis":
            for subkey in dict_name_output_key_2_default_init_pipeline12[key].keys():
                _nested_set(dict_output_hotspot_analysis, keys, subkey, dict_name_output_key_2_default_init_pipeline12[key][subkey])


def initialize_dicts_output_diffussione_1_2(
    list_all_avaliable_days_flows: list,
    list_time_intervals: list,
    UserProfiles: list,
    week_days: list,
    case_2_is_in_flow: dict,
    dict_case2column_names: Dict[str, Any],
    case_pipeline: str,
    pipeline_name: str = "OD"  # you can change this depending on your data
):
    """
    Generalized initialization of dictionaries that hold flow, grid, and hotspot analysis columns.

    Parameters
    ----------
    list_all_avaliable_days_flows : list
        List of days to consider (e.g., ['2021-06-01', '2021-06-02']).
    list_time_intervals : list
        List of time intervals (e.g., ['08:00-10:00', '10:00-12:00']).
    UserProfiles : list
        List of user profile labels (e.g., ['residents', 'tourists']).
    week_days : list
        List of weekday flags (e.g., [True, False]).
    case_2_is_in_flow : dict
        Dictionary mapping flow type suffixes (e.g., {'in': True, 'out': False}).
    dict_case2column_names : dict
        Dictionary defining how to build the case schema.
    case_pipeline : str
        Pipeline schema key, e.g. 'day_hour_user_weekday'.
    pipeline_name : str, optional
        Pipeline type ('OD' or 'Markowitz'), defaults to 'OD'.

    Returns
    -------
    Tuple[Dict, Dict, Dict]
        (dict_column_flows, dict_column_grid, dict_output_hotspot_analysis)
    """

    print(f"[INIT] Case pipeline = {case_pipeline}")
    # NOTE:
    dict_column_flows = {}
    dict_column_grid = {}
    dict_output_hotspot_analysis = {}
    # Determine which iterables are relevant from the pipeline name
    aggregation_names_2_iterables = {
        "day": list_all_avaliable_days_flows,
        "hour": list_time_intervals,
        "user": UserProfiles,
        "weekday": week_days,
        }

    # Figure out which iterables to use based on the case_pipeline name
    active_dimensions = [key for key in aggregation_names_2_iterables if key in case_pipeline]

    # Build the Cartesian product over all relevant dimensions
    import itertools
    all_combinations = itertools.product(*[aggregation_names_2_iterables[k] for k in active_dimensions])

    # Iterate through all combinations and suffixes
    for combination in all_combinations:
        for suffix_in in case_2_is_in_flow.keys():
            kwargs = {
                "dict_case2column_names": dict_case2column_names,
            }
            # Fill kwargs dynamically {}
            for dim, value in zip(active_dimensions, combination):
                kwargs[dim] = value
            kwargs["suffix_in"] = suffix_in

            # Get the schema for this combination
            case_schema = _get_case_schema_diffusione_1_2(
                pipeline_name=pipeline_name,
                **kwargs
            )
            if case_pipeline not in case_schema:
                raise ValueError(f"case_pipeline {case_pipeline} not found in schema output.")

            keys = case_schema[case_pipeline]
            _init_leaves_for_keys_diffusione_1_2(dict_column_flows,
                                                 dict_column_grid,
                                                 dict_output_hotspot_analysis,
                                                 dict_name_output_key_2_default_init_pipeline12,
                                                 keys)

    return dict_column_flows, dict_column_grid, dict_output_hotspot_analysis


def compute_filters_and_messages_for_case_analysis(
                                                   conditioning_dict_just_aggregation: Dict[str, Any],
                                                    day_id_of_interest: str,
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
    # NEW APPROACH
    aggregation_name_2_value_condition = {col_str_is_week: is_weekday,
                                        col_str_day_od: day_id_of_interest,
                                        str_departure_hour_od: hour_id_of_interest,
                                        str_origin_visitor_class_id_od: int_user_profile
                                        }
    for case_pipeline in conditioning_dict_just_aggregation.keys():
        for column_name in conditioning_dict_just_aggregation[case_pipeline]:
            value_condition = aggregation_name_2_value_condition.get(column_name, None)
            if value_condition is not None:
                condition = (pl.col(column_name) == value_condition)
            else:
                raise ValueError(f"Column name {column_name} not found in aggregation_name_2_value_condition mapping.")
            if case_pipeline not in dict_case_2_tuple_filters:
                dict_case_2_tuple_filters[case_pipeline] = ()
                dict_case_2_filters_baseline[case_pipeline] = ()
                dict_case_message[case_pipeline] = ()
                dict_case_message_baseline[case_pipeline] = ()
            dict_case_2_tuple_filters[case_pipeline] += (condition,)
            dict_case_message[case_pipeline] += (f"{column_name} == {value_condition}",)
            if column_name != col_str_day_od:
                dict_case_2_filters_baseline[case_pipeline] += (condition,)
                dict_case_message_baseline[case_pipeline] += (f"{column_name} == {value_condition}",)
            else:
                # Skip day condition for baseline
                pass
            # NOTE: touristic period
            dict_case_2_tuple_filters[case_pipeline]["_"] = ()
            dict_case_message[case_pipeline]["_"] = ("already everything aggregated",)
            # NOTE: baseline
            dict_case_2_filters_baseline[case_pipeline]["_"] = ()
            dict_case_message_baseline[case_pipeline]["_"] = ("already everything aggregated",)
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
    schema = _get_case_schema_diffusione_1_2(str_day, time_interval, user_profile, is_weekday, suffix_in)

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

    schema = _get_case_schema_diffusione_1_2(str_day, time_interval, user_profile, is_weekday, suffix_in)
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

    schema = _get_case_schema_diffusione_1_2(str_day, time_interval, user_profile, is_weekday, suffix_in)
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

    schema = _get_case_schema_diffusione_1_2(str_day, time_interval, user_profile, is_weekday, suffix_in)
    if case_pipeline not in schema:
        raise ValueError(f"[set_col_grid] Unknown case_pipeline {case_pipeline}")

    keys = schema[case_pipeline]

    name_hotspot = f"hotspot_level_tot_{suffix_in}_flows_{user_profile}_t_{str_t}_{str_t1}_w_{is_weekday}_d_{str_day}" if user_profile else f"hotspot_level_tot_{suffix_in}_flows_t_{str_t}_{str_t1}_w_{is_weekday}_d_{str_day}"
    name_tot = f"tot_{suffix_in}_flows_{user_profile}_t_{str_t}_{str_t1}_w_{is_weekday}_d_{str_day}" if user_profile else f"tot_{suffix_in}_flows_t_{str_t}_{str_t1}_w_{is_weekday}_d_{str_day}"

    _nested_set(dict_column_grid, keys, "str_col_hotspot", name_hotspot)
    _nested_set(dict_column_grid, keys, "str_col_total_flows_grid_hierachical_routine", name_tot)

#    print(f"[set_col_grid] Set grid column names at {keys}: hotspot={name_hotspot}, tot={name_tot}")
    return dict_column_grid
