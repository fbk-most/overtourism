"""
    To handle the pipeline you need essentially the following informations:
    - AVAILABLE AT THE START
        - aggregation_names: list of the possible conditioning names (e.g., day, hour, user, weekday)
        - aggregation_names_2_columns_aggregation: mapping from the conditioning names to the corresponding variable {}
    - GENERATED AT THE START
        - dict_case2column_names: mapping from the concatenated conditioning names (e.g., day_hour_user_weekday) to the list of corresponding variable names (always including the area id as the first element)
        - case_schema: mapping from the concatenated conditioning names to the list of
        - dict_name_output_key_2_default_init_pipeline: mapping from the output keys to their default initialization values
    - AVAILABLE AT RUNTIME

"""

from itertools import combinations
from itertools import combinations
from typing import Dict, List, Any
from data_preparation.diffusion.constant_names_variables import str_area_id_presenze, str_time_block_id_presenze, str_visitor_class_id_presenze, str_country_presenze, col_str_is_week
from data_preparation.diffusion.constant_names_variables import AGGREGATION_NAMES_2_COLUMNS_AGGREGATION_PRESENCES, DICT_NAME_OUTPUT_KEY_2_DEFAULT_INIT_PIPELINE_3
from data_preparation.diffusion.dictionary_handles import _nested_get, _nested_set

# Presences = Pipeline 3

def init_dict_case2column_names_diffusione_3(name_keys_pipeline_2_columns_aggregation_diffusione_3):
    """
        Generates the dictionary of the conditioning that are available to aggregate the presences for 
        the Markowitz analysis. It generates all the possible combinations of the keys in the input dictionary.
        Returns a dictionary where the keys are the combinations of the input keys (joined by "_") and the values
        are lists of the corresponding variable names, always including the area id as the first element.
        i.e.:
        {'time': ['AREA_ID', 'TIME_BLOCK_ID'],
        'visitor': ['AREA_ID', 'VISITOR_CLASS_ID'],
        'country': ['AREA_ID', 'COUNTRY'],
        'weekday': ['AREA_ID', 'is_weekday'],
        'time_visitor': ['AREA_ID', 'TIME_BLOCK_ID', 'VISITOR_CLASS_ID'],
        'time_country': ['AREA_ID', 'TIME_BLOCK_ID', 'COUNTRY'],
        'time_weekday': ['AREA_ID', 'TIME_BLOCK_ID', 'is_weekday'],
        'visitor_country': ['AREA_ID', 'VISITOR_CLASS_ID', 'COUNTRY'],
        'visitor_weekday': ['AREA_ID', 'VISITOR_CLASS_ID', 'is_weekday'],
        'country_weekday': ['AREA_ID', 'COUNTRY', 'is_weekday'],
        'time_visitor_country': ['AREA_ID','TIME_BLOCK_ID','VISITOR_CLASS_ID','COUNTRY'],
        'time_visitor_weekday': ['AREA_ID','TIME_BLOCK_ID','VISITOR_CLASS_ID','is_weekday'],
        'time_country_weekday': ['AREA_ID','TIME_BLOCK_ID','COUNTRY','is_weekday'],
        'visitor_country_weekday': ['AREA_ID','VISITOR_CLASS_ID','COUNTRY','is_weekday'],
        'time_visitor_country_weekday': ['AREA_ID','TIME_BLOCK_ID','VISITOR_CLASS_ID','COUNTRY','is_weekday'],
        'time_nationality_visitor_country_weekday': ['AREA_ID','TIME_BLOCK_ID','NATIONALITY_CLASS_ID','VISITOR_CLASS_ID','COUNTRY','is_weekday']}
    """
    # Initialize output
    dict_case2column_names = {}

    # Generate all non-empty combinations of the keys
    for r in range(1, len(name_keys_pipeline_2_columns_aggregation_diffusione_3) + 1):
        for comb in combinations(name_keys_pipeline_2_columns_aggregation_diffusione_3, r):
            # Create a name for this combination (e.g., "time_visitor_is_weekday")
            key_conditioning_dict = "_".join(comb)
            
            # Base list always includes the area id
            list_values_comb = [str_area_id_presenze]
            
            # Add corresponding variable names
            for key in comb:
                list_values_comb.append(name_keys_pipeline_2_columns_aggregation_diffusione_3[key])
            
            dict_case2column_names[key_conditioning_dict] = list_values_comb
    dict_case2column_names["_"] = []
    return dict_case2column_names



