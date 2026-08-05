"""
Overview:
    This script contains the functions to produce and visualize map_fluxes = map_fluxes_{user_profile}_t_{str_t}_{str_t1}_{suffix_in_out}.html
    visualize_critical_fluxes_with_lines that calls internally: 
        - draw_flux_line: draw a single flux line between two grid points
        - color_the_origin_destination_points: color the origin and destination points of the flux lines
        - get_colormap_from_df_fluxes_and_col: get a colormap based on the number of trips in the fluxes DataFrame

"""

from typing import Dict, List
import folium
import branca.colormap as cm
import geopandas as gpd
import polars as pl


def draw_flux_line(origin_idx: int,
                   destination_idx: int, 
                   level: int, 
                   n_trips: int,
                   grid_coords:Dict,
                   min_trips: int,
                   max_trips: int,
                   level_group: folium.FeatureGroup,
                   is_in_flows: bool,
                   grid_idx_2_grid_name: Dict[int, str],
                   colormap) -> tuple:
    """
    Helper function to draw a single flux line between two grid points
    
    Parameters:
    -----------
    origin_idx : int
        Origin grid index
    destination_idx : int
        Destination grid index
    level : int
        Hotspot level
    n_trips : int
        Number of trips for this flux
    """
#    print(f"Drawing flux line from {grid_idx_2_grid_name[origin_idx]} → {grid_idx_2_grid_name[destination_idx]} with {n_trips} trips at level {level}")
    # Get coordinates
    if origin_idx not in grid_coords or destination_idx not in grid_coords:
        print(f"Warning: Origin or destination index not found in grid_coords. Origin: {origin_idx}, Destination: {destination_idx}")
        return
    
    origin_coords = grid_coords[origin_idx]
    dest_coords = grid_coords[destination_idx]
    
    # Get color based on trip count
    line_color = colormap(n_trips) if n_trips > 0 else 'gray'
    
    # Calculate line properties based on trip intensity
    line_opacity = min(0.9, max(0.3, (n_trips - min_trips) / (max_trips - min_trips + 1)))
    line_weight = min(12, max(2, int((n_trips - min_trips) / (max_trips - min_trips + 1) * 6)))
    
    # Draw the flux line with tooltip
    folium.PolyLine(
        locations=[origin_coords, dest_coords],
        color=line_color,
        weight=line_weight,
        opacity=line_opacity,
        popup=folium.Popup(
            f"<b>Level {level} Critical Flux</b><br>"
            f"From: {grid_idx_2_grid_name[origin_idx]}<br>"
            f"To: {grid_idx_2_grid_name[destination_idx]}<br>"
            f"Trips: {n_trips}<br>"
            f"Direction: {'Incoming' if is_in_flows else 'Outgoing'}",
            max_width=250
        ),
        tooltip=f"From: {grid_idx_2_grid_name[origin_idx]} → To: {grid_idx_2_grid_name[destination_idx]}<br>Trips: {n_trips} <br>Direction: {'Incoming' if is_in_flows else 'Outgoing'}"
    ).add_to(level_group)
    
    return level_group

##### FUNCTIONS FOR COLORMAP COMPUTATION #####

def get_colormap_from_df_fluxes_and_col(filtered_flows,str_col_n_trips, caption = "Flow Intensity", colormap='YlOrRd'):
    """
        From a filtered DataFrame of flows, compute a colormap based on the number of trips.
    """
    assert str_col_n_trips in filtered_flows.columns, f"Column {str_col_n_trips} not found in DataFrame"
    colormap_obj = cm.linear.YlOrRd_09 if colormap == 'YlOrRd' else getattr(cm.linear, colormap, cm.linear.YlOrRd_09)        
    if len(filtered_flows) > 0:
        min_trips = filtered_flows[str_col_n_trips].min()
        max_trips = filtered_flows[str_col_n_trips].max()
        
        if min_trips == max_trips:
            # Handle case where all values are the same
            min_trips = min_trips - 1 if min_trips > 0 else 0
        
        colormap = cm.LinearColormap(
            colors=colormap_obj.colors,
            vmin=min_trips,
            vmax=max_trips,
            caption= caption
        )
    else:
        # Handle case where no flows are available - set default values
        min_trips = 0
        max_trips = 1
        colormap = cm.LinearColormap(
            colors=colormap_obj.colors,
            vmin=min_trips,
            vmax=max_trips,
            caption=caption
        )
    return colormap, min_trips, max_trips


