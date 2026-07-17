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

def plot_polygons_and_with_scalar_field(gdf,
                                        column_plot,
                                        ax,
                                        fig,
                                        title,
                                        crs_proj = "EPSG:3857",
                                        int_size_tick_measure = 10000,
                                        str_size_tick_measure = "10"
                                        ):
    if gdf.crs != crs_proj:
        gdf = gdf.to_crs(crs_proj)
    try:
        gdf.plot(ax=ax, alpha=0.2, edgecolor='black')
        # Plot centroids
        # Create points for centroids
        centroids = gdf.geometry.centroid
        centroids_gdf = gpd.GeoDataFrame(geometry=centroids, crs=gdf.crs)
        centroids_gdf.plot(ax=ax, column=column_plot,colorbar="viridis", alpha=0.4, markersize=30, marker='o')
        ax.axis('off')
        # Add a black and white basemap
        ctx.add_basemap(ax, crs=crs_proj, source=ctx.providers.CartoDB.PositronNoLabels)
        fontprops = fm.FontProperties(size=12)
        scalebar = AnchoredSizeBar(ax.transData,
                                int_size_tick_measure, str_size_tick_measure+ ' km', 'lower right', 
                                pad=0.1,
                                color='black',
                                frameon=False,
                                size_vertical=1,
                                fontproperties=fontprops)

        ax.add_artist(scalebar)
        ax.set_title(title)
    except Exception as e:
        # Close figure on error
        plt.close(fig)
        raise e
    return fig,ax

def plot_polygons_with_centroids(gdf,crs_proj,int_size_tick_measure,str_size_tick_measure,complete_path_plot):
    """
        Used to plot any polygon with their centroids.
    """
    if gdf.crs != crs_proj:
        gdf = gdf.to_crs(crs_proj)
    fig, ax = plt.subplots(1, 1, figsize=(15, 10))
    
    try:
        # Plot each city with a different color
        gdf.plot(ax=ax, alpha=0.2, edgecolor='black')
        # Plot centroids
        # Create points for centroids
        centroids = gdf.geometry.centroid
        centroids_gdf = gpd.GeoDataFrame(geometry=centroids, crs=gdf.crs)
        centroids_gdf.plot(ax=ax, color='green', alpha=0.4, markersize=30, marker='o')
        ax.axis('off')
        # Add a black and white basemap
        ctx.add_basemap(ax, crs=crs_proj, source=ctx.providers.CartoDB.PositronNoLabels)

        # Set the extent to the area of interest
        #ax.set_xlim(ctx.bounds2img(lon_min, lat_min, lon_max, lat_max, zoom=12)[1][0], ctx.bounds2img(lon_min, lat_min, lon_max, lat_max, zoom=12)[1][2])
        #ax.set_ylim(ctx.bounds2img(lon_min, lat_min, lon_max, lat_max, zoom=12)[1][1], ctx.bounds2img(lon_min, lat_min, lon_max, lat_max, zoom=12)[1][3])

        # Add a scale bar
        fontprops = fm.FontProperties(size=12)
        scalebar = AnchoredSizeBar(ax.transData,
                                int_size_tick_measure, str_size_tick_measure+ ' km', 'lower right', 
                                pad=0.1,
                                color='black',
                                frameon=False,
                                size_vertical=1,
                                fontproperties=fontprops)

        ax.add_artist(scalebar)
        
        ax.set_title('City Boundaries and Centroids')
        # Save the figure   
        plt.savefig(complete_path_plot, dpi=300, bbox_inches='tight')
        
        return fig, ax
    except Exception as e:
        # Close figure on error
        plt.close(fig)
        raise e

