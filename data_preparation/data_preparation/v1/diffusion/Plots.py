import contextily as ctx
#
import branca.colormap as cm
import folium
from folium.plugins import MarkerCluster


# 
import geopandas as gpd
# 
import matplotlib.pyplot as plt
from matplotlib_scalebar.scalebar import ScaleBar
from matplotlib.colors import Normalize
from mpl_toolkits.axes_grid1.anchored_artists import AnchoredSizeBar
import matplotlib.font_manager as fm
#
import numpy as np
# 
from shapely.geometry import Point

#
from data_preparation.diffusion.OD import *

# Utility functions for memory management
import gc
import logging
logger = logging.getLogger(__name__)

def safe_close_figures():
    """Safely close all matplotlib figures to prevent memory leaks."""
    try:
        plt.close('all')
    except Exception as e:
        logger.warning(f"Error closing matplotlib figures: {e}")

# Helper function for matplotlib memory management
def safe_figure_context(func):
    """Decorator to ensure matplotlib figures are properly closed"""
    def wrapper(*args, **kwargs):
        import matplotlib.pyplot as plt
        initial_figs = len(plt.get_fignums())
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            # Close any figures created during function execution
            current_figs = plt.get_fignums()
            for fig_num in current_figs:
                if fig_num not in plt.get_fignums()[:initial_figs]:
                    plt.close(fig_num)
            gc.collect()
    return wrapper


#### ---------------- DEBUG GEOMETRIES ------------------ ####

def folium_visualize_stops_and_roads(gdf_stops,
                             gdf_public_transport,
                             str_stop_idx,
                             buffer_distance,
                             is_dynamical_plot=True, 
                             figsize=(15, 15),
                             zoom_start=13,
                             crs = "EPSG:3857"):
    """
    Visualize bus stops and road network, highlighting associated and non-associated stops.
    
    Parameters:
        gdf_stops: GeoDataFrame with stop locations
        gdf_public_transport: GeoDataFrame with road network
        str_stop_idx: Column name for the stop ID
        buffer_distance: Maximum distance used in spatial join
        is_dynamical_plot: If True, creates an interactive Folium map, else a static plot
        figsize: Figure size for static plot
        zoom_start: Initial zoom level for Folium map
        
    Returns:
        fig, ax for static plot or folium.Map for dynamic plot
    """    
    # Ensure all data is in the same CRS
    common_crs = crs
    gdf_public_transport = gdf_public_transport.to_crs(common_crs)
    
    # Get the list of associated stop IDs
    associated_stop_ids = gdf_public_transport.loc[
        gdf_public_transport["distance"] <= buffer_distance
    ][str_stop_idx].unique().tolist()
    
    # Create masks for associated and non-associated stops
    associated_mask = gdf_stops[str_stop_idx].isin(associated_stop_ids)
    associated_stops = gdf_stops[associated_mask].copy()
    non_associated_stops = gdf_stops[~associated_mask].copy()
    
    print(f"Total stops: {len(gdf_stops)}")
    print(f"Associated stops: {len(associated_stops)}")
    print(f"Non-associated stops: {len(non_associated_stops)}")
    
    if is_dynamical_plot:
        # Convert to WGS84 for Folium map
        if common_crs != "EPSG:4326":
            gdf_stops = gdf_stops.to_crs("EPSG:4326")
            gdf_public_transport = gdf_public_transport.to_crs("EPSG:4326")
            associated_stops = associated_stops.to_crs("EPSG:4326")
            non_associated_stops = non_associated_stops.to_crs("EPSG:4326")
        
        # Determine map center (mean of all stops)
        center_lat = gdf_stops.geometry.centroid.y.mean()
        center_lon = gdf_stops.geometry.centroid.x.mean()
        
        # Create Folium map
        m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start,
                       tiles='cartodbpositron')
        
        # Add the road network
        for idx, row in gdf_public_transport.iterrows():
            # Extract coordinates from the LineString
            if row.geometry.geom_type == 'LineString':
                coords = [(y, x) for x, y in row.geometry.coords]
                folium.PolyLine(
                    coords,
                    color='blue',
                    weight=2.5,
                    opacity=0.7,
                    tooltip=f"Road ID: {idx}"
                ).add_to(m)
        
        # Create clusters for associated and non-associated stops
        associated_cluster = MarkerCluster(name="Associated Stops").add_to(m)
        non_associated_cluster = MarkerCluster(name="Non-Associated Stops").add_to(m)
        
        # Add associated stops
        for idx, row in associated_stops.iterrows():
            coords = (row.geometry.y, row.geometry.x)
            folium.CircleMarker(
                location=coords,
                radius=5,
                color='green',
                fill=True,
                fill_color='green',
                fill_opacity=0.7,
                tooltip=f"Stop ID: {row[str_stop_idx]}"
            ).add_to(associated_cluster)
        
        # Add non-associated stops
        for idx, row in non_associated_stops.iterrows():
            coords = (row.geometry.y, row.geometry.x)
            folium.CircleMarker(
                location=coords,
                radius=5,
                color='red',
                fill=True,
                fill_color='red',
                fill_opacity=0.7,
                tooltip=f"Stop ID: {row[str_stop_idx]}"
            ).add_to(non_associated_cluster)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        return m
    
    else:  # Static plot
        # Create figure and axis
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot road network
        gdf_public_transport.plot(ax=ax, color='blue', linewidth=0.5, alpha=0.7, label='Roads')
        
        # Plot associated stops
        if len(associated_stops) > 0:
            associated_stops.plot(
                ax=ax, color='green', markersize=50, alpha=0.7, label='Associated Stops'
            )
            
        # Plot non-associated stops
        if len(non_associated_stops) > 0:
            non_associated_stops.plot(
                ax=ax, color='red', markersize=50, alpha=0.7, label='Non-Associated Stops'
            )
        
        # Add basemap
        try:
            ctx.add_basemap(ax, crs=common_crs, source=ctx.providers.CartoDB.Positron)
        except Exception as e:
            print(f"Warning: Could not add basemap: {e}")
        
        # Finalize plot
        ax.set_title(f'Bus Stops and Road Network (Buffer: {buffer_distance}m)')
        ax.legend(loc='upper left')
        plt.tight_layout()
        
        return fig, ax



