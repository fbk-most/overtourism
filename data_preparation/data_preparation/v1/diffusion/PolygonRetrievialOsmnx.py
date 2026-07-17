"""
Polygon Retrieval OSMnx - Transportation Network Extraction Module

This module provides utilities for extracting transportation network data from OpenStreetMap
using OSMnx library. It specializes in retrieving different types of transportation networks
(driving, walking, cycling) from geographic bounding boxes and converting them into 
GeoDataFrames for spatial analysis and mobility studies.

Main Components:

1. NETWORK TYPE EXTRACTION:
   - Driving network extraction for vehicle routing analysis
   - Walking network extraction for pedestrian accessibility
   - Cycling network extraction for bike route planning
   - Configurable simplification and edge truncation parameters

2. GRAPH PROCESSING:
   - NetworkX graph generation from OSM data
   - Graph-to-GeoDataFrame conversion for spatial operations
   - Graph simplification and cleaning for GraphML export
   - Coordinate system transformations and CRS management

3. PIPELINE INTEGRATION:
   - Complete pipeline for transport network retrieval with caching
   - Automatic file existence checking and data loading
   - Integration with configuration management system
   - Support for GTFS bounds-based network extraction

Key Functions:

gdf_drive_from_coords_bbox():
    Extracts driving network from bounding box coordinates.
    Returns both NetworkX graph and GeoDataFrame representations.

gdf_walk_from_coords_bbox():
    Retrieves pedestrian walkable network with edge truncation.
    Optimized for accessibility and tourism flow analysis.

gdf_bike_from_coords_bbox():
    Extracts cycling infrastructure including bike lanes and paths.
    Supports multi-modal transportation analysis.

pipeline_get_transport_network():
    Complete pipeline with caching, validation, and coordinate system handling.
    Integrates with project configuration and file management systems.

Network Processing Features:
- Automatic graph simplification for reduced complexity
- Edge geometry preservation for accurate routing
- Index assignment for network element identification
- CRS transformation for consistent spatial analysis
- GraphML export preparation with metadata cleaning

Integration Points:
- Works with GTFS bounding box data for network extent definition
- Supports mobility flow analysis through road network topology
- Compatible with tourism route planning and accessibility studies
- Provides foundation for multi-modal transportation analysis

Output Structure:
- GeoDataFrame with edge geometries and OSM attributes
- NetworkX graph for routing and network analysis algorithms
- Consistent indexing system for cross-referencing
- Geographic coordinate system standardization

Dependencies: osmnx, geopandas, networkx, RoadNetwork utilities
Data Source: OpenStreetMap via OSMnx API
Use Cases: Tourism routing, accessibility analysis, network topology studies
Author: Alberto Amaduzzi
"""
from osmnx import graph_from_bbox
from osmnx.simplification import simplify_graph
from osmnx.convert import graph_to_gdfs
from geopandas import GeoDataFrame
from networkx import read_graphml,write_graphml, compose_all
from os.path import exists
import numpy as np
from shapely.geometry import box
import logging
import pandas as pd

from data_preparation.diffusion.RoadNetwork import clean_graph_for_graphml, advanced_simplify_road_network

# DRIVE
def gdf_drive_from_coords_bbox(south,east,north,west):
    """
        @param bounds_gtfs: list of bounds
        @return: G_drive, gdf_drive
        NOTE: The function takes the bounds of the GTFS data and creates a graph using osmnx.
    """
    bbox = (north, south, east, west)
    G_public_transport = graph_from_bbox(bbox=bbox, network_type='drive',simplify=True,retain_all=False,truncate_by_edge=False)
    gdf_public_transport = graph_to_gdfs(G_public_transport, nodes=False, edges=True,node_geometry=True)
    return G_public_transport, gdf_public_transport
# WALK
def gdf_walk_from_coords_bbox(south,east,north,west):
    """
        @param bounds_gtfs: list of bounds
        @return: G_walk, gdf_walk
        NOTE: The function takes the bounds of the GTFS data and creates a graph using osmnx.
    """
    bbox = (north, south, east, west)
    G_walk = graph_from_bbox(bbox = bbox, network_type='walk',simplify=True,retain_all=False,truncate_by_edge=True)
    gdf_walk = graph_to_gdfs(G_walk, nodes=False, edges=True,node_geometry=True)
    return G_walk, gdf_walk
