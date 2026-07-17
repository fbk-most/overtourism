import geopandas as gpd
import folium
import branca.colormap as cm


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