def folium_plot_two_geodataframe(gdf1, gdf2, center, name1="Layer 1", name2="Layer 2",
                          color1='blue', color2='red', 
                          zoom_start=12, tile='cartodbpositron',
                          complete_path_map=None):
    """
        Create an interactive folium map with two GeoDataFrames.
        Parameters:
        gdf1: First GeoDataFrame to plot.
        gdf2: Second GeoDataFrame to plot.
        center: Center coordinates for the map [lat, lon].
        name1: Name for the first layer.
        name2: Name for the second layer.
        color1: Color for the first layer.
        color2: Color for the second layer.
        zoom_start: Initial zoom level for the map.
        tile: Tile type for the map (e.g., 'cartodbpositron', 'Stamen Terrain').
        Returns:
            folium.Map object with the two layers added. It generates the map and displays two different layers of geometries.
            It can be used to display the transportation network 
        NOTE: Usage to check if the transportation ne
    """
    assert center is not None, "Center coordinates must be provided."
    assert isinstance(center, (list, tuple)) and len(center) == 2, "Center must be a list or tuple with two elements [lat, lon]."
    assert isinstance(gdf1, gpd.GeoDataFrame), "gdf1 must be a GeoDataFrame."
    assert isinstance(gdf2, gpd.GeoDataFrame), "gdf2 must be a GeoDataFrame."
    # Ensure both are in WGS84 for folium
    if gdf1.crs != "EPSG:4326":
        gdf1 = gdf1.to_crs("EPSG:4326")
    if gdf2.crs != "EPSG:4326":
        gdf2 = gdf2.to_crs("EPSG:4326")
        
    # Create map
    m = folium.Map(location=center, zoom_start=zoom_start, tiles=tile)
    
    # Add first layer based on geometry type
    if 'Point' in gdf1.geometry.iloc[0].geom_type:
        # For points, use circle markers
        for idx, row in gdf1.iterrows():
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=5,
                color=color1,
                fill=True,
                fill_opacity=0.7,
                tooltip=f"{name1}: {idx}"
            ).add_to(m)
    else:
        # For polygons or lines
        folium.GeoJson(
            gdf1,
            name=name1,
            style_function=lambda x: {
                'color': color1,
                'fillColor': color1,
                'weight': 1.5,
                'fillOpacity': 0.5
            },
            tooltip=folium.GeoJsonTooltip(fields=gdf1.columns[:3].tolist())
        ).add_to(m)
    
    # Add second layer based on geometry type
    if 'Point' in gdf2.geometry.iloc[0].geom_type:
        for idx, row in gdf2.iterrows():
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=5,
                color=color2,
                fill=True,
                fill_opacity=0.7,
                tooltip=f"{name2}: {idx}"
            ).add_to(m)
    else:
        folium.GeoJson(
            gdf2,
            name=name2,
            style_function=lambda x: {
                'color': color2,
                'fillColor': color2,
                'weight': 1.5,
                'fillOpacity': 0.5
            },
            tooltip=folium.GeoJsonTooltip(fields=gdf2.columns[:3].tolist())
        ).add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    if complete_path_map is not None:
        m.save(complete_path_map)                                                                                                               # save the map in the output folder
    
    return m


    