def plot_shapes_comuni_with_names(cities_gdf,
                                  centroids_gdf,
                                  complete_path_plot,
                                  int_size_tick_measure = 10000,
                                  str_size_tick_measure = "10",
                                  crs_proj="EPSG:3857"):
    """
    Plot the city boundaries with their areas labeled.
    
    Parameters:
        cities_gdf (GeoDataFrame): GeoDataFrame with city boundaries and areas
    """
    if cities_gdf.crs != crs_proj:
        cities_gdf = cities_gdf.to_crs(crs_proj)
    if centroids_gdf.crs != crs_proj:
        centroids_gdf = centroids_gdf.to_crs(crs_proj)
    fig, ax = plt.subplots(1, 1, figsize=(15, 10))
    
    # Plot each city with a different color
    cities_gdf.plot(ax=ax, alpha=0.5, edgecolor='black')
    
    # Plot centroids
    # Create points for centroids
    centroids_gdf.plot(ax=ax, color='red', markersize=30, marker='o')
    
    # Add city labels
    for idx, row in cities_gdf.iterrows():
        # Add annotation
        ax.annotate(
            f"{row['city_name']}", 
            xy=(row['centroid_lon'], row['centroid_lat']),
            xytext=(3, 3),
            textcoords="offset points",
            fontsize=10,
            ha='center'
        )
    ax.axis('off')
    # Add a black and white basemap
    ctx.add_basemap(ax, crs=crs_proj, source=ctx.providers.CartoDB.PositronNoLabels)

    # Set the extent to the area of interest
    #ax.set_xlim(ctx.bounds2img(lon_min, lat_min, lon_max, lat_max, zoom=12)[1][0], ctx.bounds2img(lon_min, lat_min, lon_max, lat_max, zoom=12)[1][2])
    #ax.set_ylim(ctx.bounds2img(lon_min, lat_min, lon_max, lat_max, zoom=12)[1][1], ctx.bounds2img(lon_min, lat_min, lon_max, lat_max, zoom=12)[1][3])

    # Add a scale bar
    fontprops = fm.FontProperties(size=12)
    scalebar = AnchoredSizeBar(ax.transData,
                            int_size_tick_measure, str_size_tick_measure+ ' km', 'lower right', 
                            pad=0.1,
                            color='black',
                            frameon=False,
                            size_vertical=1,
                            fontproperties=fontprops)

    ax.add_artist(scalebar)
    
    ax.set_title('City Boundaries and Centroids')
    # Save the figure   
    plt.savefig(complete_path_plot, dpi=300, bbox_inches='tight')
    
    return fig, ax


################# ROAD NETWORKS AND TRANSPORTATION NETWORKS #################

def plot_two_geodataframe_gpd(gdf1, gdf2, name1="Layer 1", name2="Layer 2", 
                             figsize=(15, 10), alpha1=0.7, alpha2=0.7, 
                             color1='blue', color2='red', add_basemap=True,
                             complete_path_gdf = None):
    """
    Plot two GeoDataFrames with different geometries on the same map.
    
    Parameters:
        gdf1, gdf2: GeoDataFrames to plot
        name1, name2: Names for the legend
        figsize: Figure size as (width, height)
        alpha1, alpha2: Transparency for each layer
        color1, color2: Colors for each layer
        add_basemap: Whether to add a basemap
    """
    # Ensure same CRS
    crs_to_use = "EPSG:3857"  # Web Mercator for basemap compatibility
    if gdf1.crs != crs_to_use:
        gdf1 = gdf1.to_crs(crs_to_use)
    if gdf2.crs != crs_to_use:
        gdf2 = gdf2.to_crs(crs_to_use)
    
    # Create figure and axis
    fig, ax = plt.subplots(figsize=figsize)
    
    # Plot first layer
    gdf1.plot(ax=ax, color=color1, alpha=alpha1, label=name1)
    
    # Plot second layer
    gdf2.plot(ax=ax, color=color2, alpha=alpha2, label=name2)
    
    # Add basemap
    if add_basemap:
        ctx.add_basemap(ax, source=ctx.providers.CartoDB.Positron)
    
    # Add legend and title
    ax.legend()
    ax.set_title(f"Comparison of {name1} and {name2}")
    
    # Add scale bar
    from matplotlib_scalebar.scalebar import ScaleBar
    ax.add_artist(ScaleBar(1, "m", location="lower right"))
    if complete_path_gdf is not None:
        plt.savefig(complete_path_gdf, dpi=300, bbox_inches='tight')
    
    
    return fig, ax

