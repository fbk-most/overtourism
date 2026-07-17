from numpy import zeros
from geopandas import sjoin
from data_preparation.diffusion.GeometrySphere import compute_area_geom_km2

def compute_intersection_among_geometries(Grid_intersected_cities,
                                          cities_gdf,
                                          str_area_intersection,
                                          str_grid_idx,
                                          str_city_name_idx,
                                          str_area_city,
                                          str_area_grid,
                                          str_fraction_intersection_area_city,
                                          str_fraction_intersection_area_grid,
                                          crs_proj = "EPSG:3857",
                                          crs = "EPSG:4326"):
    """
    Compute the intersection area between the grid and the cities.
    It is in general valid for any two g
    """
    assert str_area_intersection not in Grid_intersected_cities.columns, f"Column {str_area_intersection} already exists in the dataframe"
    assert str_grid_idx in Grid_intersected_cities.columns, f"Column {str_grid_idx} not found in the dataframe"
    assert str_city_name_idx in Grid_intersected_cities.columns, f"Column {str_city_name_idx} not found in the dataframe"
    assert str_area_city in Grid_intersected_cities.columns, f"Column {str_area_city} not found in the dataframe"
    assert str_area_grid in Grid_intersected_cities.columns, f"Column {str_area_grid} not found in the dataframe"
    assert str_fraction_intersection_area_city not in Grid_intersected_cities.columns, f"Column {str_fraction_intersection_area_city} already exists in the dataframe"
    assert str_fraction_intersection_area_grid not in Grid_intersected_cities.columns, f"Column {str_fraction_intersection_area_grid} already exists in the dataframe"
    # set crs
    Grid_intersected_cities = Grid_intersected_cities.to_crs(crs_proj)
    cities_gdf = cities_gdf.to_crs(crs_proj)
    # Compute the intersection area
    Grid_intersected_cities[str_area_intersection] = zeros(len(Grid_intersected_cities))
    for idx, grid_cell in Grid_intersected_cities.iterrows():
        idx_grid_intersected = grid_cell[str_grid_idx]
        # Get all cities that intersect this grid cell
        intersecting_cities = cities_gdf[cities_gdf.geometry.intersects(grid_cell.geometry)]
        for _, city in intersecting_cities.iterrows():
            # Calculate intersection
            intersection = grid_cell.geometry.intersection(city.geometry)
            # pick the index of the city intersected
            idx_city_intersected = city[str_city_name_idx]
            # assign the area of the intersection to the grid cell
            condition_idces_intersection = (Grid_intersected_cities[str_grid_idx] == idx_grid_intersected) & (Grid_intersected_cities[str_city_name_idx] == idx_city_intersected)
            # assign the area of the intersection to the grid cell
            Grid_intersected_cities.loc[condition_idces_intersection,str_area_intersection] = intersection.area/1000000
        
    # Compute the fraction of the intersection area over the city area
    Grid_intersected_cities[str_fraction_intersection_area_city] = Grid_intersected_cities[str_area_intersection] / Grid_intersected_cities[str_area_city]
    Grid_intersected_cities[str_fraction_intersection_area_grid] = Grid_intersected_cities[str_area_intersection] / Grid_intersected_cities[str_area_grid]
    Grid_intersected_cities[str_fraction_intersection_area_city] = [val if val < 1 else 1 for val in Grid_intersected_cities[str_fraction_intersection_area_city]]
    Grid_intersected_cities[str_fraction_intersection_area_grid] = [val if val < 1 else 1 for val in Grid_intersected_cities[str_fraction_intersection_area_grid]]
    Grid_intersected_cities.to_crs(crs,inplace = True)
    return Grid_intersected_cities


def intersect_Grid_2_polygons(Grid_gtfs,
                              cities_gdf,
                              crs = "EPSG:4326"):
    Grid_gtfs = Grid_gtfs.to_crs(crs)
    cities_gdf = cities_gdf.to_crs(crs)
    joined =  sjoin(Grid_gtfs,
           cities_gdf,
           how = "left",
          )
    joined = joined.drop(columns=["index_right"])
    return joined


def pipeline_intersect_grid_2_polygons(Grid_gtfs,
                                    cities_gdf,
                                    str_area_intersection,
                                    str_grid_idx,
                                    str_city_name_idx,
                                    str_area_city,
                                    str_area_grid,
                                    str_fraction_intersection_area_city,
                                    str_fraction_intersection_area_grid,
                                    crs_proj = "EPSG:3857",
                                    crs = "EPSG:4326"
                                    ):
    # Compute areas     
    cities_gdf[str_area_city] = compute_area_geom_km2(cities_gdf)
    Grid_gtfs[str_area_grid] = compute_area_geom_km2(Grid_gtfs)
    # Intersect grid and cities
    Grid_intersected_cities = intersect_Grid_2_polygons(Grid_gtfs,
                                cities_gdf)


    Grid_intersected_cities = compute_intersection_among_geometries(Grid_intersected_cities,
                                                                    cities_gdf,
                                                                    str_area_intersection,
                                                                    str_grid_idx,
                                                                    str_city_name_idx,
                                                                    str_area_city,
                                                                    str_area_grid,
                                                                    str_fraction_intersection_area_city,
                                                                    str_fraction_intersection_area_grid,
                                                                    crs_proj = crs_proj,
                                                                    crs = crs)
    return Grid_intersected_cities