# ----------------------------- ORIGIN DESTINATION ----------------------------- #
def compute_normalized_colormap(selected_fluxes, str_flux_col,str_normalized_colormap = 'normalized_flux'):
    """
        @params selected_fluxes: DataFrame 
        @params str_flux_col: str
            The name of the column containing the flux values
        @params str_normalized_colormap: str
        It adds the column of the normalized values of the dataframe that I want to use for fluxes pourposes
    """
    assert str_flux_col in selected_fluxes.columns, f"Column {str_flux_col} not found in DataFrame"
    max_flux = selected_fluxes[str_flux_col].max()
    min_flux = selected_fluxes[str_flux_col].min()
    
    # Avoid division by zero
    if max_flux == min_flux:
        selected_fluxes[str_normalized_colormap] = 1
    else:
        selected_fluxes[str_normalized_colormap] = (selected_fluxes[str_flux_col] - min_flux) / (max_flux - min_flux)
    return selected_fluxes, max_flux,min_flux



def visualize_selected_fluxes(
    gdf_polygons, 
    df_fluxes, 
    str_grid_idx="grid_idx",
    str_origin_col="origin",
    str_destination_col="destination",
    str_flux_col="flux",
    crs_proj="EPSG:3857",
    title = "",
    figsize=(15, 15),
    cmap="viridis",
    arrow_scale=1.0,
    width_scale=0.5,
    min_width=0.5,
    base_map=True,
    save_path=None

):
    """
    Visualize selected fluxes between polygon centroids.
    
    Parameters:
    -----------
    gdf_polygons : GeoDataFrame
        GeoDataFrame containing polygons with geometry column
    df_fluxes : DataFrame
        DataFrame containing origin-destination pairs and flux values
    origin_indices : list
        List of origin indices to include
    destination_indices : list
        List of destination indices to include
    str_grid_idx : str, default="grid_idx"
        Name of the column in gdf_polygons containing grid indices
    str_origin_col : str, default="origin"
        Name of the column in df_fluxes containing origin indices
    str_destination_col : str, default="destination"
        Name of the column in df_fluxes containing destination indices
    str_flux_col : str, default="flux"
        Name of the column in df_fluxes containing flux values
    figsize : tuple, default=(15, 15)
        Figure size
    cmap : str, default="viridis"
        Colormap for arrows
    arrow_scale : float, default=1.0
        Scaling factor for arrow size
    width_scale : float, default=0.5
        Scaling factor for arrow width
    min_width : float, default=0.5
        Minimum width of arrows
    base_map : bool, default=True
        Whether to add a basemap from contextily
    save_path : str, default=None
        Path to save the figure, if None, figure is not saved
        
    Returns:
    --------
    fig, ax : matplotlib figure and axes objects
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from shapely.geometry import LineString
    from matplotlib import colormaps
    from matplotlib.patches import FancyArrowPatch
    import contextily as ctx
    
    # Calculate centroids for polygons
    gdf_centroids = gdf_polygons.copy()
    if gdf_polygons.crs.to_string() != crs_proj:
        gdf_polygons = gdf_polygons.to_crs(crs_proj)

    gdf_centroids['centroid'] = gdf_polygons.geometry.centroid
    gdf_centroids = gdf_centroids.set_geometry('centroid')
    # Create a dictionary mapping grid indices to centroid coordinates
    centroids_dict = {}
    for idx, row in gdf_centroids.iterrows():
        centroids_dict[row[str_grid_idx]] = (row['centroid'].x, row['centroid'].y)
    

    # Normalize flux values for width and color
    selected_fluxes,max_flux,min_flux = compute_normalized_colormap(df_fluxes, str_flux_col,str_normalized_colormap = 'normalized_flux')
    if len(selected_fluxes) == 0:
        print("No fluxes match the selected origin and destination indices.")
        return None
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot polygons
    gdf_polygons.plot(ax=ax, color='lightgray', edgecolor='darkgray', alpha=0.1)
    colormap = colormaps[cmap]
    # Plot arrows for fluxes
    count_points = 0
    for _, row in selected_fluxes.iterrows():
        origin_idx = row[str_origin_col]
        dest_idx = row[str_destination_col]
        
        # Skip if either origin or destination is not in the centroids dictionary
        if origin_idx not in centroids_dict or dest_idx not in centroids_dict:
            continue
            
        origin_point = centroids_dict[origin_idx]
        dest_point = centroids_dict[dest_idx]
        # Calculate arrow properties based on flux
        flux = row[str_flux_col]
        normalized_flux = row['normalized_flux']
        width = max(min_width, normalized_flux * width_scale)
        # Draw arrow
        # Create a FancyArrowPatch
        arrow = FancyArrowPatch(
            posA=origin_point,
            posB=dest_point,
            arrowstyle=f'simple,head_width={width*3*arrow_scale},head_length={width*5*arrow_scale}',
            color=colormap(normalized_flux),
            linewidth=width,
            alpha=0.7,
            zorder=10
        )
        ax.add_patch(arrow)    
        if count_points == 0:
            origin_label = "origin"
            dest_label = "destination"
            count_points += 1
        else:
            origin_label = ""
            dest_label = ""
        ax.scatter(
            origin_point[0], 
            origin_point[1],
            color='red', s=50, zorder=11, label=origin_label)

    
        ax.scatter(
            dest_point[0], 
            dest_point[1],
            color='blue', s=50, zorder=11, label=dest_label)
    
    # Add basemap if requested
    if base_map:
        # Convert to Web Mercator projection for contextily
        if gdf_polygons.crs.to_string() != 'EPSG:3857':
            gdf_plot = gdf_polygons.to_crs(epsg=3857)
            ctx.add_basemap(ax, crs=gdf_polygons.crs.to_string())
        else:
            ctx.add_basemap(ax)
    
    # Add colorbar
    sm = plt.cm.ScalarMappable(cmap=colormap, norm=plt.Normalize(vmin=min_flux, vmax=max_flux))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax)
    cbar.set_label(f'{str_flux_col}')
    
    # Add legend for origin and destination points
    ax.legend()
    
    # Set title and labels
    plt.title(title, fontsize=14)
    plt.xlabel('X Coordinate')
    plt.ylabel('Y Coordinate')
    
    # Add a text box with statistics
    stats_text = (
        f"Number of fluxes: {len(selected_fluxes)}\n"
        f"Max flux: {max_flux:.2f}\n"
        f"Min flux: {min_flux:.2f}\n"
        f"Total flux: {selected_fluxes[str_flux_col].sum():.2f}"
    )
    plt.annotate(
        stats_text, 
        xy=(0.05, 0.05), 
        xycoords='axes fraction',
        bbox=dict(boxstyle="round,pad=0.5", fc="white", alpha=0.8)
    )
    try:
        plt.tight_layout()
    except ValueError:
        # If tight_layout fails, adjust figure size and try again
        fig.set_size_inches(figsize[0]*1.1, figsize[1]*1.1)
        try:
            plt.tight_layout()
        except ValueError:
            pass  # If it still doesn't work, just continue    
    # Save figure if path is provided
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    return fig, ax

def interactive_visualize_selected_fluxes(
    gdf_polygons,
    df_fluxes,
    origin_indices,
    destination_indices,
    str_grid_idx="grid_idx",
    str_origin_col="origin",
    str_destination_col="destination",
    str_flux_col="flux",
    save_path=None
):
    """
    Create an interactive map visualization of selected fluxes.
    
    Parameters:
    -----------
    gdf_polygons : GeoDataFrame
        GeoDataFrame containing polygons with geometry column (must be in EPSG:4326)
    df_fluxes : DataFrame
        DataFrame containing origin-destination pairs and flux values
    origin_indices : list
        List of origin indices to include
    destination_indices : list
        List of destination indices to include
    str_grid_idx : str, default="grid_idx"
        Name of the column in gdf_polygons containing grid indices
    str_origin_col : str, default="origin"
        Name of the column in df_fluxes containing origin indices
    str_destination_col : str, default="destination"
        Name of the column in df_fluxes containing destination indices
    str_flux_col : str, default="flux"
        Name of the column in df_fluxes containing flux values
    save_path : str, default=None
        Path to save the HTML map, if None, map is not saved
        
    Returns:
    --------
    folium.Map : Interactive folium map
    """
    import folium
    import numpy as np
    from branca.colormap import linear
    import pandas as pd
    import geopandas as gpd
    
    # Ensure GeoDataFrame is in EPSG:4326 (required for folium)
    if gdf_polygons.crs.to_string() != 'EPSG:4326':
        gdf_polygons = gdf_polygons.to_crs(epsg=4326)
    
    # Calculate centroids for polygons (as separate lat/lon coordinates, not Point objects)
    centroids_dict = {}
    for idx, row in gdf_polygons.iterrows():
        # Check if the row's geometry is None or empty
        if row.geometry is not None and not row.geometry.is_empty:
            # Extract centroid coordinates
            centroid = row.geometry.centroid
            centroids_dict[row[str_grid_idx]] = (centroid.y, centroid.x)  # Folium uses lat, lon order
    
        
    # Normalize flux values for width and color
    selected_fluxes, max_flux, min_flux = compute_normalized_colormap(
        df_fluxes, 
        str_flux_col,
        str_normalized_colormap='normalized_flux'
    )
    if len(selected_fluxes) == 0:
        print("No fluxes match the selected origin and destination indices.")
        return None
    
    # Determine map center based on centroids
    all_indices = list(set(origin_indices + destination_indices))
    available_indices = [idx for idx in all_indices if idx in centroids_dict]
    
    if available_indices:
        center_lat = sum([centroids_dict[idx][0] for idx in available_indices]) / len(available_indices)
        center_lon = sum([centroids_dict[idx][1] for idx in available_indices]) / len(available_indices)
        center = [center_lat, center_lon]
        zoom_start = 12
    else:
        # Fallback to a default center
        center = [0, 0]
        zoom_start = 2
    
    # Create folium map
    m = folium.Map(location=center, zoom_start=zoom_start, control_scale=True)
    
    # Create a clean copy of the geodataframe for Folium
    # This avoids potential serialization issues
    gdf_for_folium = gdf_polygons[['geometry', str_grid_idx]].copy()
    
    # Add choropleth layer for polygons
    geojson_data = gdf_for_folium.__geo_interface__
    folium.GeoJson(
        geojson_data,
        style_function=lambda x: {
            'fillColor': '#808080',
            'color': '#000000',
            'fillOpacity': 0.3,
            'weight': 1
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[str_grid_idx],
            aliases=['Grid ID:'],
            style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;")
        ),
        name='Grid Cells'
    ).add_to(m)
    
    # Create feature group for fluxes
    fluxes_group = folium.FeatureGroup(name=f'Fluxes ({len(selected_fluxes)})')
    # Create feature groups for origins and destinations
    origins_group = folium.FeatureGroup(name=f'Origins ({len(origin_indices)})')
    destinations_group = folium.FeatureGroup(name=f'Destinations ({len(destination_indices)})')
    
    # Create color map for flux values
    colormap = linear.viridis.scale(min_flux, max_flux)
    
    # Add lines for fluxes
    for _, row in selected_fluxes.iterrows():
        origin_idx = row[str_origin_col]
        dest_idx = row[str_destination_col]
        
        # Skip if either origin or destination is not in the centroids dictionary
        if origin_idx not in centroids_dict or dest_idx not in centroids_dict:
            continue
            
        origin_point = centroids_dict[origin_idx]
        dest_point = centroids_dict[dest_idx]
        
        # Calculate line properties based on flux
        flux = row[str_flux_col]
        normalized_flux = row['normalized_flux']
        weight = max(2, 1 + 5 * normalized_flux)
        
        # Create line
        folium.PolyLine(
            [origin_point, dest_point],
            color=colormap(flux),
            weight=weight,
            opacity=0.7,
            tooltip=f"Flux: {flux:.2f}<br>Origin: {origin_idx}<br>Destination: {dest_idx}",
            dash_array='5, 5' if flux < (min_flux + max_flux) / 2 else None
        ).add_to(fluxes_group)
        
        # Add origins and destinations to map
        folium.CircleMarker(
            location=origin_point,
            radius=7,
            color='red',
            fill=True,
            fill_color='red',
            fill_opacity=0.7,
            tooltip=f"Origin: {origin_idx}"
        ).add_to(origins_group)
        # Add destinations to map
        folium.CircleMarker(
            location=dest_point,
            radius=7,
            color='blue',
            fill=True,
            fill_color='blue',
            fill_opacity=0.7,
            tooltip=f"Destination: {dest_idx}"
        ).add_to(destinations_group)
    
    # Add the feature group to the map
    fluxes_group.add_to(m)    
    # Add feature groups to map
    origins_group.add_to(m)
    destinations_group.add_to(m)
    
    # Add colormap legend
    colormap.caption = f'Flux ({str_flux_col})'
    m.add_child(colormap)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Save to file if path is provided
    if save_path:
        m.save(save_path)
    
    return m





############# HIERARCHY PLOTS #############
def create_style_function(fill_color):
    return lambda feature: {
        'fillColor': fill_color,
        'color': 'fill_color',
        'weight': 1,
        'fillOpacity': 0.7,
        'opacity': 0.8
    }

from shapely.geometry import mapping

def folium_visualization_hierarchy(
    grid,
    hotspot_levels,
    str_hotspot_prefix,
    str_col_comuni_name,
    str_col_total_flows_grid,
    colormap="YlOrRd"
) -> folium.Map:
    """
    Visualize hotspot hierarchy on a folium map.
    Each hotspot level is drawn in a separate layer, colored by flow intensity.
    Level -1 is excluded.
    """

    # Center of the map
    center = grid.geometry.unary_union.centroid
    fmap = folium.Map(location=[center.y, center.x], zoom_start=12, tiles="cartodbpositron")

    # Select colormap
    colormap_obj = cm.linear.YlOrRd_09 if colormap == "YlOrRd" else getattr(cm.linear, colormap, cm.linear.YlOrRd_09)

    # Filter out -1 hotspots
    hotspot_grid = grid[grid[f"{str_hotspot_prefix}_{str_col_total_flows_grid}"] != -1]

    if len(hotspot_grid) > 0:
        # Get min and max flow values
        min_flow = hotspot_grid[str_col_total_flows_grid].min()
        max_flow = hotspot_grid[str_col_total_flows_grid].max()

        # Create colormap for flows
        flow_colormap = cm.LinearColormap(
            colors=colormap_obj.colors,
            vmin=min_flow,
            vmax=max_flow,
            caption=f"Flow Intensity ({str_col_total_flows_grid})"
        )
    else:
        flow_colormap = None

    # Add layers for each hotspot level (excluding -1)
    for level in sorted(hotspot_levels.keys()):
        if level == -1:
            continue  # skip

        grid_level = grid[grid[f"{str_hotspot_prefix}_{str_col_total_flows_grid}"] == level].copy()

        if not grid_level.empty:
            level_group = folium.FeatureGroup(name=f"Hotspot Level {level} ({len(grid_level)} areas)")

            for _, row in grid_level.iterrows():
                flow_value = row[str_col_total_flows_grid]
                fill_color = flow_colormap(flow_value) if (flow_colormap and pd.notna(flow_value)) else "lightgray"

                individual_geojson = folium.GeoJson(
                    mapping(row.geometry),
                    style_function=lambda feature, color=fill_color: {
                        "fillColor": color,
                        "color": "black",
                        "weight": 1,
                        "fillOpacity": 0.7,
                        "opacity": 0.8,
                    },
                    tooltip=folium.Tooltip(
                        f"<b>{row[str_col_comuni_name]}</b><br>"
                        f"Total Flows: {flow_value}<br>"
                        f"Hotspot Level: {level}"
                    ),
                )
                individual_geojson.add_to(level_group)

            level_group.add_to(fmap)

    # Add legend if available
    if flow_colormap:
        flow_colormap.add_to(fmap)

    # Add layer control
    folium.LayerControl().add_to(fmap)

    return fmap



############### PLOT FLUXES WITH LINES ###############
from typing import Dict, List
import folium
import branca.colormap as cm
import pandas as pd
import numpy as np


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

# Calculate bearing for arrow direction
import math    
def calculate_bearing(lat1, lon1, lat2, lon2):
    dlon = math.radians(lon2 - lon1)
    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)
    
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing = math.atan2(y, x)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360
    return bearing
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
    Case: is_in_flows -> incoming fluxes to the hotspot.
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


## ---------------- Plots the Bus deficency in a given area ---------------- ##

import folium
import branca.colormap as cm
import numpy as np

def plot_negative_differences_interactive(
    grid, 
    flows_negative, 
    str_col_i, 
    str_col_j, 
    str_col_difference,
    str_centroid_lat, str_centroid_lon, 
    caption_colorbar = "Negative Difference (Demand - Bus Supply)"
):
    flows_negative = flows_negative.filter(pl.col(str_col_difference) < - 10)
    # Prepare colormap (for negative values, more negative = darker)
    min_diff = flows_negative[str_col_difference].min()
    max_diff = flows_negative[str_col_difference].max()
    
    # Handle case where min_diff or max_diff is None (empty DataFrame or all null values)
    if min_diff is None or max_diff is None:
        min_diff = -100  # Default minimum for negative differences
        max_diff = 0     # Default maximum (0 for no difference)
    
    # Ensure max_diff is not greater than 0 for negative differences
    if max_diff > 0:
        max_diff = 0
        
    # Create colormap using LinearColormap
    colormap = cm.LinearColormap(
        colors=['red', 'orange', 'yellow'],
        vmin=min_diff,
        vmax=max_diff,
        caption= caption_colorbar
    )

    # Prepare centroid lookup
    grid_coords = {idx: [row[str_centroid_lat], row[str_centroid_lon]] for idx, row in grid.iterrows()}

    # Center map
    center_lat = grid[str_centroid_lat].mean()
    center_lon = grid[str_centroid_lon].mean()
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles='cartodbpositron')

    # Add grid polygons (light)
    folium.GeoJson(
        grid,
        name="Grid",
        style_function=lambda feature: {
            'fillColor': 'lightgray',
            'color': 'gray',
            'weight': 1,
            'fillOpacity': 0.2,
            'opacity': 0.5
        }
    ).add_to(fmap)

    # Plot negative difference flows
    for row in flows_negative.iter_rows(named=True):
        i, j, diff = row[str_col_i], row[str_col_j], row[str_col_difference]
        if i in grid_coords and j in grid_coords:
            folium.PolyLine(
                [grid_coords[i], grid_coords[j]],
                color=colormap(diff),
                weight=4,
                opacity=0.8,
                tooltip=f"From: {i} → To: {j}<br>Difference: {diff:.1f}"
            ).add_to(fmap)
            # Optionally, mark origins/destinations
            folium.CircleMarker(
                location=grid_coords[i],
                radius=4,
                color='blue',
                fill=True,
                fill_opacity=0.6,
                tooltip=f"Origin: {i}"
            ).add_to(fmap)
            folium.CircleMarker(
                location=grid_coords[j],
                radius=4,
                color='red',
                fill=True,
                fill_opacity=0.6,
                tooltip=f"Destination: {j}"
            ).add_to(fmap)

    fmap.add_child(colormap)
    folium.LayerControl().add_to(fmap)
    return fmap


import geopandas as gpd
import folium


def plot_portfolio_map_single_layer(cities_gdf,
                                    str_area_id_presenze, 
                                    str_col_comuni_name, 
                                    path_save_portfolio):
    """
    Plots an interactive folium map showing portfolio weights for each area in cities_gdf.  
    Areas with missing portfolio weights are excluded from the map.
    Parameters:
    -----------
    cities_gdf : GeoDataFrame
        GeoDataFrame containing city areas with geometry and portfolio weights
            str_area_id_presenze : str
        Column name in cities_gdf representing area IDs
    str_col_comuni_name : str
        Column name in cities_gdf representing comune names
    path_save_portfolio : str
        File path to save the portfolio map
    Returns:
    --------
    None
    The function saves an interactive folium map to the specified path.
    """

    # Report missing mappings if any
    _missing = cities_gdf["portfolio"].isna()
    n_missing = int(_missing.sum())
    if n_missing:
        print(
            f"Warning: {n_missing} areas in cities_gdf had no portfolio weight mapping.",
            "Examples:",
            cities_gdf.loc[_missing, str_area_id_presenze].head().tolist(),
        )

    # --- Folium visualization ---
    map_center = [cities_gdf.geometry.centroid.y.mean(), cities_gdf.geometry.centroid.x.mean()]
    m = folium.Map(location=map_center, zoom_start=8, tiles="cartodbpositron")

    # Add choropleth
    folium.Choropleth(
        geo_data=cities_gdf.dropna().to_json(),
        data=cities_gdf.dropna(),
        columns=[str_area_id_presenze, "portfolio"],
        key_on=f"feature.properties.{str_area_id_presenze}",
        fill_color="OrRd",
        fill_opacity=0.7,
        line_opacity=0.3,
        legend_name="Portfolio Weight",
    ).add_to(m)

    # Add hover tooltips (instead of markers/popups)
    tooltip = folium.GeoJson(
        cities_gdf.dropna(),
        style_function=lambda feature: {"fillOpacity": 0, "weight": 0},  # no extra styling
        tooltip=folium.features.GeoJsonTooltip(
            fields=[str_area_id_presenze, "portfolio", str_col_comuni_name],
            aliases=["Area ID:", "Portfolio Weight:", "Comune:"],
            localize=True,
            sticky=False,
            labels=True,
        ),
    )
    tooltip.add_to(m)

    m.save(path_save_portfolio)
    print("✅ Interactive Folium map saved to portfolio_map.html (hover to see info)")
    return m


def plot_portforlio_map_multiple_layers(cities_gdf: gpd.GeoDataFrame,
                                        str_area_id_presenze: str,
                                        columns_to_plot: list,
                                        str_col_comuni_name: str,
                                        save_path: str = "multi_layer_portfolio_map.html"):
    """
    Plots an interactive folium map with multiple layers, each representing a different portfolio weight column.
    Each layer will have its own independent color scale.
    """

    if not isinstance(cities_gdf, gpd.GeoDataFrame):
        raise TypeError("cities_gdf must be a GeoDataFrame")
    assert str_area_id_presenze in cities_gdf.columns, f"{str_area_id_presenze} not in cities_gdf"
    assert all(col in cities_gdf.columns for col in columns_to_plot), "Some columns in columns_to_plot not in cities_gdf"    

    cities_gdf = cities_gdf.dropna(subset=columns_to_plot)
    if cities_gdf.empty:
        raise ValueError("No data available in cities_gdf after dropping NaNs for specified columns.")

    # Create base map
    map_center = [cities_gdf.geometry.centroid.y.mean(), cities_gdf.geometry.centroid.x.mean()]
    m = folium.Map(location=map_center, zoom_start=8, tiles="cartodbpositron")
    portfolios_intensity = []
    for col in columns_to_plot:
        if len(portfolios_intensity) == 0:
            portfolios_intensity = list(cities_gdf[col])
        else:
            portfolios_intensity.extend(list(cities_gdf[col]))

    vmin, vmax = float(min(portfolios_intensity)), float(max(portfolios_intensity))
    colormap = cm.linear.OrRd_09.scale(vmin, vmax)
    colormap.caption = f"Investimento"
    for col in columns_to_plot:
        # Compute column-specific vmin/vmax and colormap
        layer = folium.FeatureGroup(name=f"{col}", show=(col == columns_to_plot[0]))
        folium.GeoJson(
            cities_gdf,
            style_function=lambda feature, column=col: {
                "fillColor": colormap(feature["properties"][column])
                if feature["properties"][column] is not None else "transparent",
                "color": "black",
                "weight": 0.3,
                "fillOpacity": 0.7,
            },
            tooltip=folium.features.GeoJsonTooltip(
                fields=[str_area_id_presenze, str_col_comuni_name, col],
                aliases=["Area ID:", "Comune:", f"{col}:"],
                localize=True,
                sticky=False,
                labels=True,
            ),
        ).add_to(layer)

        # Add layer + its colormap
        layer.add_to(m)
        colormap.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    m.save(save_path)
    print(f"✅ Multi-layer Folium map saved to {save_path}")


import geopandas as gpd
import contextily as ctx
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from mpl_toolkits.axes_grid1.anchored_artists import AnchoredSizeBar

def plot_polygons_and_with_scalar_field(
    gdf,
    column_plot,
    ax,
    fig,
    title,
    crs_proj="EPSG:3857",
    int_size_tick_measure=10000,
    str_size_tick_measure="10",
    cmap="viridis",   # new argument
    add_colorbar=True # optional colorbar
):
    """
    Plot the scalar field defined in column_plot over the geometries in gdf.

    Parameters
    ----------
    gdf : GeoDataFrame
        GeodataFrame containing geometries and a scalar field.
    column_plot : str
        Name of the column to visualize.
    ax : matplotlib.axes.Axes
        Axis to plot on.
    fig : matplotlib.figure.Figure
        Figure handle.
    title : str
        Title of the plot.
    crs_proj : str, optional
        CRS to project to (default: EPSG:3857).
    int_size_tick_measure : int, optional
        Real-world distance (in CRS units) represented by the scalebar.
    str_size_tick_measure : str, optional
        Label for the scalebar.
    cmap : str, optional
        Matplotlib colormap name (default: 'viridis').
    add_colorbar : bool, optional
        If True, adds a colorbar legend.
    """
    if gdf.crs != crs_proj:
        gdf = gdf.to_crs(crs_proj)

    try:
        # Plot polygons with colormap
        plot = gdf.plot(
            ax=ax,
            column=column_plot,
            alpha=0.7,
            edgecolor='black',
            cmap=cmap,
            legend=add_colorbar,
            legend_kwds={'label': column_plot, 'shrink': 0.7}
        )

        # Add basemap
        ctx.add_basemap(ax, crs=crs_proj, source=ctx.providers.CartoDB.PositronNoLabels)

        # Add scalebar
        fontprops = fm.FontProperties(size=12)
        scalebar = AnchoredSizeBar(
            ax.transData,
            int_size_tick_measure,
            str_size_tick_measure + ' km',
            'lower right',
            pad=0.1,
            color='black',
            frameon=False,
            size_vertical=1,
            fontproperties=fontprops
        )
        ax.add_artist(scalebar)

        ax.set_title(title)
        ax.axis('off')

    except Exception as e:
        plt.close(fig)
        raise e

    return fig, ax




def plot_pastur(eigvals_clean,q,sigma=1.0):
    def marchenko_pastur_pdf(x, q, sigma=1.0):
        """Marchenko-Pastur probability density function."""
        lambda_plus = sigma**2 * (1 + np.sqrt(1/q))**2
        lambda_minus = sigma**2 * (1 - np.sqrt(1/q))**2
        if lambda_minus < x < lambda_plus:
            return (1 / (2 * np.pi * q * sigma**2 * x)) * np.sqrt((lambda_plus - x) * (x - lambda_minus))
        else:
            return 0

    lambda_plus = sigma**2 * (1 + np.sqrt(1/q))**2
    lambda_minus = sigma**2 * (1 - np.sqrt(1/q))**2
    fig1,ax1 = plt.subplots(1,1,figsize=(6,6))
    ax1.hist(eigvals_clean, bins=50, density=True, alpha=0.5, label="Eigenvalues Clean", color="orange")
    #ax1.hist(np.linalg.eigvals(cov_matrix_numpy), bins=50, density=True, alpha=0.5, label="Eigenvalues Original", color="blue")
    x = np.linspace(0.01, max(eigvals_clean), 1000)
#    dx = x[1] - x[0]
    y = [marchenko_pastur_pdf(xi, q, sigma) for xi in x]
#    y = np.array(y)//np.sum(np.array(y))  # Normalize the PDF
    ax1.plot(x, y, label="Marchenko-Pastur PDF", color="green")
    ax1.axvline(x=lambda_plus, color='red', linestyle='--', label=r'$\lambda_{+}$')
    ax1.axvline(x=lambda_minus, color='green', linestyle='--', label=r'$\lambda_{-}$')
    ax1.set_yscale('log')
    plt.title("Eigenvalues Distribution")
    plt.legend()
    return fig1,ax1
