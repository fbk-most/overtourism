"""
ShapeFiles - Municipality Boundary and Centroid Extraction Module

This module provides utilities for extracting municipality boundaries and centroids from 
OpenStreetMap data using OSMnx geocoding. It specifically handles Vodafone dataset city 
names from the Trentino-Alto Adige region, with special preprocessing for problematic 
or ambiguous city names.

Main Components:

1. CITY NAME PREPROCESSING:
   - Standardization of compound city names (e.g., "City + District")
   - Special case handling for ambiguous names (Male, Ala, etc.)
   - Automatic province/region addition for better geocoding accuracy
   - Support for historical name changes and municipal reorganizations

2. BOUNDARY EXTRACTION:
   - OSMnx-based geocoding and polygon retrieval
   - Multi-polygon handling and geometry union operations
   - Coordinate system transformations and CRS management
   - Error handling for failed geocoding attempts

3. CENTROID CALCULATION:
   - Geographic centroid computation from polygon boundaries
   - Proper handling of multipolygon geometries
   - Latitude/longitude extraction in WGS84 coordinates
   - Separate centroid GeoDataFrame generation

Key Functions:

preprocess_city_name():
    Cleans and standardizes city names for improved geocoding success.
    Handles special cases specific to Trentino region municipalities.

extract_cities_boundaries_and_areas():
    Core function that retrieves city boundaries from OSM using geocoding.
    Computes centroids and handles coordinate system transformations.

pipeline_extract_boundary_and_centroid_gdf_from_name_comuni():
    Complete pipeline for boundary and centroid extraction with caching.
    Handles file existence checks and automatic GeoJSON export.

Special Cases Handled:
- "Malè" → "Malè, Trentino-Alto Adige" (disambiguation)
- "Ala" → "Ala, Trentino-Alto Adige" (common name conflict)
- "Vigo Di Fassa" → "Sen Jan di Fassa" (municipal merger 2018)
- Compound names with "+" separators
- Province/region addition for unqualified names

Output Structure:
- Municipality boundaries as polygon geometries
- Centroid coordinates (lat/lon) for each municipality  
- Separate centroids GeoDataFrame for point-based analysis
- GeoJSON export for external use and caching

Integration:
- Works with Vodafone DataLake city name lists
- Supports mobility analysis grid generation
- Compatible with tourism flow analysis pipelines
- Handles caching to avoid repeated OSM API calls

Dependencies: geopandas, osmnx, shapely, pandas
Data Source: OpenStreetMap via OSMnx geocoding API
Region Focus: Trentino-Alto Adige, Italy
Author: Alberto Amaduzzi
"""
from geopandas import GeoDataFrame, read_file
from osmnx import geocode_to_gdf
from shapely.geometry import Point
from pandas import concat
from data_preparation.diffusion.Plots_geopandas import plot_shapes_comuni_with_names
from os.path import exists


# Handling the names of the city -> NOTE: 
def preprocess_city_name(city_name):
    """
    Clean and standardize city names for better geocoding results.
    
    Parameters:
        city_name (str): Original city name
    
    Returns:
        str: Processed city name
    """
    original_name = city_name
    
    # Handle compound names with '+'
    if " + " in city_name:
        # Take just the first part for geocoding
        city_name = city_name.split(" + ")[0]
    
    # Special cases that need explicit handling
    special_cases = {
        "Male": "Malè, Trentino-Alto Adige",
        "Ala": "Ala, Trentino-Alto Adige",
        "Vigo Di Fassa": "Sen Jan di Fassa, Trentino-Alto Adige",  # New name since 2018
        "Soraga": "Soraga di Fassa, Trentino-Alto Adige",
        "Fai Della Paganella": "Fai della Paganella, Trentino-Alto Adige"
    }
    
    if city_name in special_cases:
        return special_cases[city_name]
    
    # Add province for better geocoding if not already present
    if not any(x in city_name.lower() for x in [", italy", ", trentino", ", alto adige"]):
        city_name += ", Trentino-Alto Adige, Italy"
        
    print(f"Converted '{original_name}' to '{city_name}'")
    return city_name

