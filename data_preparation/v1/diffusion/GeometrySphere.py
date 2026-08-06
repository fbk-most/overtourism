"""
    This snippet is responsible of handling the geometry of the sphere.
"""

import numpy as np
from shapely.geometry import Point, Polygon
##---------------------------------- GEOMETRIC FEATURES ----------------------------------##
def ProjCoordsTangentSpace(lat,lon,lat0,lon0):
    '''
        Description:
            Projects in the tangent space of the earth in (lat0,lon0) 
        Return: 
            The projected coordinates of the lat,lon  
    '''
    PI = np.pi
    c_lat= 0.6*100000*(1.85533-0.006222*np.sin(lat0*PI/180))
    c_lon= c_lat*np.cos(lat0*PI/180)
    
    x = c_lon*(lon-lon0)
    y = c_lat*(lat-lat0)
    if isinstance(x,np.ndarray) or isinstance(x,np.float64):
        pass
    else:        
        x = x.to_numpy()
    if isinstance(y,np.ndarray) or isinstance(y,np.float64):
        pass
    else:
        y = y.to_numpy()
    return x,y

def from_tangent_space_to_latlon(x,y,lat0,lon0):
    '''
        Description:
            Projects from the tangent space of the earth in (lat0,lon0) to lat,lon
        Return: 
            The projected coordinates of the lat,lon  
    '''
    PI = np.pi
    c_lat= 0.6*100000*(1.85533-0.006222*np.sin(lat0*PI/180))
    c_lon= c_lat*np.cos(lat0*PI/180)
    
    lon = x/c_lon + lon0
    lat = y/c_lat + lat0
    return lat,lon


def ComputeAreaSquare(geometry):
    """
        Description:
            Compute the area of a square in square meters.
    """
    x,y = geometry.centroid.xy
    lat0 = x[0]
    lon0 = y[0]
    # Extract the coordinates from the Polygon's exterior
    latlon = np.array([[p[0],p[1]] for p in geometry.exterior.coords]).T
    lat = latlon[0]
    lon = latlon[1]
    # Ensure the last coordinate is the same as the first to close the polygon
    x,y = ProjCoordsTangentSpace(lat,lon,lat0,lon0)
    area = np.sqrt((x[1] - x[0])**2 + (y[1] - y[0])**2)*np.sqrt((x[2] - x[1])**2 + (y[2] - y[1])**2)/1000000
    return area

def choose_closest_point(principal_point: list,
                         idx_point_2_point: dict):
    assert len(principal_point) == 2, "principal_point should be a list of two elements"
    min_distance = np.inf
    proj_principal = ProjCoordsTangentSpace(principal_point[0],principal_point[1],principal_point[0],principal_point[1])
    for idx_point, point in idx_point_2_point.items():
        proj_point = ProjCoordsTangentSpace(point[0],point[1],principal_point[0],principal_point[1])
        diff = np.array([proj_point[0] - proj_principal[0], proj_point[1] - proj_principal[1]])
        dist = np.linalg.norm(diff)
        if dist < min_distance:
            min_distance = dist
            idx_closest_point = idx_point
    return idx_closest_point


def compute_area_geom_km2(gdf,
                        crs_proj = "EPSG:3857"):
    return gdf.to_crs(crs_proj).geometry.area/1000000


def polar_coordinates(point, center):
    # Calculate r    
    if isinstance(point,Point):
        point = np.array(point.coords)[0]
    else:
        pass
    y = point[1] - center[1]#ProjCoordsTangentSpace(center[0],center[1],point[0],point[1])
    x = point[0] - center[0]
    r = np.sqrt(x**2 + y**2)/1000
    theta = np.arctan(y/x)
    return r, theta


## ------------------- BOUNDARY FROM SHAPEFILE OR GEODATAFRAME ------------------- ##

def extract_bbox_from_shapefile(shapefile_path):
    """
    Extract bounding box coordinates from a shapefile.
    
    Parameters:
    -----------
    shapefile_path : str
        Path to the shapefile
        
    Returns:
    --------
    dict
        Dictionary containing south, east, north, west coordinates
    """
    import geopandas as gpd
    
    # Load the shapefile
    gdf = gpd.read_file(shapefile_path)
    
    # Get the total bounds of all polygons
    minx, miny, maxx, maxy = gdf.total_bounds
    
    # Assign to standard bbox variables
    south = miny
    east = maxx
    north = maxy
    west = minx
    
    return {
        "south": south,
        "east": east,
        "north": north,
        "west": west
    }

def extract_bbox_from_geodataframe(gdf):
    """
    Extract bounding box coordinates from a GeoDataFrame.
    
    Parameters:
    -----------
    gdf : gpd.GeoDataFrame
        GeoDataFrame containing polygons
        
    Returns:
    --------
    dict
        Dictionary containing south, east, north, west coordinates
    """
    # Get the total bounds of all polygons
    minx, miny, maxx, maxy = gdf.total_bounds
    
    # Assign to standard bbox variables
    south = miny
    east = maxx
    north = maxy
    west = minx
    
    return {
        "south": south,
        "east": east,
        "north": north,
        "west": west
    }

# Example 4: With buffer (expand bbox by certain distance)
def extract_bbox_with_buffer(gdf, buffer_degrees=0.01):
    """
    Extract bounding box with buffer around the edges.
    
    Parameters:
    -----------
    gdf : gpd.GeoDataFrame
        GeoDataFrame containing polygons
    buffer_degrees : float
        Buffer distance in degrees (for geographic CRS)
        
    Returns:
    --------
    dict
        Dictionary containing buffered south, east, north, west coordinates
    """
    minx, miny, maxx, maxy = gdf.total_bounds
    
    return {
        "south": miny - buffer_degrees,
        "east": maxx + buffer_degrees,
        "north": maxy + buffer_degrees,
        "west": minx - buffer_degrees
    }

