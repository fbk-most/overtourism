from typing import Dict, List
import numpy as np
import geopandas as gpd
import polars as pl

from collections import defaultdict

@staticmethod
def get_lorenz_curve(flows: np.ndarray):
    """
        Takes the total flows measured for a single geometry and computes the Lorenz curve.
        @returns:
            x (np.ndarray): The x-coordinates of the Lorenz curve (cumulative share of population). [0, 1]
            y (np.ndarray): The y-coordinates of the Lorenz curve (cumulative share of flows). [0, 1]
            sorted_indices (np.ndarray): The indices that would sort the flows array.
    """
    sorted_indices = np.argsort(flows)
    # Step 2: Compute the cumulative distribution
    sorted_flows = flows[sorted_indices]
    x = np.linspace(0, 1, len(flows))
    
    # Handle case where sum of flows is zero or very small
    total_flows = np.sum(sorted_flows)
    if total_flows == 0 or not np.isfinite(total_flows):
        print("Warning: Total flows is zero or invalid!")
        y = np.zeros_like(x)  # All zeros if no flows
    else:
        y = np.cumsum(sorted_flows) / total_flows
    
    return x, y, sorted_indices
    

@staticmethod
def get_loubar_threshold(remaining_grid, str_col_total_flows_grid: str) -> tuple:
    """
        Computes the list of actual DataFrame indices that correspond to the ones that are categorized
        as hotspots based on the Loubar threshold.
    Parameters:
        remaining_grid: The remaining grid with actual indices (pandas or polars DataFrame)
        str_col_total_flows_grid (str): Column name for flows
    
    Returns:
        tuple: (chosen_actual_indices, Fstar, angle)
    """
    # Handle both pandas and polars DataFrames
    if hasattr(remaining_grid, 'to_pandas'):  # Polars DataFrame
        flows = remaining_grid[str_col_total_flows_grid].to_numpy()
        # For polars, we need to get the index differently
        actual_indices = np.arange(len(remaining_grid))  # or use remaining_grid.get_column_index() if you have a specific index column
    else:  # Pandas DataFrame/GeoDataFrame
        flows = remaining_grid[str_col_total_flows_grid].to_numpy()
        actual_indices = remaining_grid.index.to_numpy()

    # Early return if no data
    if len(flows) == 0:
        print("Warning: No flows data provided!")
        return [], 0, 0

    # Filter out NaN, infinite, and negative values
    valid_mask = np.isfinite(flows) & (flows >= 0)
    if not np.any(valid_mask):
        print("Warning: All flow values are NaN, infinite, or negative!")
        return [], 0, 0
    
    flows_clean = flows[valid_mask]
    actual_indices_clean = actual_indices[valid_mask]
    
    if len(flows_clean) == 0:
        print("Warning: No valid flow values after filtering!")
        return [], 0, 0
    
    # Check if all flows are zero
    if np.sum(flows_clean) == 0:
        print("Warning: All flow values are zero!")
        return [], 0, 0


    x, y, sorted_flow_indices = get_lorenz_curve(flows_clean)
    
    # NOTE: Compute fraction of total outflow
    if len(y) < 2:
        return [], 0, 0
    
    # Check for NaN or infinite values in y
    if not np.isfinite(y[-1]) or not np.isfinite(y[-2]):
        print("Warning: NaN or infinite values in Lorenz curve!")
        return [], 0, 0
        
    angle = y[-1] - y[-2]
    
    # Handle edge cases for angle
    if angle == 0 or not np.isfinite(angle):
        return [], len(y), angle
    
    # Calculate Fstar with safety checks
    fstar_raw = y[-1] / angle
    if not np.isfinite(fstar_raw):
        print("Warning: Invalid Fstar calculation!")
        return [], len(y), angle
        
    Fstar = int(len(y) + 1 - fstar_raw)
    
    # Ensure Fstar is within valid bounds
    Fstar = max(0, min(Fstar, len(y)))
    
    # Ensure we don't go out of bounds
    num_to_select = min(len(y) - Fstar, len(sorted_flow_indices))
    if num_to_select <= 0:
        return [], Fstar, angle
    
    # Map the flow array indices back to actual DataFrame indices
    chosen_flow_indices = [int(sorted_flow_indices[-i-1]) for i in range(num_to_select)]
    chosen_actual_indices = [actual_indices_clean[idx] for idx in chosen_flow_indices]
    
    return chosen_actual_indices, Fstar, angle


def extract_hotspot_levels(grid,
                        str_col_total_flows_grid,
                        max_levels: int = 5,
                        ) -> Dict[int, List[int]]:
    """
        Extracts hotspot levels based on the Loubar threshold from the outflows.
        Parameters:
        max_levels (int): Maximum number of levels to extract.
        
    """
    if isinstance(grid, pl.DataFrame):
        # Convert Polars DataFrame to Pandas DataFrame for compatibility
        grid = grid.to_pandas()
    else:
        pass
    
    # Check if the column exists and has valid data
    if str_col_total_flows_grid not in grid.columns:
        print(f"Warning: Column {str_col_total_flows_grid} not found in grid!")
        return {}
    
    # Check if there's any non-zero data
    flows_data = grid[str_col_total_flows_grid].to_numpy()
    if len(flows_data) == 0 or np.sum(np.isfinite(flows_data)) == 0 or np.sum(flows_data) == 0:
        print(f"Warning: No valid flow data in column {str_col_total_flows_grid}!")
        return {}
    
    levels = {}
    remaining = grid.copy()
    level = 0
    while(len(remaining)> 0 and len(levels) < max_levels):
        try:
            selected_idces, _, _ = get_loubar_threshold(remaining,str_col_total_flows_grid)
        except Exception as e:
            print(f"Error in get_loubar_threshold for level {level}: {e}")
            break
            
        if len(selected_idces) == 0:
            break
        print(f"Level {level}: {len(selected_idces)} hotspots found.")
        selected_idces = [int(x) for x in selected_idces]  # Ensure indices are integers
        levels[level] = selected_idces
        # Correct way to filter out indices
        remaining = remaining.loc[~remaining.index.isin(selected_idces)]
        level += 1
    return levels


