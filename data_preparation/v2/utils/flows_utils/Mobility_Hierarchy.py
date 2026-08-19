"""
Mobility Hierarchy Analysis Module

This module implements hierarchical analysis of mobility flows to identify tourism hotspots
and critical flow patterns using the Lorenz curve and Loubar threshold methodology.

Key Features:
- Hierarchical hotspot classification (0-4 levels) based on flow intensity
- Lorenz curve analysis for identifying flow concentration patterns
- Loubar threshold computation for automatic hotspot detection
- Support for both in-flow and out-flow analysis
- Interactive Folium visualization of hierarchical patterns
- Integration with gravity model-generated or real mobility data

Main Class:
    MobilityHierarchy: Core class for performing hierarchical mobility analysis

Typical Workflow:
    1. Initialize with grid/polygon_shape (GeoDataFrame) and flows (Polars DataFrame)
    2. Run hierarchical routine for in-flows and out-flows
    3. Generate visualizations and extract critical flow patterns

The analysis helps identify:
- High-impact tourism destinations (hotspots)
- Critical mobility corridors between regions
- Flow concentration patterns and inequality measures
- Multi-level hierarchy of regional importance

Dependencies: numpy, polars, geopandas, folium, matplotlib
Author: Alberto Amaduzzi
"""

import geopandas as gpd
import numpy as np
import polars as pl
from typing import Dict, List
from data_preparation.v2.utils.flows_utils.Mobility_Hierarchy_functions import (
    extract_hotspot_levels,
    get_critical_fluxes_per_hotspot_level,
    get_lorenz_curve,
)
from data_preparation.v2.utils.flows_utils.OD import compute_total_flows_from_flow