def color_the_origin_destination_points(is_in_flows, is_hotspot, level, grid_idx_2_grid_name, idx_flow, idces_flow):
    """
        Hotspot are red and bigger.
        Contributing to hotspot are smaller and blue.
    """
    if is_hotspot:
        # Coloring the origin    
        if is_in_flows:
            color = "red"
            fill_color = "darkred"
            message_popup = f"<b>Hotspot di attrazione utenti</b><br>Nome: {grid_idx_2_grid_name[idx_flow]}<br>Livello: {level}<br># Regioni che contribuiscono: {len(idces_flow)}"
            # Hotspots are larger
            radius = 6

        else:
            # Destination is the hotspot since the flows are incoming therefore the incoming flows are going to the destination
            color = "red"
            fill_color = "darkred"
            message_popup = f"<b>Hotspot di generazione utenti</b><br>Livello: {level}<br>Nome: {grid_idx_2_grid_name[idx_flow]}<br># Regioni che contribuiscono: {len(idces_flow)}"
            radius = 6

    else:
        # Coloring the destination
        if is_in_flows:
#            assert idces_flow is not None, "idces_flow should not be None when coloring since we are coloring an origin contributing to in-flows, and not an hotspot"
            color = "blue"
            fill_color = "darkblue"            
            # We are considering the origin in the hotspot defined by total in-flows, therefore the origin is contributing to the in-flow of the hotspot that has been computed for destinations 
            message_popup = f"<b>Sorgente utenti</b><br>Livello: {level}<br>Nome: {grid_idx_2_grid_name[idx_flow]}<br>"
            # Contributing to hotspot are smaller and blue            
            radius = 4
        else:
#            assert idces_flow is None, "idces_flow should be None when coloring since we are coloring a destination contributing to out-flows, and not an hotspot"
            # Destination is contributing to the out-flows of the hotspot since the flows are outgoing
            color = "blue"
            fill_color = "darkblue"
            message_popup = f"<b>Destinazione utenti</b><br>Livello: {level}<br>Nome: {grid_idx_2_grid_name[idx_flow]}<br>"
            radius = 4
    return color,fill_color,message_popup,radius 



