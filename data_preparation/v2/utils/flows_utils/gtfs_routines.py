import gtfs_kit as gk

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


