# Subdivided Transport Network Extraction

This document describes the new subdivided transport network extraction functionality that allows for efficient extraction of large geographic areas by breaking them into smaller tiles.

## Overview

When extracting transport networks from large geographic areas using OSMnx, you may encounter:
- Memory limitations 
- API rate limits
- Network timeouts
- Reduced performance

The subdivided extraction approach solves these issues by:
1. **Dividing** the large bounding box into smaller tiles
2. **Extracting** transport networks from each tile independently  
3. **Merging** the results while preserving network connectivity
4. **Deduplicating** overlapping edges to create a unified network

## Key Features

### Automatic Subdivision Decision
- Automatically determines whether to use subdivision based on area size
- Configurable area threshold (default: 0.1 square degrees)
- Falls back to standard extraction for small areas

### Connectivity Preservation
- Uses overlap buffers between tiles to ensure network connectivity
- Merges NetworkX graphs using `compose_all()` 
- Deduplicates edges based on OSM IDs or geometry

### Multi-Modal Support
- Supports driving, walking, and biking networks
- Consistent API across all transport modes
- Same functionality as standard OSMnx extraction

### Flexible Configuration
- Configurable subdivision factors (2x2, 3x3, 4x4, etc.)
- Adjustable overlap buffers
- Force subdivision or auto-decide based on area

## Functions

### Core Functions

#### `subdivide_bbox_into_tiles(south, east, north, west, subdivision_factor=2)`
Divides a bounding box into smaller tiles.

**Parameters:**
- `south, east, north, west`: Bounding box coordinates
- `subdivision_factor`: Number of subdivisions per dimension (default: 2)

**Returns:**
- List of tuples: `[(south, east, north, west), ...]` for each tile

#### `merge_transport_networks(graph_list, gdf_list)`
Merges multiple transport networks from subdivided extractions.

**Parameters:**
- `graph_list`: List of NetworkX graphs from different tiles
- `gdf_list`: List of GeoDataFrames from different tiles  

**Returns:**
- `merged_graph`: Combined NetworkX graph
- `merged_gdf`: Combined GeoDataFrame with deduplicated edges

### Transport-Specific Functions

#### `gdf_drive_from_coords_bbox_subdivided(south, east, north, west, subdivision_factor=2, overlap_buffer=0.001)`
Extract driving network using subdivision approach.

#### `gdf_walk_from_coords_bbox_subdivided(south, east, north, west, subdivision_factor=2, overlap_buffer=0.001)` 
Extract walking network using subdivision approach.

#### `gdf_bike_from_coords_bbox_subdivided(south, east, north, west, subdivision_factor=2, overlap_buffer=0.001)`
Extract biking network using subdivision approach.

**Parameters:**
- `south, east, north, west`: Bounding box coordinates
- `subdivision_factor`: Number of subdivisions per dimension (default: 2)
- `overlap_buffer`: Buffer to add to each tile for connectivity (default: 0.001 degrees)

**Returns:**
- `G_transport`: Combined NetworkX graph
- `gdf_transport`: Combined GeoDataFrame

### Pipeline Functions

#### `pipeline_get_transport_network_subdivided(config, crs, str_transport_idx, complete_path_transport_gdf, complete_path_transport_graph, subdivision_factor=2, area_threshold=0.1, use_subdivision=None)`

Enhanced pipeline with automatic subdivision decision.

**Parameters:**
- `config`: Configuration dictionary with bbox coordinates
- `crs`: Target coordinate reference system
- `str_transport_idx`: Transport index column name
- `complete_path_transport_gdf`: Path to save/load GeoDataFrame
- `complete_path_transport_graph`: Path to save/load graph
- `subdivision_factor`: Number of subdivisions per dimension (default: 2)
- `area_threshold`: Area threshold above which subdivision is used (default: 0.1)
- `use_subdivision`: Force subdivision (True/False) or auto-decide (None)

## Usage Examples

### Basic Subdivided Extraction

```python
from PolygonRetrievialOsmnx import gdf_drive_from_coords_bbox_subdivided

# Extract driving network with 3x3 subdivision
G_drive, gdf_drive = gdf_drive_from_coords_bbox_subdivided(
    south=45.8, east=12.5, north=47.1, west=10.4,
    subdivision_factor=3,
    overlap_buffer=0.001
)

print(f"Extracted: {len(G_drive.nodes)} nodes, {len(G_drive.edges)} edges")
```