# ================================================================
# Helper: unified schema (list of nesting keys) for each pipeline
# ================================================================

def _get_case_schema_diffusione_3(
                                dict_case2column_names: Dict[str, Any],
                                list_time,
                                list_visitor,
                                list_country,
                                list_weekday,
                                ) -> Dict[str, List[Any]]:
    """
    Dynamically generate a case schema mapping based on dict_ keys.

    Parameters
    ----------
    dict_ : dict_case2column_names
        Dictionary mapping key names (e.g., 'time', 'visitor', ...) to their corresponding variables.
        Example: {"time":{"time":TIME_BLOCK_ID},
                 "visitor":{"visitor":VISITOR_CLASS_ID}, ...
                 "visitor_country_weekday":{"visitor":VISITOR_CLASS_ID, "country":COUNTRY, "weekday":IS_WEEKDAY}, ...}
    
    Returns
    -------
    Dict[str, Dict[str, List[Any]]]
        Mapping from concatenated key names (e.g. 'time_visitor_is_weekday') to lists of variable values.
    Example Output:
    {visitor:{visitor: [...], ...}, 
    visitor_country:{visitor: [...], country: [...], ...}, 
    visitor_country_weekday:{visitor: [...], country: [...], weekday: [...], ...}, 
    ...}
    
    """
    case_2iterable_values = {}

    # Generate all non-empty combinations of dict_ keys
    for case_pipeline in dict_case2column_names.keys():
        case_2iterable_values[case_pipeline] = {}
        if "time" in case_pipeline:
            case_2iterable_values[case_pipeline]["time"] = list_time
        if "visitor" in case_pipeline:
            case_2iterable_values[case_pipeline]["visitor"] = list_visitor
        if "country" in case_pipeline:
            case_2iterable_values[case_pipeline]["country"] = list_country
        if "weekday" in case_pipeline:
            case_2iterable_values[case_pipeline]["weekday"] = list_weekday
    return case_2iterable_values



def _init_leaves_for_keys_diffusione_3(dict_presences_output,
                                       DICT_NAME_OUTPUT_KEY_2_DEFAULT_INIT_PIPELINE_3,
                                       keys):
    """
        Initialize the leaves of a nested dictionary based on a list of keys and a mapping of default values.
        NOTE: keys are going to be dependent on the case_pipeline. The lack of explicit dependence here is kind of confusing
        Output:
            dict_presences_output: {key0: {key1: {key2: { ... {"column_presences_no_baseline": [default_value], }
            
                                                        }
                                                }
                                            }
                                    }
        keys: list of keys to navigate the nested dictionary 
    """
    for key in DICT_NAME_OUTPUT_KEY_2_DEFAULT_INIT_PIPELINE_3.keys():
        print(f"Initializing key {key} at path {keys} with default value {DICT_NAME_OUTPUT_KEY_2_DEFAULT_INIT_PIPELINE_3[key]}")
        _nested_set(dict_presences_output, 
                    keys, 
                    key, 
                    DICT_NAME_OUTPUT_KEY_2_DEFAULT_INIT_PIPELINE_3[key])     # NOTE

    return dict_presences_output

def initialize_dict_presences_output_diffusione_3(dict_case2column_names: Dict[str, Any],
                                                  list_all_hours,
                                                  list_all_visitors,
                                                  list_all_countries,
                                                  list_all_weekdays,
                                                  case_pipeline: str):
    """
    Generalized initialization of dictionaries that hold the portfolio analysis results for presences.
    """
    dict_presences_output = {}
    # Get the schema for this combination
    case_2iterable_values = _get_case_schema_diffusione_3( 
                                        dict_case2column_names= dict_case2column_names, 
                                        list_time = list_all_hours, 
                                        list_visitor = list_all_visitors, 
                                        list_country = list_all_countries, 
                                        list_weekday = list_all_weekdays)

    if case_pipeline not in case_2iterable_values:
        raise ValueError(f"case_pipeline {case_pipeline} not found in schema output.")

    keys = case_2iterable_values[case_pipeline]
    dict_presences_output = _init_leaves_for_keys_diffusione_3(dict_presences_output = dict_presences_output,
                                                               DICT_NAME_OUTPUT_KEY_2_DEFAULT_INIT_PIPELINE_3 = DICT_NAME_OUTPUT_KEY_2_DEFAULT_INIT_PIPELINE_3,
                                                               keys = keys)
    return dict_presences_output,case_2iterable_values