# BIKE
def gdf_bike_from_coords_bbox(south,east,north,west):
    """
        @param bounds_gtfs: list of bounds
        @return: G_bike, gdf_bike
        NOTE: The function takes the bounds of the GTFS data and creates a graph using osmnx.
    """
    bbox = (north, south, east, west)
    G_bike = graph_from_bbox(bbox = bbox, network_type='bike',simplify=True,retain_all=False,truncate_by_edge=True)
    gdf_bike = graph_to_gdfs(G_bike, nodes=False, edges=True,node_geometry=True)
    return G_bike, gdf_bike


#





## ---------------------- PIPELINE SPECIFIC ---------------------- ## 

def pipeline_get_transport_network(config,crs,str_transport_idx,complete_path_transport_gdf,complete_path_transport_graph, use_subdivision=False, subdivision_factor=2):
    """
    Original pipeline function with optional subdivision support.
    
    Args:
        config: Configuration dictionary with bbox coordinates
        crs: Target coordinate reference system  
        str_transport_idx: Transport index column name
        complete_path_transport_gdf: Path to save/load GeoDataFrame
        complete_path_transport_graph: Path to save/load graph
        use_subdivision: Whether to use subdivision approach (default: False for backward compatibility)
        subdivision_factor: Number of subdivisions per dimension if using subdivision
    
    Returns:
        gdf_public_transport: GeoDataFrame with transport network
        G_public_transport: NetworkX graph
    """
    if use_subdivision:
        # Use the new subdivided approach
        return pipeline_get_transport_network_subdivided(
            config, crs, str_transport_idx, complete_path_transport_gdf, 
            complete_path_transport_graph, subdivision_factor=subdivision_factor,
            use_subdivision=True
        )
    
    # Original implementation for backward compatibility
    assert "north" in config, "North bound not set"                                                                                     # check if the north bound is set
    assert "south" in config, "South bound not set"                                                                                     # check if the south bound is set
    assert "east" in config, "East bound not set"                                                                                       # check if the east bound is set
    assert "west" in config, "West bound not set"                                                                                       # check if the west bound is set
    assert config["north"] > config["south"], "North bound must be greater than south bound"                                            # check if the north bound is greater than the south bound
    assert config["east"] > config["west"], "East bound must be greater than west bound"                                                # check if the east bound is greater than the west bound 
    if not exists(complete_path_transport_gdf):                                                                                         # check if the gdf file exists
        G_public_transport, gdf_public_transport = gdf_drive_from_coords_bbox(config["south"],                                          #
                                                                            config["east"],                                             # compute the gdf transport
                                                                            config["north"],                                            # compute the G transport
                                                                            config["west"])                                             #     
        G_public_transport = clean_graph_for_graphml(G_public_transport)  
#        G_public_transport = simplify_graph(G_public_transport)                               # clean the graph for graphml
        gdf_public_transport = gdf_public_transport.to_crs(crs)                                                                         # convert the gdf to the crs_proj
        gdf_public_transport["index"] = range(len(gdf_public_transport))                                                                # add the index column to the gdf
        gdf_public_transport = gdf_public_transport.rename(columns={"index":str_transport_idx})                                         # rename the column name to transport_id
        gdf_public_transport.to_file(complete_path_transport_gdf, driver="GeoJSON")                                                     # save the gdf to the output folder
    else:
        gdf_public_transport = GeoDataFrame.from_file(complete_path_transport_gdf)                                                      # load the gdf transport        
        bbox = (config["north"],config["south"],config["east"],config["west"])
        G_public_transport = graph_from_bbox(bbox=bbox, network_type='drive',simplify=True,retain_all=False,truncate_by_edge=False)
                                                                                                                                        # load the graph
    return gdf_public_transport, G_public_transport


def subdivide_bbox_into_tiles(south, east, north, west, subdivision_factor=2):
    """
    Subdivide a bounding box into smaller tiles for distributed network extraction.
    
    Args:
        south, east, north, west: Bounding box coordinates
        subdivision_factor: Number of subdivisions per dimension (default: 2x2 = 4 tiles)
    
    Returns:
        List of tuples: [(south, east, north, west), ...] for each tile
    """
    lat_step = (north - south) / subdivision_factor
    lon_step = (east - west) / subdivision_factor
    
    tiles = []
    for i in range(subdivision_factor):
        for j in range(subdivision_factor):
            tile_south = south + i * lat_step
            tile_north = south + (i + 1) * lat_step
            tile_west = west + j * lon_step
            tile_east = west + (j + 1) * lon_step
            tiles.append((tile_south, tile_east, tile_north, tile_west))
    
    return tiles


