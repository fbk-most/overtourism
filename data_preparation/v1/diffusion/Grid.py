"""
Grid Generation and Geospatial Analysis Module

This module provides utilities for creating and managing spatial grids for geospatial analysis,
particularly focused on tourism and mobility studies. It handles grid generation from bounding
boxes, spatial relationships, and population-based analysis within grid cells.

Main Components:

1. GRID GENERATION FUNCTIONS:
   - Angular resolution grid creation from bounding boxes
   - Metric resolution grid generation (meters-based)
   - Grid clipping and intersection with geographic boundaries
   - Coordinate system transformations and projections

2. SPATIAL RELATIONSHIP ANALYSIS:
   - Grid-to-point spatial joins (e.g., stops per grid cell)
   - Geometry containment analysis
   - Grid cell filtering based on content thresholds
   - Component-based grid organization

3. POPULATION AND CENTER-OF-MASS ANALYSIS:
   - Population-weighted center calculation
   - Center-of-mass computation from grid data
   - Maximum population center identification
   - Population distribution analysis within grids

Key Functions:

get_grid_bbox_resolution_in_angle():
    Creates a grid with angular resolution from geographic bounding box.
    Useful for large-scale geographic analysis.

get_grid_from_bounding_box_resolution_in_meters():
    Generates a grid with metric resolution (Lx, Ly in meters).
    Handles coordinate transformations to tangent space for accurate measurements.

count_number_stops_per_grid():
    Counts transportation stops within each grid cell.
    Used for transport network analysis and filtering.

compute_center_of_mass_from_grid():
    Calculates population-weighted center of mass.
    Essential for tourism flow analysis and hotspot identification.

pipeline_get_grid_gtfs():
    Complete pipeline for GTFS-based grid generation.
    Handles caching, coordinate systems, and centroid calculation.

Grid Structure:
Each grid cell contains:
- Geometry (polygon boundaries)
- Index coordinates (i, j)
- Centroid coordinates (x, y)
- Component identifier
- Optional population/activity data

Use Cases:
- Tourism hotspot analysis through population grids
- Transportation network analysis with stop counting
- Spatial aggregation of mobility data
- Center-of-mass calculations for flow analysis
- Grid-based visualization and mapping

Dependencies: numpy, geopandas, shapely, GeometrySphere
Integration: Works with GTFS data, population datasets, and mobility analysis
Author: Alberto Amaduzzi
"""

import logging
import os
import numpy as np
import geopandas as gpd
import shapely as shp
from data_preparation.diffusion.GeometrySphere import *
from shapely.ops import unary_union
from shapely.geometry import Polygon,Point, LineString
logger = logging.getLogger(__name__)


######## GRID FROM BOUNDING BOX #########

def get_grid_bbox_resolution_in_angle(grid_size,
                                bounding_box,
                                crs,
                                dir_grid,
                                save_dir_local):
    '''
        Input:
            grid_size: float -> size of the grid (in angle units)
            save_dir_local: str -> local directory to save the grid
            save_dir_server: str -> server directory to save the grid
            Files2Upload: dict -> dictionary to upload the files
        Output:

        centroid: Point -> centroid of the city
        bounding_box: tuple -> (minx,miny,maxx,maxy)
        grid: GeoDataFrame -> grid of points of size grid_size
        In this way grid is ready to be used as the matrix representation of the city and the gradient and the curl defined on it.
        From now on I will have that the lattice is associated to the centroid grid.
        Usage:
            grid and lattice are together containing spatial and network information
    '''
    logger.info("Get grid from bounding box info, with angular grid size ")
    if os.path.isfile(os.path.join(dir_grid,str(round(grid_size,3)),"grid.geojson")):
        grid = gpd.read_file(os.path.join(dir_grid,str(round(grid_size,3)),"grid.geojson"))
        bbox = shp.geometry.box(*bounding_box)
        bbox_gdf = gpd.GeoDataFrame(geometry=[bbox], crs=crs)
        x = np.arange(bounding_box[0], bounding_box[2], grid_size)
        y = np.arange(bounding_box[1], bounding_box[3], grid_size)
    else:
        bbox = shp.geometry.box(*bounding_box)
        bbox_gdf = gpd.GeoDataFrame(geometry=[bbox], crs=crs)
        x = np.arange(bounding_box[0], bounding_box[2], grid_size)
        y = np.arange(bounding_box[1], bounding_box[3], grid_size)