def get_critical_fluxes_per_hotspot_level(
    grid: gpd.GeoDataFrame,
    df_flows: pl.DataFrame,
    str_col_total_flows_grid: str,
    hotspot_levels: Dict[int, List[int]],
    is_in_flows: bool = True,
    str_hotspot_prefix: str = "hotspot_level",
    str_col_origin: str = "i",
    str_col_destination: str = "j",
    str_col_n_trips: str = "n_trips"    

) -> Dict[int, float]:
    """
        @param grid: The grid containing the geometries and their indices.
        @param df_flows: The DataFrame containing the flows. (i,j columns contain values of the indices of the grid)
        @param str_col_total_flows_grid: The column name in the grid geoDataFrame that contains the total flows.
        @param hotspot_levels: A dictionary where keys are levels and values are lists of indices corresponding to hotspots.
        @param is_in_flows: Boolean indicating if the flows are incoming (True) or outgoing (False).
        @param str_col_origin: The column name in df_flows that contains the origin indices.
        @param str_col_destination: The column name in df_flows that contains the destination indices.
        @param str_col_n_trips: The column name in df_flows that contains the number of trips.

        @description:
            - according of wether I am looking at incoming or outgoing flows, I will:
            - if is_in_flows is True:
                - pick the rows of the flows that have as destination that index (that is the col of OD matrix)
                - select the flows whose origin generated the fluxes to the 


        @returns:
            A dictionary where keys are origin indices and values are lists of critical destination indices.
            {hotspot_level: {origin_index: [critical_destination_indices]}}
    """
    # NOTE: The column of the hotspot in the grid. -> it must be the same as the one defined in the Mobility_Hierarchy class
    str_hotspot_level_grid = f'{str_hotspot_prefix}_{str_col_total_flows_grid}'
    assert str_hotspot_level_grid in grid.columns, f"Column {str_col_total_flows_grid} not found in grid, look at the definition of the Mobility_Hierarchy class."
    hotspot_2_origin_idx_2_crit_dest_idx = defaultdict()
    list_indices_all_fluxes_for_colormap = []
    # NOTE: Iterating over the indices of each level given it is in-out total flows
    for level, indices in hotspot_levels.items():
        # NOTE: for each level prepare the dictionary that will hold the information O:[Ds] (if is_in_flows) or D:[Os] (if not is_in_flows)
        hotspot_2_origin_idx_2_crit_dest_idx[level] = defaultdict(list)
        # TODO: for each index: that is, considering the hotspot index for the case in/out flows 
        for idx in indices:
            if is_in_flows:
                # NOTE: filter the flows that have destination in the hotspot index: -> I am loking at the critical fluxes that give the incoming flows to the hotspot i
                selected_flows = df_flows.filter(pl.col(str_col_destination) == int(idx))                                                       # NOTE: choosing the flows that end in the hotspot chosen from in-fluxes
                # NOTE: apply the Loubar method to extract the critical flows (obtain the indices of the places that contribut most to the incoming flows to the hotspot idx)
                ordered_local_indices_in_selected_flows , _, _ = get_loubar_threshold(selected_flows, str_col_n_trips)
                if isinstance(selected_flows, pl.DataFrame):
                    selected_flows = selected_flows.to_pandas()
                # Cast the indices to int since they can become np.int64
                grid_idces =  [int(x) for x in selected_flows.loc[ordered_local_indices_in_selected_flows, str_col_origin].to_numpy()]

                if len(hotspot_2_origin_idx_2_crit_dest_idx[level][int(idx)]) == 0:
                    hotspot_2_origin_idx_2_crit_dest_idx[level][int(idx)] = list(grid_idces)
                    list_indices_all_fluxes_for_colormap.append(grid_idces)
                else:
                    
                    hotspot_2_origin_idx_2_crit_dest_idx[level][int(idx)].extend(grid_idces)
                    list_indices_all_fluxes_for_colormap.extend(grid_idces)
            # NOTE: case critical index out flows
            else:
                # NOTE: filter the flows that have origin in the hotspot index: -> I am loking at the critical fluxes that give the outgoing flows
                selected_flows = df_flows.filter(pl.col(str_col_origin) == int(idx))
                # NOTE: apply the Loubar method to extract the critical flows
                ordered_local_indices_in_selected_flows, _, _ = get_loubar_threshold(selected_flows, str_col_n_trips)
                if isinstance(selected_flows, pl.DataFrame):
                    selected_flows = selected_flows.to_pandas()
                # NOTE: get the destination indices of the critical flows (these are the outgoing flows that create problem)
                grid_idces = [int(x) for x in selected_flows.loc[ordered_local_indices_in_selected_flows, str_col_destination].to_numpy()]
                # NOTE: Choose the critical destination indices based on the flows
                if len(hotspot_2_origin_idx_2_crit_dest_idx[level][int(idx)]) == 0:
                    hotspot_2_origin_idx_2_crit_dest_idx[level][int(idx)] = list(grid_idces)
                    list_indices_all_fluxes_for_colormap.append(grid_idces)
                else:
                    
                    hotspot_2_origin_idx_2_crit_dest_idx[level][int(idx)].extend(grid_idces)
                    list_indices_all_fluxes_for_colormap.extend(grid_idces)

    return hotspot_2_origin_idx_2_crit_dest_idx,list_indices_all_fluxes_for_colormap