class MobilityHierarchy:
    def __init__(
        self,
        grid: gpd.GeoDataFrame,
        flows: pl.DataFrame,
        int_levels: int = 5,  # NOTE: This is the number of levels to extract from the hierarchy
        str_population_col: str = "Popolazione_Totale",  # NOTE: This is the column in the grid GeoDataFrame that contains the population data
        str_col_comuni_name: str = "city_name",  # NOTE: This is the column in the grid GeoDataFrame that contains the name of the city (or the identifier that does not correspond with numerical order.)
        str_col_origin: str = "i",  # NOTE: "i" is the origin column in the flows DataFrame and coincides with the index of the grid GeoDataFrame
        str_col_destination: str = "j",  # NOTE: "j" is the destination column in the flows DataFrame and coincides with the index of the grid GeoDataFrame
        str_col_n_trips: str = "n_trips",  # NOTE: "n_trips" is the column in the flows DataFrame that contains the number of trips
    ):
        # NOTE: Grid Columns
        self.str_population_col = str_population_col
        self.str_col_comuni_name = str_col_comuni_name
        # NOTE: Flows Columns
        self.str_col_origin = str_col_origin
        self.str_col_destination = str_col_destination
        self.str_col_n_trips = str_col_n_trips
        self.str_col_population_i = f"{str_population_col}_{str_col_origin}"
        self.str_col_population_j = f"{str_population_col}_{str_col_destination}"
        # NOTE: Hierarchical Parameter
        self.str_hotspot_prefix = "hotspot_level"
        self.int_levels = int_levels
        self.grid = grid.copy()
        self.flows = flows
        self.hotspot_levels = {}

    def _hierarchical_routine(
        self, is_in_flows, str_col_total_flows_grid, y_label, str_col_n_trips_flows
    ):
        """
        Hierarchical routine to compute total flows and extract hotspot levels.
        Parameters:
            is_in_flows (bool): True for in-flows, False for out-flows
            str_col_total_flows_grid (str): Column name for total flows in the grid
            y_label (str): Label for the y-axis in plots
            str_col_n_trips_flows (str): Column name for number of trips in flows
        Description:
            - Computes total flows from the flow matrix to the grid. -> init self.grid[str_col_total_flows_grid] NOTE: information about the total flows in the grid.
            - Extracts hotspot levels based on the Loubar threshold. -> {int_level: {int_idx_grid: [int_idx_grid_complement,...]}} NOTE: int_idx_grid (int_idx_grid_complement) = index origin (index destination) if is_in_flows else index destination (index origin)
            - Annotates the grid with hotspot levels. -> init self.grid[f'{self.str_hotspot_prefix}_{str_col_total_flows_grid}'] NOTE: information about the hotspot levels in the grid.
            - Plots the Lorenz curve per level.
            - Visualizes the hierarchy of hotspots on a Folium map.
        Returns:
            self.hotspot_levels {int_level: {int_idx_grid: [int_idx_grid_complement,...]}}: Dictionary of hotspot levels with indices

        """
        # NOTE: From flow matrix -> grid total out flows
        self.grid = compute_total_flows_from_flow(
            self.flows,
            self.grid,
            is_in_flows,
            str_col_total_flows_grid,
            str_col_origin=self.str_col_origin,
            str_col_destination=self.str_col_destination,
            str_col_n_trips=str_col_n_trips_flows,
        )

        # NOTE: Extract the total flows from the grid
        self.extract_hotspot_levels(
            str_col_total_flows_grid=str_col_total_flows_grid,
            max_levels=self.int_levels,
        )

        # Check if any hotspots were found
        if not self.hotspot_levels:
            print(f"Warning: No hotspots found for {str_col_total_flows_grid}!")
            # Create an empty hotspot level to prevent errors
            self.hotspot_levels = {0: []}

        # NOTE: Annotate the grid with the hotspot levels
        self.annotate_grid_with_levels(
            str_col_total_flows_grid=str_col_total_flows_grid,
        )
        return self.hotspot_levels

    ############ FLOWS ANALYSIS METHODS ############

    @staticmethod
    def get_lorenz_curve(flows: np.ndarray):
        sorted_indices = np.argsort(flows)
        # Step 2: Compute the cumulative distribution
        sorted_flows = flows[sorted_indices]
        x = np.linspace(0, 1, len(flows))
        y = np.cumsum(sorted_flows) / np.sum(sorted_flows)
        return x, y, sorted_indices

    @staticmethod
    def get_loubar_threshold(flows: np.ndarray) -> float:
        """
            Computes the list of indices that correspond to the ones that are categorized
            as hotspots based on the Loubar threshold.
        Parameters:
            flows (np.ndarray): The array of outflows to analyze. NOTE: Same dimension of the grid.

        """
        return get_lorenz_curve(flows)

    def extract_hotspot_levels(
        self,
        str_col_total_flows_grid,
        max_levels: int = 5,
    ) -> Dict[int, List[int]]:
        """
        Extracts hotspot levels based on the Loubar threshold from the outflows.
        Parameters:
        max_levels (int): Maximum number of levels to extract.

        """
        self.hotspot_levels = extract_hotspot_levels(
            self.grid,
            str_col_total_flows_grid,
            max_levels=max_levels,
        )

    def annotate_grid_with_levels(
        self,
        str_col_total_flows_grid,
    ):
        """
        NOTE: The column of the hotspot is related to different classes of mobility:
        i.e. tourists, residents, commuters, etc.
        """
        for level, indices in self.hotspot_levels.items():
            self.grid.loc[
                indices, f"{self.str_hotspot_prefix}_{str_col_total_flows_grid}"
            ] = level
        self.grid[f"{self.str_hotspot_prefix}_{str_col_total_flows_grid}"] = (
            self.grid[f"{self.str_hotspot_prefix}_{str_col_total_flows_grid}"]
            .fillna(-1)
            .astype(int)
        )


## ---------------------- PIPELINE SPECIFIC Main_diffusion_1_2 ---------------------- ##