import polars as pl
from typing import Any, Dict, List, Tuple
from itertools import combinations
from data_preparation.diffusion.dictionary_handles import _nested_get, _nested_set


# ================================================================
# 1. Compute filters and messages
# ================================================================

import polars as pl
from typing import Any, Dict

def compute_filters_and_messages_for_case_analysis_diffusione_3(
    dict_case2column_names: Dict[str, Any],
    time_of_interest: Any,
    visitor_of_interest: Any,
    country_of_interest: Any,
    is_weekday: bool,
):
    """
    Compute filters and messages for case analysis in Pipeline 3 (presences).
    It maps the conditioning columns (from dict_case2column_names) to
    their corresponding filter conditions and human-readable messages.
    """
    dict_case_2_tuple_filters = {}
    dict_case_message = {}

    aggregation_name_2_value_condition = {
        "time": time_of_interest,
        "visitor": visitor_of_interest,
        "country": country_of_interest,
        "weekday": is_weekday,
    }

    for case_pipeline, list_columns in dict_case2column_names.items():
        if case_pipeline == "_":
            dict_case_2_tuple_filters["_"] = ()
            dict_case_message["_"] = ("already everything aggregated",)
            continue

        filters = []
        messages = []

        for agg_name, col_name in AGGREGATION_NAMES_2_COLUMNS_AGGREGATION_PRESENCES.items():
            if agg_name in case_pipeline:
                value = aggregation_name_2_value_condition[agg_name]

                # Handle None values safely
                if value is None:
                    filters.append(pl.col(col_name).is_null())
                    messages.append(f"{col_name} IS NULL")
                else:
                    filters.append(pl.col(col_name) == value)
                    messages.append(f"{col_name} == {value}")

        dict_case_2_tuple_filters[case_pipeline] = tuple(filters)
        dict_case_message[case_pipeline] = tuple(messages)

    return dict_case_2_tuple_filters, dict_case_message


# ================================================================
# 2. Getter from nested dicts (analogue to get_values_from_case_pipeline_OD_analysis)
# ================================================================

def nested_get_output_from_key_presences_analysis(
    case_2iterable_values: dict,
    dict_presences_output: dict,
    name_key: str,
    case_pipeline: str,):
    """
    Input:
        case_2iterable_values: output of _get_case_schema_diffusione_3: {case_pipeline: {key: list_of_values, ...}, ...}
    Retrieve a value from the nested dict_presences_output for the given case pipeline.
    
    """
    keys = case_2iterable_values[case_pipeline]
    got_value = _nested_get(dict_presences_output, keys, name_key)
    return got_value


# ================================================================
# 3. Set column names for presences (analogous to set_dict_column_names_flows_OD_analysis)
# ================================================================

def nested_set_dict_column_names_presences_analysis(
    case_2iterable_values: dict,
    dict_presences_output: dict,
    time: Any,
    visitor: Any,
    country: Any,
    is_weekday: bool,
    case_pipeline: str,
):
    """
    Set column names for presences analysis output at the correct nested path.
    NOTE: This function assumes that the leaves have already been initialized.
    NOTE: This is the function to touch when another column name is needed.
    """
    keys = case_2iterable_values[case_pipeline]

    # Build column name templates
    base = f"v_{visitor}_c_{country}_w_{is_weekday}_t_{time}"
    _nested_set(dict_presences_output, keys, "column_presences_no_baseline", f"presences_{base}")
    _nested_set(dict_presences_output, keys, "column_presences_baseline", f"presences_baseline_{base}")
    _nested_set(dict_presences_output, keys, "column_total_diff_october_mean_0", f"diff_oct_mean0_{base}")
    _nested_set(dict_presences_output, keys, "column_total_diff_october_mean_0_var_1", f"diff_oct_mean0_var1_{base}")
    _nested_set(dict_presences_output, keys, "column_total_diff_october_var_1", f"diff_oct_var1_{base}")
    _nested_set(dict_presences_output, keys, "column_total_diff_oct", f"diff_oct_{base}")
    _nested_set(dict_presences_output, keys, "column_std", f"std_{base}")
    _nested_set(dict_presences_output, keys, "column_expected_return", f"exp_return_{base}")
    _nested_set(dict_presences_output, keys, "column_cov", f"cov_{base}")
    _nested_set(dict_presences_output, keys, "column_portfolio", f"portfolio_{base}")

    return dict_presences_output



