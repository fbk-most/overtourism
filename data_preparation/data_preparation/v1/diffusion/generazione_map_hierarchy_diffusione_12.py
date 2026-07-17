"""
Overview:
    This script contains the function to produce and visualize map_hierarchy = map_hierarchy_{user_profile}_t_{str_t}_{str_t1}.html
    folium_visualization_hierarchy that calls internally create_style_function
Description:
    - folium_visualization_hierarchy: creates a folium map visualizing hierarchical hotspot levels
    - create_style_function: generates a style function for folium GeoJson layers

The visualization consists of multiple layers. Each layer corresponds to a hotspot level (excluding level -1). Each area within a level is colored based on the intensity of flows, using a specified colormap.
The flows can be incoming and outcoming. If they are incoming, then the hotspot is the is defined as the one that is receiving too many people, otherwhise the hotpost is the one that is sending too many people.
Therefore, the in and out are not symmetric, since we have that for example Pinzolo can be receiving many people while sending few people. Bologna can be sending a lot of people while receiving few people.
    
Author: Alberto Amaduzzi

"""
import branca.colormap as cm
import folium
import pandas as pd
from shapely.geometry import mapping

def create_style_function(fill_color):
    return lambda feature: {
        'fillColor': fill_color,
        'color': 'fill_color',
        'weight': 1,
        'fillOpacity': 0.7,
        'opacity': 0.8
    }


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