def pipeline_mobility_hierarchy_time_day_type_trips(
    cities_gdf,
    Tij_dist_fit_gravity,
    str_population_col_grid,
    str_col_comuni_name,
    str_col_origin,
    str_col_destination,
    str_col_n_trips,
    str_col_total_flows_grid,
    str_hotspot_prefix,
    str_grid_idx,
    is_in_flows,
    int_levels=5,
):
    """
    @description:
        The input is differentiated by:
            - in-flows and out-flows.
            - class of user (i.e. tourists, residents, commuters, etc.) -> user_profile.
            - time interval (str_t, str_t1).
    For each different configurations of these parameters it extracts:
        - aggregated flows from Tij_dist_fit_graavity to the grid (in-out flows according to is_in_flows). hierarchical_routine -> compute_total_flows_from_flow (output: gird[str_col_total_flows_grid_hierachical_routine])
        - hotspot levels from the grid (in-out flows according to is_in_flows). hierarchical_routine -> extract_hotspot_levels: (output: hotspot_dict: Dict[int, List[int]]) -> list of indices of grid of (in/out flows)
        - Annotates the grid with hotspot levels. _hierarchical_routine -> annotate_grid_with_levels:  self.grid[f'{self.str_hotspot_prefix}_{str_col_total_flows_grid}'] NOTE: information about the hotspot levels in the grid.
        - Plots the Lorenz curve per level.
        - Visualizes the hierarchy of hotspots on a Folium map.

    """

    if is_in_flows:
        y_label = "in flows"
        str_col_total_flows_grid_hierachical_routine = str_col_total_flows_grid
    else:
        y_label = "out flows"
        str_col_total_flows_grid_hierachical_routine = str_col_total_flows_grid
    #    print(f"Running Mobility Hierarchy Analysis for {user_profile} from {str_t} to {str_t1} with {'in' if is_in_flows else 'out'} flows..., flows column: {str_col_total_flows_grid_hierachical_routine}")
    mh = MobilityHierarchy(
        grid=cities_gdf,
        flows=Tij_dist_fit_gravity,
        int_levels=int_levels,  # NOTE: This is the number of levels to extract from the hierarchy
        str_population_col=str_population_col_grid,  # NOTE: This is the column in the grid GeoDataFrame that contains the population data
        str_col_comuni_name=str_col_comuni_name,  # NOTE: This is the column in the grid GeoDataFrame that contains the name of the city (or the identifier that does not correspond with numerical order.)
        str_col_origin=str_col_origin,  # NOTE: "i" is the origin column in the flows DataFrame and coincides with the index of the grid GeoDataFrame
        str_col_destination=str_col_destination,  # NOTE: "j" is the destination column in the flows DataFrame and coincides with the index of the grid GeoDataFrame
        str_col_n_trips=str_col_n_trips,  # NOTE: "n_trips" is the column in the flows DataFrame that contains the number of trips
    )
    if str_grid_idx not in mh.grid.columns:
        mh.grid[str_grid_idx] = (
            mh.grid.index
        )  # NOTE: add the grid index to the grid GeoDataFrame

    try:
        hotspot_dict = mh._hierarchical_routine(
            is_in_flows=is_in_flows,
            str_col_total_flows_grid=str_col_total_flows_grid_hierachical_routine,
            y_label=y_label,
            str_col_n_trips_flows=str_col_n_trips,
        )
    except Exception as e:
        print(f"Error in hierarchical routine: {e}")
        # Return empty/default values to prevent script crash
        hotspot_dict = {}
        hotspot_2_origin_idx_2_crit_dest_idx = {}
        map_flux = None
        return mh, map_flux, hotspot_2_origin_idx_2_crit_dest_idx, hotspot_dict

    print(f"Hotspot levels extracted: {hotspot_dict}")

    # Skip critical fluxes analysis if no hotspots found
    if not hotspot_dict or all(len(indices) == 0 for indices in hotspot_dict.values()):
        print("Warning: No hotspots found, skipping critical flux analysis")
        hotspot_2_origin_idx_2_crit_dest_idx = {}
        map_flux = None
        return mh, map_flux, hotspot_2_origin_idx_2_crit_dest_idx, hotspot_dict
    # NOTE: Analysis for the the critical fluxes
    # NOTE: Logically big: get_critical_fluxes_per_hotspot_level consider the flows that are outgoing if is in_fluxes.
    # if is_in_fluxes -> subhotspots in i: sum_j T_ij, get_critical_fluxes_per_hotspot_level -> consider the flows outgoing from i (i.e. T_ij) and puts them in order.
    # NOTE: Therefore that we are answering the question: for each polygon in the hotspot, what are the flows thatare contributing to it?
    # That is: total in flows
    hotspot_2_origin_idx_2_crit_dest_idx, list_indices_all_fluxes_for_colormap = (
        get_critical_fluxes_per_hotspot_level(
            mh.grid,
            mh.flows,
            str_col_total_flows_grid=str_col_total_flows_grid_hierachical_routine,
            hotspot_levels=hotspot_dict,
            is_in_flows=is_in_flows,
            str_hotspot_prefix=str_hotspot_prefix,
            str_col_origin=str_col_origin,
            str_col_destination=str_col_destination,
            str_col_n_trips=str_col_n_trips,
        )
    )
    #    print(f"Critical fluxes extracted: {hotspot_2_origin_idx_2_crit_dest_idx}")
    #    print(f"List of indices for colormap: {list_indices_all_fluxes_for_colormap}")
    return (
        mh,
        hotspot_2_origin_idx_2_crit_dest_idx,
        hotspot_dict,
        list_indices_all_fluxes_for_colormap,
    )