def visualize_critical_fluxes_with_lines(
    grid: gpd.GeoDataFrame,
    df_flows: pl.DataFrame,
    hotspot_2_origin_idx_2_crit_dest_idx: Dict[int, Dict[int, List[int]]],
    str_col_total_flows_grid: str,
    str_col_hotspot: str,
    str_col_n_trips: str,
    is_in_flows: bool,
    str_col_origin: str,
    str_col_destination: str,
    str_centroid_lat: str,
    str_centroid_lon: str,
    str_grid_idx: str = "grid_id",
    str_col_comuni_name: str = "city_name",
    str_caption_colormap: str = "Flow Intensity",
    str_colormap: str = "YlOrRd"
) -> folium.Map:
    """
    Visualizes critical fluxes as lines between grid centroids on a folium map.
        Input: 
        - grid: GeoDataFrame with grid information including centroids and total flows.
        - df_flows: DataFrame with flow information between grid cells.
        - hotspot_2_origin_idx_2_crit_dest_idx: Dict mapping hotspot levels to origin and critical destination indices.
        - str_col_total_flows_grid: Column name in grid for total flows.
        - str_col_hotspot: Column name in grid for hotspot levels.
        - str_col_n_trips: Column name in df_flows for number of trips.
        - str_col_origin: Column name in df_flows for origin grid index.
        - str_col_destination: Column name in df_flows for destination grid index.
        - str_centroid_lat: Column name in grid for centroid latitude.
        - str_centroid_lon: Column name in grid for centroid longitude.
        - str_grid_idx: Column name in grid for grid index.
        - str_col_comuni_name: Column name in grid for grid name.
        - str_caption_colormap: Caption for the colormap legend.
        - str_colormap: Colormap to use for flow intensity.
        - is_in_flows: Boolean indicating if the flows are incoming (True) or outgoing (False).
    Returns:
        - folium.Map object with visualized fluxes.
    Description:
        - The map contains different layers.
        - Each layer corresponds to different levels of criticality 0 = biggest,  last level = smallest.
        - The map plots the hotspots in red and the points that contribute to the hotspot in blue through the call of the function color_the_origin_destination_points.
        - The lines are drawn with the function draw_flux_line and are colored based on the number of trips using a colormap.
    """
    print(f"Generating interactive map with critical flux lines: n valid grid: {len(grid[str_col_total_flows_grid].notna())}, n valid flows: {len(df_flows.filter(pl.col(str_col_n_trips) > 0))}")
    str_caption_colormap = "Incoming Flow Intensity" if is_in_flows else "Outgoing Flow Intensity"
    # NOTE: Get all the elements of the grid that are going to be plotted: it is important in the draw fluxes function since otherwhise some elements would not be picked and level_group would be None
    list_idces_all_grids_to_plot = [idces_d + [idx_o] for _, idx_o_2_idces_d in hotspot_2_origin_idx_2_crit_dest_idx.items() for idx_o, idces_d in idx_o_2_idces_d.items() ]
    list_idces_all_grids_to_plot  = [item for sublist in list_idces_all_grids_to_plot for item in sublist]
    # Drop grids with no flows
    mask = grid[str_grid_idx].isin(list_idces_all_grids_to_plot)
    grid = grid[mask]
    filtered_flows = df_flows.filter(pl.col(str_col_origin).is_in(list_idces_all_grids_to_plot)) \
                           .filter(pl.col(str_col_destination).is_in(list_idces_all_grids_to_plot)) \
                           .filter(pl.col(str_col_n_trips) > 0)
    df_flows = filtered_flows
    hotspot_levels = [int(level) for level in list(grid[str_col_hotspot].unique())]

    print(f" - Hotspot levels found in grid: {hotspot_levels}")
    print(f" - n grid after dropping NaN total flows: {len(grid)}, n flows after dropping zero trips: {len(df_flows)}")

    # Init Map
    center_lat = grid[str_centroid_lat].mean()
    center_lon = grid[str_centroid_lon].mean()
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles="cartodbpositron")

    grid_idx_2_grid_name = dict(zip(grid[str_grid_idx], grid[str_col_comuni_name]))

    # Colormap
    print(f" - n filtered flows for colormap: {len(filtered_flows)}")
    colormap, min_trips, max_trips = get_colormap_from_df_fluxes_and_col(
        filtered_flows, str_col_n_trips, caption=str_caption_colormap, colormap=str_colormap
    )
    print(f" - Colormap range: min_trips={min_trips}, max_trips={max_trips}")

    # Base grid
    folium.GeoJson(
        grid,
        name="Grid",
        style_function=lambda feature: {
            "fillColor": "lightgray",
            "color": "gray",
            "weight": 1,
            "fillOpacity": 0.2,
            "opacity": 0.5,
        },
    ).add_to(fmap)

    # Grid coordinates
    grid_coords = {row[str_grid_idx]: [row[str_centroid_lat], row[str_centroid_lon]] for _, row in grid.iterrows()}

    # --- Draw fluxes ---
    for level in hotspot_levels:
        if level != -1:
            level_group = folium.FeatureGroup(name=f"Livello flussi: {level}")
            origin_idx_2_crit_dest_idx = hotspot_2_origin_idx_2_crit_dest_idx[level]

            if is_in_flows:
                # Hotspot is destination
                for idx_destination_flow, idces_origin_flows in origin_idx_2_crit_dest_idx.items():
                    # Mark hotspot (destination)
                    if idx_destination_flow in grid_coords:
                        dest_coords = grid_coords[idx_destination_flow]
                        color, fill_color, message_popup, radius = color_the_origin_destination_points(
                            is_in_flows=True,
                            is_hotspot=True,
                            level=level,
                            grid_idx_2_grid_name=grid_idx_2_grid_name,
                            idx_flow=idx_destination_flow,      # ✅ fixed
                            idces_flow=idces_origin_flows,      # ✅ fixed
                        )