def merge_transport_networks(graph_list, gdf_list):
    """
    Merge multiple transport networks from subdivided extractions.
    
    Args:
        graph_list: List of NetworkX graphs from different tiles
        gdf_list: List of GeoDataFrames from different tiles
    
    Returns:
        merged_graph: Combined NetworkX graph
        merged_gdf: Combined GeoDataFrame with deduplicated edges
    """
    logger = logging.getLogger(__name__)
    
    # Merge graphs using NetworkX compose_all
    logger.info(f"Merging {len(graph_list)} graphs from subdivided extraction")
    merged_graph = compose_all(graph_list)
    
    # Merge GeoDataFrames and remove duplicates
    logger.info(f"Merging {len(gdf_list)} GeoDataFrames from subdivided extraction")
    
    # Manual concatenation of GeoDataFrames
    if len(gdf_list) == 1:
        merged_gdf = gdf_list[0].copy()
    else:
        # Combine all GeoDataFrames
        all_data = []
        for gdf in gdf_list:
            all_data.extend(gdf.to_dict('records'))
        
        # Create new GeoDataFrame from combined data
        if all_data:
            merged_gdf = GeoDataFrame(all_data)
    
    # Remove duplicate edges based on geometry and osmid
    if 'osmid' in merged_gdf.columns:
        merged_gdf = merged_gdf.drop_duplicates(subset=['osmid'], keep='first')
    else:
        # Fallback: remove duplicates based on geometry similarity
        merged_gdf = merged_gdf.drop_duplicates(subset=['geometry'], keep='first')
    
    # Reset index
    merged_gdf = merged_gdf.reset_index(drop=True)
    
    logger.info(f"Final network: {len(merged_graph.nodes)} nodes, {len(merged_graph.edges)} edges")
    logger.info(f"Final GeoDataFrame: {len(merged_gdf)} edges")
    
    return merged_graph, merged_gdf


def gdf_drive_from_coords_bbox_subdivided(south, east, north, west, subdivision_factor=2, overlap_buffer=0.001):
    """
    Extract driving network from bounding box using subdivision approach.
    
    Args:
        south, east, north, west: Bounding box coordinates
        subdivision_factor: Number of subdivisions per dimension
        overlap_buffer: Buffer to add to each tile to ensure connectivity (in degrees)
    
    Returns:
        G_drive: Combined NetworkX graph
        gdf_drive: Combined GeoDataFrame
    """
    logger = logging.getLogger(__name__)
    
    # Calculate total area for subdivision decision
    area = (north - south) * (east - west)
    logger.info(f"Extracting driving network from area: {area:.6f} deg² using {subdivision_factor}x{subdivision_factor} subdivision")
    
    # Get subdivision tiles
    tiles = subdivide_bbox_into_tiles(south, east, north, west, subdivision_factor)
    
    graphs = []
    gdfs = []
    
    for i, (tile_s, tile_e, tile_n, tile_w) in enumerate(tiles):
        logger.info(f"Processing tile {i+1}/{len(tiles)}: bounds=({tile_s:.4f}, {tile_e:.4f}, {tile_n:.4f}, {tile_w:.4f})")
        
        # Add buffer to ensure connectivity between tiles
        buffered_s = max(tile_s - overlap_buffer, south)
        buffered_e = min(tile_e + overlap_buffer, east)
        buffered_n = min(tile_n + overlap_buffer, north)
        buffered_w = max(tile_w - overlap_buffer, west)
        
        try:
            # Extract network for this tile
            tile_graph, tile_gdf = gdf_drive_from_coords_bbox(
                buffered_s, buffered_e, buffered_n, buffered_w
            )
            
            if len(tile_gdf) > 0:
                graphs.append(tile_graph)
                gdfs.append(tile_gdf)
                logger.info(f"Tile {i+1}: extracted {len(tile_gdf)} edges")
            else:
                logger.warning(f"Tile {i+1}: no edges extracted")
                
        except Exception as e:
            logger.error(f"Error processing tile {i+1}: {e}")
            continue
    
    if not graphs:
        raise ValueError("No valid network data extracted from any tiles")
    
    # Merge all networks
    merged_graph, merged_gdf = merge_transport_networks(graphs, gdfs)
    
    return merged_graph, merged_gdf


