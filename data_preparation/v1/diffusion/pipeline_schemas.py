from Markowitz_pipeline import *
from OD_pipeline import *
from constant_names_variables import *

def init_dict_case2column_names(pipeline_name: str) -> Dict[str, Any]:
    """
        Initialize the case to column names mapping based on the specified pipeline.
        NOTE: The columns' names are the columns of the input dataframes (e.g., presences (Markowitz), flows (OD), etc.)
    """
    if pipeline_name == "Markowitz":
        dict_case2column_names = dict_case2column_names_diffusione_3(name_keys_pipeline_2_columns_aggregation_diffusione_3)
    elif pipeline_name == "OD":
        dict_case2column_names = dict_case2column_names_diffusione_1_2(name_keys_pipeline_2_columns_aggregation_diffusione_1_2)
    else:
        raise ValueError(f"Unknown pipeline name: {pipeline_name}")
    return dict_case2column_names

from typing import Any, Dict, List

def _get_case_schema(pipeline_name: str,
                     dict_case2column_names: Dict[str, Any],
                     *,
                     str_day: str = None,
                     time_interval: list = None,
                     user_profile: str = None,
                     time: Any = None,
                     visitor: Any = None,
                     country: Any = None,
                     is_weekday: bool = None,
                     suffix_in: str = None
                     ) -> Dict[str, List[Any]]:
    """
    Get the case schema based on the specified pipeline.
    
    This provides a unified interface for different schema generation pipelines
    (e.g., 'OD' and 'Markowitz') with input validation through assertions.

    Parameters
    ----------
    pipeline_name : str
        Name of the schema pipeline ('OD' or 'Markowitz').
    dict_case2column_names : Dict[str, Any]
        Mapping of case names to column names.
    str_day, time_interval, user_profile, suffix_in : optional
        Required for 'OD' pipeline.
    time, visitor, country : optional
        Required for 'Markowitz' pipeline.
    is_weekday : bool
        Used by both pipelines.

    Returns
    -------
    Dict[str, List[Any]]
        Mapping from case names to lists of parameter values.
    """
    if pipeline_name == "OD":
        # Validate required arguments
        assert str_day is not None, "OD pipeline requires 'str_day'"
        assert time_interval is not None and isinstance(time_interval, list), \
            "OD pipeline requires 'time_interval' as a list"
        assert user_profile is not None, "OD pipeline requires 'user_profile'"
        assert suffix_in is not None, "OD pipeline requires 'suffix_in'"
        assert is_weekday is not None, "OD pipeline requires 'is_weekday'"
        case_schema = _get_schema_diffusione_1_2(
            dict_case2column_names=dict_case2column_names,
            str_day=str_day,
            time_interval=time_interval,
            user_profile=user_profile,
            is_weekday=is_weekday,
            suffix_in=suffix_in
        )

    elif pipeline_name == "Markowitz":
        # Validate required arguments
        assert time is not None, "Markowitz pipeline requires 'time'"
        assert visitor is not None, "Markowitz pipeline requires 'visitor'"
        assert country is not None, "Markowitz pipeline requires 'country'"
        assert is_weekday is not None, "Markowitz pipeline requires 'is_weekday'"
        case_schema = _get_case_schema_diffusione_3(
            dict_case2column_names=dict_case2column_names,
            time=time,
            visitor=visitor,
            country=country,
            is_weekday=is_weekday
        )

    else:
        raise ValueError(f"Unknown pipeline name: {pipeline_name}")

    return case_schema