#        grid_points = gpd.GeoDataFrame(geometry=[shp.geometry.box(xi, yi,maxx = max(x),maxy = max(y)) for xi in x for yi in y], crs=crs)
        grid_points = gpd.GeoDataFrame(geometry=[shp.geometry.box(xi, yi, xi + grid_size, yi + grid_size) for xi in x for yi in y], crs=crs)
        ij = [[i,j] for i in range(len(x)) for j in range(len(y))]
        grid_points['i'] = np.array(ij)[:,0]
        grid_points['j'] = np.array(ij)[:,1]
        # Clip the grid to the bounding box
        grid = gpd.overlay(grid_points, bbox_gdf, how='intersection')
        grid['centroidx'] = grid.geometry.centroid.x
        grid['centroidy'] = grid.geometry.centroid.y                
        grid['area'] = grid['geometry'].apply(ComputeAreaSquare)
        grid['index'] = grid.index
    return grid


def get_grid_from_bounding_box_resolution_in_meters(bounding_box,
                                                    lat_c,
                                                    lon_c,
                                                    crs_,
                                                    Lx = 2.5,
                                                    Ly = 2,
                                                    str_name_index = "index",
                                                    str_i_name = "i",
                                                    str_j_name = "j"):
    """
        Description: 
            Generates a grid with cell's side lengths Lx,Ly:
            Columns:
                i: index in the x direction
                j: index on y
                component: Component of the beach
                geometry: grid
    """
    # Creating an overall box to have a rectangular grid and avoid dishomogeneities in the grid indices
    lon_max,lon_min, lat_max, lat_min = bounding_box
    # NOTE:transform the bounding box to the tangent space
    minx,miny = ProjCoordsTangentSpace(lat_min, lon_min, lat_c, lon_c)
    maxx,maxy = ProjCoordsTangentSpace(lat_max, lon_max, lat_c, lon_c)
    # Count That are useful to define the grid indexing
    CountPolygons,CountIsPolygon,CountJsPolygon = 0,0,0
    Is,Js = [], []    
    indices = []
    CountIsPolygon = CountIsPolygon + len(Is)
    CountJsPolygon = CountJsPolygon + len(Js)
    # Columns GeoDataFrame squares
    squares = []
    Is,Js = [], []
    Component = []
    # 
    coord_x = minx
    coord_y = miny
    i = 0
    # Tessellate The Overall Box so that i,j are ordered, and the grid i,j is below i,j+1
    # and on the left of i+1,j
    index = 0
    while (coord_x < maxx):
        j = 0
        while (coord_y < maxy):
            # Transform back to lat,lon
            x0,y0 = from_tangent_space_to_latlon(coord_x, coord_y,lat_c, lon_c)
            x1,y1 = from_tangent_space_to_latlon(coord_x + Lx, coord_y + Ly,lat_c, lon_c)
            square = Polygon([(x0,y0), (x1,y0), (x1,y1), (x0,y1)])
            squares.append(square)
            Is.append(int(i + CountIsPolygon*CountPolygons))
            Js.append(int(j + CountJsPolygon*CountPolygons))
            Component.append(int(CountPolygons))
            indices.append(index)
            j += 1
            coord_y += Ly
            index += 1

        i += 1
        coord_x += Lx
        coord_y = miny
    squares_gdf = gpd.GeoDataFrame(geometry=squares) # crs= "EPSG:32632"
    squares_gdf[str_i_name] = Is
    squares_gdf[str_j_name] = Js   
    squares_gdf["component"] = Component   
    squares_gdf[str_name_index] = indices
#        squares_gdf = squares_gdf[poly.contains(squares_gdf['geometry'])]
    CountPolygons += 1
    grid = gpd.GeoDataFrame(geometry=squares_gdf.geometry,crs = crs_) # crs= "EPSG:32632"
    grid[str_i_name] =squares_gdf[str_i_name]
    grid[str_j_name] = squares_gdf[str_j_name]   
    grid["component"] = squares_gdf["component"]   
    grid[str_name_index] = squares_gdf[str_name_index]
    # Define The components in the grid.  
    grid = grid.to_crs(crs_)
    return grid



def get_bounding_box_from_polygon_gdf(gdf_polygons):
    """
        @description:
            Get the bounding box from a polygon GeoDataFrame
        @input:
            gdf_polygons: GeoDataFrame -> polygons of the geometry of interest
        @output:
            bbox: tuple -> (minx,miny,maxx,maxy)
            crs_: str -> coordinate reference system of the polygons
            beach_polygons: list -> list of polygons
        @usage:
            bbox, crs_, beach_polygons = get_bounding_box_from_polygon_gdf(gdf_polygons)
    """
    crs_ = gdf_polygons.crs
    gdf_polygons = gdf_polygons.to_crs(gdf_polygons.estimate_utm_crs()) # "EPSG:4326"
    # All Polygons
    beach_polygons = list(unary_union(gdf_polygons['geometry']).geoms)
    bbox = unary_union(beach_polygons).bounds
    return bbox, crs_, beach_polygons


# Relationships with other geometries

