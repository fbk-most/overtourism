"""
Created on 19/04/2025 author: Alberto Amaduzzi
This script is used to set the configuration for the project.
It contains the paths to the data and output folders, the names of the datasets,
the names of the variables, and the parameters for the analysis.
It is used to set the configuration for the project.
NOTE: Change here the paths to the data and output folders, the names of the datasets,
"""

import os
from collections import defaultdict
from data_preparation.v2.utils.flows_utils.constant_names_variables import (
    str_dir_output,
)


def set_config(str_dir_output_path):
    """Set the (minimal) configuration for the project.

    Args:
        str_dir_output_path: path to the output folder. Created if missing.

    Returns:
        config: dict with a single populated key, `str_dir_output`, holding
            the output folder path. Downstream code (e.g.
            `init_distance_matrix_associated_to_polygons`) reads this key to
            build file paths under the output folder.
    """
    config = defaultdict()

    config[str_dir_output] = str_dir_output_path
    os.makedirs(str_dir_output_path, exist_ok=True)

    return config
