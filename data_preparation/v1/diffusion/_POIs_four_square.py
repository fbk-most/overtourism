"""
    Disclaimer: ##### NOT USED IN THE PROJECT #####
    NOTE: This script is designed to retrieve Points of Interest (POIs) from the Foursquare API
    Within the project of AIXPA Overtourism Analysis is not used
"""

import requests

def get_pois_from_foursquare(client_id, client_secret, bbox, category=None, limit=50):
    """
    Retrieve POIs from Foursquare within a bounding box.
    
    Parameters:
        client_id (str): Foursquare API client ID.
        client_secret (str): Foursquare API client secret.
        bbox (tuple): Bounding box as (minx, miny, maxx, maxy).
        category (str): Optional category to filter POIs (e.g., 'restaurant', 'park').
        limit (int): Maximum number of POIs to retrieve.
    
    Returns:
        pois (list): List of POIs with their details.
    """
    minx, miny, maxx, maxy = bbox
    url = "https://api.foursquare.com/v2/venues/search"
    
    # Define parameters for the API request
    params = {
        'client_id': client_id,
        'client_secret': client_secret,
        'v': '20230401',  # API version
        'intent': 'browse',
        'sw': f"{miny},{minx}",  # Southwest corner of the bounding box
        'ne': f"{maxy},{maxx}",  # Northeast corner of the bounding box
        'limit': limit
    }
    if category:
        params['query'] = category
    
    # Make the API request
    response = requests.get(url, params=params)
    data = response.json()
    
    # Extract POIs from the response
    pois = []
    if 'response' in data and 'venues' in data['response']:
        for venue in data['response']['venues']:
            pois.append({
                'name': venue.get('name'),
                'lat': venue['location'].get('lat'),
                'lon': venue['location'].get('lng'),
                'category': venue['categories'][0]['name'] if venue['categories'] else None
            })
    
    return pois