### Using Enhanced Pipeline

```python
from PolygonRetrievialOsmnx import pipeline_get_transport_network_subdivided

config = {
    "north": 47.1,
    "south": 45.8, 
    "east": 12.5,
    "west": 10.4
}

# Automatic subdivision based on area
gdf, G = pipeline_get_transport_network_subdivided(
    config=config,
    crs="EPSG:4326",
    str_transport_idx="transport_id",
    complete_path_transport_gdf="transport_network.geojson",
    complete_path_transport_graph="transport_network.graphml",
    subdivision_factor=2,
    area_threshold=0.05,  # Use subdivision if area > 0.05 sq degrees
    use_subdivision=None  # Auto-decide
)
```

### Backward Compatible Usage

```python
from PolygonRetrievialOsmnx import pipeline_get_transport_network

# Original function with subdivision option
gdf, G = pipeline_get_transport_network(
    config=config,
    crs="EPSG:4326", 
    str_transport_idx="transport_id",
    complete_path_transport_gdf="transport_network.geojson",
    complete_path_transport_graph="transport_network.graphml",
    use_subdivision=True,      # Enable subdivision
    subdivision_factor=3       # 3x3 tiles
)
```

## Performance Considerations

### When to Use Subdivision

**Use subdivision for:**
- Large geographic areas (> 0.1 square degrees)
- Areas with dense road networks
- When encountering memory or timeout issues
- Distributed processing scenarios

**Use standard extraction for:**
- Small areas (< 0.05 square degrees)  
- Simple road networks
- When processing speed is critical
- Testing and development

### Subdivision Factor Guidelines

- **2x2 (4 tiles)**: Good for medium areas, minimal overhead
- **3x3 (9 tiles)**: Recommended for large areas 
- **4x4 (16 tiles)**: For very large areas or memory-constrained systems
- **Higher factors**: May introduce unnecessary overhead

### Overlap Buffer Guidelines

- **0.001 degrees (~100m)**: Default, good for most cases
- **0.0005 degrees (~50m)**: For dense urban areas
- **0.002 degrees (~200m)**: For rural areas with sparse networks

## Output Structure

The subdivided extraction produces the same output structure as standard OSMnx extraction:

### NetworkX Graph
- Nodes with coordinates and OSM attributes
- Edges with geometry and road network properties
- Preserved connectivity across tile boundaries

### GeoDataFrame  
- Edge geometries as LineString objects
- OSM attributes (highway type, name, etc.)
- Transport index column for integration
- Deduplicated edges from tile overlaps

## Integration with Existing Code

The subdivided functions are designed to be drop-in replacements:

```python
# Before: Standard extraction
G, gdf = gdf_drive_from_coords_bbox(south, east, north, west)

# After: Subdivided extraction  
G, gdf = gdf_drive_from_coords_bbox_subdivided(south, east, north, west)
```

The output format and structure remain identical, ensuring compatibility with existing analysis pipelines.

## Error Handling

The subdivision approach includes robust error handling:

- **Individual tile failures**: Continue processing other tiles
- **Network merge errors**: Graceful fallback and logging  
- **Empty tile handling**: Skip tiles with no network data
- **Validation checks**: Ensure valid merged networks

## Logging and Monitoring

Detailed logging provides visibility into the extraction process:

```
INFO - Extracting driving network from area: 0.520000 deg² using 3x3 subdivision
INFO - Processing tile 1/9: bounds=(45.8000, 12.5000, 46.0333, 10.4000)
INFO - Tile 1: extracted 1247 edges
...
INFO - Merging 9 graphs from subdivided extraction
INFO - Final network: 3456 nodes, 8901 edges
```

## Dependencies

The subdivided extraction requires the same dependencies as standard OSMnx extraction:

- `osmnx`: OpenStreetMap network extraction
- `networkx`: Graph manipulation and merging
- `geopandas`: Spatial data handling
- `shapely`: Geometric operations
- `pandas`: Data frame operations

## Future Enhancements

Potential improvements to the subdivided extraction:

1. **Parallel Processing**: Extract tiles in parallel for faster processing
2. **Adaptive Subdivision**: Automatically adjust subdivision based on network density
3. **Caching**: Cache individual tiles for reuse across different extractions
4. **Progress Tracking**: Enhanced progress reporting for long-running extractions
5. **Network Validation**: Additional checks for network connectivity and completeness