#                        print(f"Marking destination (hotspot) {grid_idx_2_grid_name[idx_destination_flow]} with color {color} and radius {radius}")
                        folium.CircleMarker(
                                    location = dest_coords,
                                    radius = radius,
                                    color = color,
                                    fillColor= fill_color,
                                    fillOpacity=0.8,
                                    popup=folium.Popup(message_popup)
                                ).add_to(level_group)

                    # Draw each origin -> destination
                    for idx_origin_flow in idces_origin_flows:
                        if idx_origin_flow in grid_coords:
                            origin_coords = grid_coords[idx_origin_flow]
                            # NOTE: I am filtering the origin as origin
                            flow_data = df_flows.filter(
                                (pl.col(str_col_origin) == idx_origin_flow)
                                & (pl.col(str_col_destination) == idx_destination_flow)
                            )
                            if len(flow_data) > 0:
                                n_trips = flow_data[str_col_n_trips].item()
                                level_group = draw_flux_line(
                                    origin_idx=idx_origin_flow,
                                    destination_idx=idx_destination_flow,
                                    level=level,
                                    n_trips=n_trips,
                                    grid_coords=grid_coords,
                                    min_trips=min_trips,
                                    max_trips=max_trips,
                                    level_group=level_group,
                                    is_in_flows=True,
                                    grid_idx_2_grid_name=grid_idx_2_grid_name,
                                    colormap=colormap,
                                )
                                # Mark origin
                                if idx_origin_flow in grid_coords:
                                    origin_coords = grid_coords[idx_origin_flow]
                                    color, fill_color, message_popup, radius = color_the_origin_destination_points(
                                        is_in_flows=True,
                                        is_hotspot=False,
                                        level=level,
                                        grid_idx_2_grid_name=grid_idx_2_grid_name,
                                        idx_flow=idx_origin_flow,
                                        idces_flow=idces_origin_flows,
                                    )
#                                    print(f"Marking origin {grid_idx_2_grid_name[idx_origin_flow]} with color {color} and radius {radius}")
                                    folium.CircleMarker(
                                                location = origin_coords,
                                                radius = radius,
                                                color = color,
                                                fillColor= fill_color,
                                                fillOpacity=0.8,
                                                popup=folium.Popup(message_popup)
                                            ).add_to(level_group)

            else:
                # Hotspot is origin
                for idx_origin_flow, idces_destination_flows in origin_idx_2_crit_dest_idx.items():
                    # Mark hotspot (origin)
                    if idx_origin_flow in grid_coords:
                        origin_coords = grid_coords[idx_origin_flow]
                        color, fill_color, message_popup, radius = color_the_origin_destination_points(
                            is_in_flows=False,
                            is_hotspot=True,
                            level=level,
                            grid_idx_2_grid_name=grid_idx_2_grid_name,
                            idx_flow=idx_origin_flow,
                            idces_flow=idces_destination_flows,
                        )
#                        print(f"Marking hotspot origin {grid_idx_2_grid_name[idx_origin_flow]} with color {color} and radius {radius}")
                        folium.CircleMarker(
                                    location = origin_coords,
                                    radius = radius,
                                    color = color,
                                    fillColor= fill_color,
                                    fillOpacity=0.8,
                                    popup=folium.Popup(message_popup)
                                ).add_to(level_group)

                    # Draw each origin -> destination
                    for idx_dest_flux in idces_destination_flows:
                        if idx_dest_flux in grid_coords:
                            # NOTE: I am filtering the destination as destination
                            dest_coords = grid_coords[idx_dest_flux]
                            flow_data = df_flows.filter(
                                (pl.col(str_col_origin) == idx_origin_flow)
                                & (pl.col(str_col_destination) == idx_dest_flux)
                            )
                            if len(flow_data) > 0:
                                n_trips = flow_data[str_col_n_trips].item()
                                level_group = draw_flux_line(
                                    origin_idx=idx_origin_flow,
                                    destination_idx=idx_dest_flux,
                                    level=level,
                                    n_trips=n_trips,
                                    grid_coords=grid_coords,
                                    min_trips=min_trips,
                                    max_trips=max_trips,
                                    level_group=level_group,
                                    is_in_flows=False,
                                    grid_idx_2_grid_name=grid_idx_2_grid_name,
                                    colormap=colormap,
                                )

                                # Mark destination
                                if idx_dest_flux in grid_coords:
                                    dest_coords = grid_coords[idx_dest_flux]
                                    color, fill_color, message_popup, radius = color_the_origin_destination_points(
                                        is_in_flows=False,
                                        is_hotspot=False,
                                        level=level,
                                        grid_idx_2_grid_name=grid_idx_2_grid_name,
                                        idx_flow=idx_dest_flux,
                                        idces_flow=idces_destination_flows,
                                    )
#                                    print(f"Marking destination {grid_idx_2_grid_name[idx_dest_flux]} with color {color} and radius {radius}")
                                    folium.CircleMarker(
                                                location = dest_coords,
                                                radius = radius,
                                                color = color,
                                                fillColor= fill_color,
                                                fillOpacity=0.8,
                                                popup=folium.Popup(message_popup)
                                            ).add_to(level_group)


            level_group.add_to(fmap)

    # Add legend and controls
    colormap.add_to(fmap)
    folium.LayerControl().add_to(fmap)

    return fmap