def extract_cities_boundaries_and_areas(city_names,
                                        str_centroid_lat_col = "centroid_lat",
                                        str_centroid_lon_col = "centroid_lon",
                                        str_city_name_col = "city_name",
                                        crs="EPSG:4326",
                                        output_file=None):
    """
    Extract city boundaries as polygons and compute their areas and centroids.
    
    Parameters:
        city_names (list): List of city names to extract boundaries for
        crs (str): Coordinate reference system (default: WGS84)
        output_file (str, optional): Path to save the results GeoDataFrame
    
    Returns:
        GeoDataFrame: Contains city boundaries, areas, and centroids
    """
    # Create empty GeoDataFrame to store results
    cities_gdf = GeoDataFrame(
        columns=[
            str_city_name_col, 'geometry', 
            str_centroid_lon_col, str_centroid_lat_col
        ], 
        geometry='geometry', 
        crs=crs
    )
    # Process each city
    for city in city_names:
        try:
            # Get the city boundary using OSMnx
            print(f"Processing {city}...")
            processed_city = preprocess_city_name(city)
            city_boundary = geocode_to_gdf(processed_city)
            
            # Convert to the specified CRS if it's not already
            if city_boundary.crs != crs:
                city_boundary = city_boundary.to_crs(crs)
            
            # Calculate centroid of the polygon boundary
            # Note: For proper centroid calculation, we should dissolve multipolygons first
            city_geom = city_boundary.geometry.union_all()
            centroid = city_geom.centroid
            
            # Extract coordinates
            centroid_lon = centroid.x  # Longitude (x)
            centroid_lat = centroid.y  # Latitude (y)
            
            # Add to the results GeoDataFrame
            new_row = GeoDataFrame({
                str_city_name_col: [city],
                'geometry': city_boundary.geometry.values[0],
                str_centroid_lon_col: centroid_lon,
                str_centroid_lat_col: centroid_lat
            }, geometry='geometry', crs=crs)
            
            cities_gdf = concat([cities_gdf, new_row], ignore_index=True)
            
            print(f"Successfully processed {city}:")
            print(f"  - Centroid: Lon={centroid_lon:.6f}, Lat={centroid_lat:.6f}")
            
        except Exception as e:
            print(f"Error processing {city}: {str(e)}")
            import traceback
            traceback.print_exc()
        
    # Save to file if output_file is provided
    if output_file and len(cities_gdf) > 0:
        cities_gdf.to_file(output_file)
        print(f"Results saved to {output_file}")
            
    return cities_gdf


def pipeline_extract_boundary_and_centroid_gdf_from_name_comuni(names_zones_to_consider,
                                                                complete_path_shape_gdf,
                                                                complete_path_centroid_gdf,
                                                                str_centroid_lat_col = "centroid_lat",
                                                                str_centroid_lon_col = "centroid_lon",
                                                                str_city_name_col = "city_name",
                                                                crs="EPSG:4326"):
    """
    Extracts the boundaries and centroids of specified city names.
    NOTE: The epsg:4326 defines the name of the columns of the geometries to be lat lon. 
    """  
    assert ".geojson" in complete_path_shape_gdf, "The path to the shape file must be a .geojson file"
    assert ".geojson" in complete_path_centroid_gdf, "The path to the centroid file must be a .geojson file"
    if exists (complete_path_shape_gdf) and exists (complete_path_centroid_gdf):
        cities_gdf = read_file(complete_path_shape_gdf)
        centroids_gdf = read_file(complete_path_centroid_gdf)
        print("The files already exist, please delete them to re-run the code")
        return centroids_gdf, cities_gdf
    # Extract boundaries and calculate centroids
    cities_gdf = extract_cities_boundaries_and_areas(
        names_zones_to_consider,
        crs = crs,
        output_file= complete_path_shape_gdf
    )
    
    if cities_gdf.empty:
        raise ValueError ("No cities were successfully processed.")
        
    
    # Display results
    print("\nSummary:")
    for idx, row in cities_gdf.iterrows():
        print(f"{row['city_name']}:")
    
    
    # Export centroids to a separate file
    geometry = [Point(lon, lat) for lon, lat in zip(cities_gdf['centroid_lon'], cities_gdf['centroid_lat'])]
    centroids_gdf = GeoDataFrame(
        {
            str_city_name_col: cities_gdf[str_city_name_col],
            str_centroid_lon_col: cities_gdf[str_centroid_lon_col],
            str_centroid_lat_col: cities_gdf[str_centroid_lat_col]
        },
        geometry=geometry,
        crs=cities_gdf.crs
    )


    centroids_gdf.to_file(complete_path_centroid_gdf, driver='GeoJSON')
    
    return centroids_gdf, cities_gdf



# Example usage: 
if __name__ == "__main__":
    from DataHandler import DataHandler
    import polars as pl
    dh = DataHandler()
    attendences_foreigners = dh.vodafone_attendences_df.join(dh.vodafone_aree_df, on='locId', how='left')
    names_zones_to_consider = attendences_foreigners.filter(pl.col("locName").is_in(["comune"])).unique("locDescr")["locDescr"].to_list()
    centroids_gdf,cities_gdf = pipeline_extract_boundary_and_centroid_gdf_from_name_comuni(names_zones_to_consider,complete_path_shape_gdf,complete_path_centroid_gdf)