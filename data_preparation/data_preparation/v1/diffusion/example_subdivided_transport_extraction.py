#!/usr/bin/env python3
"""
Example script demonstrating subdivided transport network extraction.

This script shows how to use the new subdivision functionality to extract
transport networks from large geographic areas by breaking them into smaller
tiles and then merging the results.

Usage:
    python example_subdivided_transport_extraction.py

Author: Claude Sonnet 4
"""

import os
import logging
from PolygonRetrievialOsmnx import (
    gdf_drive_from_coords_bbox_subdivided,
    gdf_walk_from_coords_bbox_subdivided, 
    gdf_bike_from_coords_bbox_subdivided,
    pipeline_get_transport_network_subdivided
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def example_subdivided_extraction():
    """
    Example of subdivided transport network extraction for a large area.
    """
    
    # Define a large bounding box (e.g., Trentino-Alto Adige region)
    # Note: These coordinates should be adjusted to your area of interest
    config = {
        "north": 47.1,   # Northern boundary
        "south": 45.8,   # Southern boundary  
        "east": 12.5,    # Eastern boundary
        "west": 10.4     # Western boundary
    }
    
    # Calculate area
    area = (config["north"] - config["south"]) * (config["east"] - config["west"])
    logger.info(f"Total bounding box area: {area:.6f} square degrees")
    
    # Set up paths
    output_dir = "Output/subdivided_extraction_example"
    os.makedirs(output_dir, exist_ok=True)
    
    complete_path_transport_gdf = os.path.join(output_dir, "transport_network_subdivided.geojson")
    complete_path_transport_graph = os.path.join(output_dir, "transport_network_subdivided.graphml")
    
    # Example 1: Direct subdivided extraction
    logger.info("=== Example 1: Direct subdivided extraction ===")
    
    try:
        # Extract driving network with 3x3 subdivision (9 tiles)
        G_drive, gdf_drive = gdf_drive_from_coords_bbox_subdivided(
            south=config["south"],
            east=config["east"], 
            north=config["north"],
            west=config["west"],
            subdivision_factor=3,  # 3x3 = 9 tiles
            overlap_buffer=0.001   # Small buffer for connectivity
        )
        
        logger.info(f"Extracted driving network: {len(G_drive.nodes)} nodes, {len(G_drive.edges)} edges")
        logger.info(f"GeoDataFrame: {len(gdf_drive)} edges")
        
        # Save results
        gdf_drive.to_file(complete_path_transport_gdf, driver="GeoJSON")
        logger.info(f"Saved subdivided network to: {complete_path_transport_gdf}")
        
    except Exception as e:
        logger.error(f"Error in direct subdivided extraction: {e}")
    
    # Example 2: Using the enhanced pipeline
    logger.info("=== Example 2: Enhanced pipeline with auto-subdivision ===")
    
    try:
        # Use pipeline with automatic subdivision based on area
        gdf_pipeline, G_pipeline = pipeline_get_transport_network_subdivided(
            config=config,
            crs="EPSG:4326",
            str_transport_idx="transport_id",
            complete_path_transport_gdf=os.path.join(output_dir, "pipeline_subdivided.geojson"),
            complete_path_transport_graph=os.path.join(output_dir, "pipeline_subdivided.graphml"),
            subdivision_factor=2,       # 2x2 = 4 tiles
            area_threshold=0.05,        # Use subdivision if area > 0.05 sq degrees
            use_subdivision=None        # Auto-decide based on area
        )
        
        logger.info(f"Pipeline extraction: {len(gdf_pipeline)} edges")
        
    except Exception as e:
        logger.error(f"Error in pipeline extraction: {e}")
    
    # Example 3: Different transport modes
    logger.info("=== Example 3: Different transport modes ===")
    
    # Use a smaller area for this example to reduce processing time
    small_config = {
        "north": 46.1,
        "south": 45.9, 
        "east": 11.2,
        "west": 11.0
    }
    
    try:
        # Walking network
        logger.info("Extracting walking network...")
        G_walk, gdf_walk = gdf_walk_from_coords_bbox_subdivided(
            small_config["south"], small_config["east"], 
            small_config["north"], small_config["west"],
            subdivision_factor=2
        )
        gdf_walk.to_file(os.path.join(output_dir, "walk_network.geojson"), driver="GeoJSON")
        logger.info(f"Walking network: {len(gdf_walk)} edges")
        
        # Biking network  
        logger.info("Extracting biking network...")
        G_bike, gdf_bike = gdf_bike_from_coords_bbox_subdivided(
            small_config["south"], small_config["east"],
            small_config["north"], small_config["west"], 
            subdivision_factor=2
        )
        gdf_bike.to_file(os.path.join(output_dir, "bike_network.geojson"), driver="GeoJSON")
        logger.info(f"Biking network: {len(gdf_bike)} edges")
        
    except Exception as e:
        logger.error(f"Error in multi-modal extraction: {e}")

def example_performance_comparison():
    """
    Example comparing performance of standard vs subdivided extraction.
    """
    logger.info("=== Performance Comparison Example ===")
    
    # Define a medium-sized area
    config = {
        "north": 46.2,
        "south": 45.9,
        "east": 11.3, 
        "west": 10.9
    }
    
    area = (config["north"] - config["south"]) * (config["east"] - config["west"])
    logger.info(f"Test area: {area:.6f} square degrees")
    
    # Test different subdivision factors
    subdivision_factors = [1, 2, 3]  # 1x1 (no subdivision), 2x2, 3x3
    
    for factor in subdivision_factors:
        logger.info(f"Testing with {factor}x{factor} subdivision...")
        
        try:
            if factor == 1:
                # Standard extraction (no subdivision)
                from PolygonRetrievialOsmnx import gdf_drive_from_coords_bbox
                G, gdf = gdf_drive_from_coords_bbox(
                    config["south"], config["east"], config["north"], config["west"]
                )
                logger.info(f"Standard extraction: {len(gdf)} edges")
            else:
                # Subdivided extraction
                G, gdf = gdf_drive_from_coords_bbox_subdivided(
                    config["south"], config["east"], config["north"], config["west"],
                    subdivision_factor=factor
                )
                logger.info(f"{factor}x{factor} subdivision: {len(gdf)} edges")
                
        except Exception as e:
            logger.error(f"Error with {factor}x{factor} subdivision: {e}")

if __name__ == "__main__":
    logger.info("Starting subdivided transport network extraction examples")
    
    # Run examples
    example_subdivided_extraction()
    example_performance_comparison()
    
    logger.info("Examples completed!")