def gdf_walk_from_coords_bbox_subdivided(south, east, north, west, subdivision_factor=2, overlap_buffer=0.001):
    """
    Extract walking network from bounding box using subdivision approach.
    
    Args:
        south, east, north, west: Bounding box coordinates
        subdivision_factor: Number of subdivisions per dimension
        overlap_buffer: Buffer to add to each tile to ensure connectivity (in degrees)
    
    Returns:
        G_walk: Combined NetworkX graph
        gdf_walk: Combined GeoDataFrame
    """
    logger = logging.getLogger(__name__)
    
    # Calculate total area for subdivision decision
    area = (north - south) * (east - west)
    logger.info(f"Extracting walking network from area: {area:.6f} deg² using {subdivision_factor}x{subdivision_factor} subdivision")
    
    # Get subdivision tiles
    tiles = subdivide_bbox_into_tiles(south, east, north, west, subdivision_factor)
    
    graphs = []
    gdfs = []
    
    for i, (tile_s, tile_e, tile_n, tile_w) in enumerate(tiles):
        logger.info(f"Processing tile {i+1}/{len(tiles)}: bounds=({tile_s:.4f}, {tile_e:.4f}, {tile_n:.4f}, {tile_w:.4f})")
        
        # Add buffer to ensure connectivity between tiles
        buffered_s = max(tile_s - overlap_buffer, south)
        buffered_e = min(tile_e + overlap_buffer, east)
        buffered_n = min(tile_n + overlap_buffer, north)
        buffered_w = max(tile_w - overlap_buffer, west)
        
        try:
            # Extract network for this tile
            tile_graph, tile_gdf = gdf_walk_from_coords_bbox(
                buffered_s, buffered_e, buffered_n, buffered_w
            )
            
            if len(tile_gdf) > 0:
                graphs.append(tile_graph)
                gdfs.append(tile_gdf)
                logger.info(f"Tile {i+1}: extracted {len(tile_gdf)} edges")
            else:
                logger.warning(f"Tile {i+1}: no edges extracted")
                
        except Exception as e:
            logger.error(f"Error processing tile {i+1}: {e}")
            continue
    
    if not graphs:
        raise ValueError("No valid network data extracted from any tiles")
    
    # Merge all networks
    merged_graph, merged_gdf = merge_transport_networks(graphs, gdfs)
    
    return merged_graph, merged_gdf


def gdf_bike_from_coords_bbox_subdivided(south, east, north, west, subdivision_factor=2, overlap_buffer=0.001):
    """
    Extract biking network from bounding box using subdivision approach.
    
    Args:
        south, east, north, west: Bounding box coordinates
        subdivision_factor: Number of subdivisions per dimension
        overlap_buffer: Buffer to add to each tile to ensure connectivity (in degrees)
    
    Returns:
        G_bike: Combined NetworkX graph
        gdf_bike: Combined GeoDataFrame
    """
    logger = logging.getLogger(__name__)
    
    # Calculate total area for subdivision decision
    area = (north - south) * (east - west)
    logger.info(f"Extracting biking network from area: {area:.6f} deg² using {subdivision_factor}x{subdivision_factor} subdivision")
    
    # Get subdivision tiles
    tiles = subdivide_bbox_into_tiles(south, east, north, west, subdivision_factor)
    
    graphs = []
    gdfs = []
    
    for i, (tile_s, tile_e, tile_n, tile_w) in enumerate(tiles):
        logger.info(f"Processing tile {i+1}/{len(tiles)}: bounds=({tile_s:.4f}, {tile_e:.4f}, {tile_n:.4f}, {tile_w:.4f})")
        
        # Add buffer to ensure connectivity between tiles
        buffered_s = max(tile_s - overlap_buffer, south)
        buffered_e = min(tile_e + overlap_buffer, east)
        buffered_n = min(tile_n + overlap_buffer, north)
        buffered_w = max(tile_w - overlap_buffer, west)
        
        try:
            # Extract network for this tile
            tile_graph, tile_gdf = gdf_bike_from_coords_bbox(
                buffered_s, buffered_e, buffered_n, buffered_w
            )
            
            if len(tile_gdf) > 0:
                graphs.append(tile_graph)
                gdfs.append(tile_gdf)
                logger.info(f"Tile {i+1}: extracted {len(tile_gdf)} edges")
            else:
                logger.warning(f"Tile {i+1}: no edges extracted")
                
        except Exception as e:
            logger.error(f"Error processing tile {i+1}: {e}")
            continue
    
    if not graphs:
        raise ValueError("No valid network data extracted from any tiles")
    
    # Merge all networks
    merged_graph, merged_gdf = merge_transport_networks(graphs, gdfs)
    
    return merged_graph, merged_gdf


