import gtfs_kit as gk
from data_preparation.diffusion.BusStops import *

def Preprocessing_gtfs(complete_path_gtfs):
    """
        Function to preprocess the GTFS data in a unique way cleaning the feed
        @params complete_path_gtfs: path to the GTFS zip file
        -1 read the feed from file.
        -2 drop stops with no stop times
        -3 drop undefined parent stations
        -4 drop trips with no stop times
        -5 drop shapes with no trips
        -6 drop routes with no trips
        -7 drop services with no trips
        -8 substitute white spaces in ids with _
        -9 drop missing route short names and strip whitespace from route short names
        -10 convert H:MM:SS -> HH:MM:SS

    """
    feed = gk.read_feed(complete_path_gtfs, dist_units='m')
    # clean ids, times, route short names, zombies
    feed = gk.cleaners.clean(feed)
    # append dist and stop times
    feed = feed.append_dist_to_stop_times()
    return feed


def compute_routes_trips(feed, 
                         str_day, 
                         time_vector_OD, 
                         config, 
                         str_prefix_complete_path,
                         str_name_gdf_stops,
                         str_trip_idx = "trip_id"
                         ):
    """

    """
    gdf_stops = pipeline_get_gdf_stop(feed.stops,
                                    config[f"{str_prefix_complete_path}_{str_name_gdf_stops}"]) 
    # NOTE: Trips and Routes stats -> compute the trips and routes stats from the feed, save it in the output folder
    print("Computing trips stats...")                                                                                                          # compute the trips stats from the feed
    trip_stats =  gk.trips.compute_trip_stats(feed = feed,                                                                  #
                                            route_ids = feed.routes.route_id.values,                                        #
                                            compute_dist_from_shapes = False)                                               # compute the trip stats from the feed, save it in the output folder                 
    # Compute Routes stats: -> informations about how many routes are in the network                                        #
    print("Computing routes stats...")                                                                                      #
    routes_stats = gk.routes.compute_route_stats(feed = feed,                                                               #
                                                trip_stats_subset = trip_stats,                                             #
                                                dates = [str_day],                                                             #
                                                headway_start_time = config["start_time_window_interest"],                  #
                                                headway_end_time = config["end_time_window_interest"],                      #
                                                split_directions = True)                                                    #
    
    # NOTE: Filter trips ->  chooses the trips that have a point whose end is inside the interval of interest (Like Vodafone definition of OD)
    trips_in_time_interval = filter_trips_by_time(trip_stats, 
                                                time_vector_OD, 
                                                str_trip_idx,
                                                end_time_col="end_time",
                                                start_time_col="start_time")
    stop_times_in_time_interval = filter_stop_times_by_time(feed.stop_times, 
                                                        time_vector_OD[0], 
                                                        time_vector_OD[1], 
                                                        str_trip_idx,
                                                        end_time_col="departure_time")                                                                                                             # compute the gdf stops from the stops, geometry are points
    
    # Memory management: Clear large GTFS datasets after processing
    del trip_stats, routes_stats
    return gdf_stops, trips_in_time_interval, stop_times_in_time_interval