def count_number_stops_per_grid(Grid_gtfs,
                                str_grid_idx,
                                grid_idx_2_stop_idx,
                                str_col_n_stops = "n_stops"):
    """
        Count the number of stops in each grid cell and add it as a new column to the GeoDataFrame.
        NOTE: We want to clean the transport network from the roads that are very few stops.
        We decide this as keeping all the roads is too heavy for the area considered.
        This method is preliminary to the polish of the network.
    """
    Grid_gtfs[str_col_n_stops] = Grid_gtfs[str_grid_idx].apply(lambda x: len(grid_idx_2_stop_idx[x]) if x in grid_idx_2_stop_idx else 0)
    return Grid_gtfs

def is_the_geometry_inside_cell_droppable(Grid_gtfs,str_col_n_stops,str_col_is_droppable = "is_roads_inside_droppable",threshold_n_stops = 2):
    """
        Check if the geometry is inside the cell and if the number of stops is below a threshold.
        If so, the roads that are inside the cell are considered droppable.
    """
    Grid_gtfs[str_col_is_droppable] = Grid_gtfs[str_col_n_stops] >= threshold_n_stops
    return Grid_gtfs

# ---------------- Population Related Functions ---------------- #

def compute_center_of_mass_from_grid(grid,
                                    coords_center,
                                    str_col_population = "population",
                                    str_col_centroidx = "centroidx",
                                    str_col_centroidy = "centroidy"):
    '''
        This function computes the center of mass of the map.
        NOTE: It assumes one knows the population of each cell.
    '''
    assert str_col_population in grid.columns, f"Column {str_col_population} not found in grid"
    assert str_col_centroidx in grid.columns, f"Column {str_col_centroidx} not found in grid"
    assert str_col_centroidy in grid.columns, f"Column {str_col_centroidy} not found in grid"
    return np.mean(grid[str_col_population].to_numpy()[:,np.newaxis]*(np.column_stack((grid[str_col_centroidx].values, grid[str_col_centroidy].values)) - np.tile(coords_center,(len(grid),1))),axis = 0)

def ExtractCenterByPopulation(grid,
                              str_col_population = "population",
                            str_col_centroidx = "centroidx",
                            str_col_centroidy = "centroidy"):
    '''
        This code defines a function ExtractCenterByPopulation that takes a pandas DataFrame grid as input.
        It asserts that the DataFrame has a column named 'population'.
        It then creates a copy of the 'population' column and finds the index of the maximum value in it. 
        It uses this index to extract the corresponding values from the 'centroidx' and 'centroidy' columns, 
        and returns them as a numpy array coords_center along with the index center_idx.
        @return:
            coords_center: numpy array -> coordinates of the center of the grid
            center_idx: int -> index of the grid with the highest population
    '''
    assert str_col_population in grid.columns, f"Column {str_col_population} not found in grid"
    assert str_col_centroidx in grid.columns, f"Column {str_col_centroidx} not found in grid"
    assert str_col_centroidy in grid.columns, f"Column {str_col_centroidy} not found in grid"
    # Extract the index of the grid with the highest population
    population = grid[str_col_population].copy()
    center_idx = np.argmax(population)
    coords_center = np.array([grid[str_col_centroidx][center_idx],grid[str_col_centroidy][center_idx]]) 
    return coords_center,center_idx






#### PIPELINE TOURISM ####


def pipeline_get_grid_gtfs(Lx,Ly,bounds_gtfs,centroid_gtfs,str_name_index,str_i_name, str_j_name,str_centroid_grid_x,str_centroid_grid_y,complete_path_grid_gtfs,crs="EPSG:4326"):
    """
        Function to create the grid of the GTFS network.
        - Computes and saves if not computed.
        - Upload otherwhise
        @params Lx: size of the grid in meters
        @params Ly: size of the grid in meters
        @params bounds_gtfs: bounds of the GTFS network [north,south,east,west]
        @params complete_path_grid_gtfs: path to the grid file
        @return: grid of the GTFS network
    """
    if not os.path.exists(complete_path_grid_gtfs):
        Grid_gtfs = get_grid_from_bounding_box_resolution_in_meters(bounds_gtfs,
                                                        centroid_gtfs.x,
                                                        centroid_gtfs.y,
                                                        4326,
                                                        Lx = Lx,
                                                        Ly = Ly,
                                                        str_name_index = str_name_index,
                                                        str_i_name = str_i_name,
                                                        str_j_name = str_j_name)
        Grid_gtfs = Grid_gtfs.to_crs(crs)
        Grid_gtfs[str_centroid_grid_x],Grid_gtfs[str_centroid_grid_y] = Grid_gtfs.geometry.centroid.x,Grid_gtfs.geometry.centroid.y
        Grid_gtfs.to_file(complete_path_grid_gtfs, driver="GeoJSON")
    else:
        Grid_gtfs = gpd.read_file(complete_path_grid_gtfs)
    return Grid_gtfs