def pipeline_get_transport_network_subdivided(config, crs, str_transport_idx, complete_path_transport_gdf, 
                                            complete_path_transport_graph, subdivision_factor=2, 
                                            area_threshold=0.1, use_subdivision=None):
    """
    Enhanced pipeline for transport network extraction with optional subdivision for large areas.
    
    Args:
        config: Configuration dictionary with bbox coordinates
        crs: Target coordinate reference system
        str_transport_idx: Transport index column name
        complete_path_transport_gdf: Path to save/load GeoDataFrame
        complete_path_transport_graph: Path to save/load graph
        subdivision_factor: Number of subdivisions per dimension (default: 2x2 = 4 tiles)
        area_threshold: Area threshold in square degrees above which subdivision is used (default: 0.1)
        use_subdivision: Force subdivision (True/False) or auto-decide based on area (None)
    
    Returns:
        gdf_public_transport: GeoDataFrame with transport network
        G_public_transport: NetworkX graph
    """
    logger = logging.getLogger(__name__)
    
    # Validate configuration
    assert "north" in config, "North bound not set"
    assert "south" in config, "South bound not set"
    assert "east" in config, "East bound not set"
    assert "west" in config, "West bound not set"
    assert config["north"] > config["south"], "North bound must be greater than south bound"
    assert config["east"] > config["west"], "East bound must be greater than west bound"
    
    # Calculate area and decide on subdivision strategy
    area = (config["north"] - config["south"]) * (config["east"] - config["west"])
    
    if use_subdivision is None:
        use_subdivision = area > area_threshold
        
    logger.info(f"Bounding box area: {area:.6f} deg²")
    logger.info(f"Using subdivision: {use_subdivision}")
    
    if not exists(complete_path_transport_gdf):
        if use_subdivision:
            logger.info(f"Using subdivided extraction with {subdivision_factor}x{subdivision_factor} tiles")
            G_public_transport, gdf_public_transport = gdf_drive_from_coords_bbox_subdivided(
                config["south"], config["east"], config["north"], config["west"],
                subdivision_factor=subdivision_factor
            )
        else:
            logger.info("Using standard single-request extraction")
            G_public_transport, gdf_public_transport = gdf_drive_from_coords_bbox(
                config["south"], config["east"], config["north"], config["west"]
            )
        
        # Clean and process the graph
        G_public_transport = clean_graph_for_graphml(G_public_transport)
        
        # Process GeoDataFrame
        gdf_public_transport = gdf_public_transport.to_crs(crs)
        gdf_public_transport["index"] = range(len(gdf_public_transport))
        gdf_public_transport = gdf_public_transport.rename(columns={"index": str_transport_idx})
        
        # Save the results
        gdf_public_transport.to_file(complete_path_transport_gdf, driver="GeoJSON")
        logger.info(f"Saved transport network: {len(gdf_public_transport)} edges")
        
    else:
        # Load existing data
        logger.info("Loading existing transport network data")
        gdf_public_transport = GeoDataFrame.from_file(complete_path_transport_gdf)
        
        # Recreate graph (note: this might be slow for large networks)
        bbox = (config["north"], config["south"], config["east"], config["west"])
        G_public_transport = graph_from_bbox(
            bbox=bbox, network_type='drive', simplify=True, 
            retain_all=False, truncate_by_edge=False
        )
    
    return gdf_public_transport, G_public_transport