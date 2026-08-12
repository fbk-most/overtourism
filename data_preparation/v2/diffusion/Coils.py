from geopandas import GeoDataFrame, points_from_xy
def pipeline_initialize_coils(dh,int_crs = 4326):
    """
    @description:
        1- Initialize the pipeline for coils data processing.
        2- transform the dataframe into a GeoDataFrame. (the geometry are the coordinates of the coils)
    @return:
        - gdf: GeoDataFrame with the coils data.  
        columns:
        '': int -> index
        'data': str -> %YY-%MM-%DD %HH:%MM:%SS 
        'sensore': str ->
        'direzione': int -> 0,1,2,3
        'comune': str -> comune
        'cl1': int -> count of vehicles in class 1
        'cl2': int -> count of vehicles in class 2
        'cl3': int -> count of vehicles in class 3
        'cl4': int -> count of vehicles in class 4
        'cl5': int -> count of vehicles in class 5
        'cl6': int -> count of vehicles in class 6
        'cl7': int -> count of vehicles in class 7
        'nonrilevato': int -> no idea of the class of the vehicle
        'direzione': int -> 0,1,2,3
        'descrizione_direzione': str -> description of the direction (Molveno verso Spiaggia...)
        'date_dt': datetime -> date and time of the data
        'geometry': Point -> geometry of the coils (coordinates)
        'aggregated_count': int -> sum of all the classes (cl1 + cl2 + cl3 + cl4 + cl5 + cl6 + cl7 + nonrilevato)
    """
    dh.contamezzi_df = dh.contamezzi_df.join(dh.contamezzi_descrizione_sensore_df, on='sensore', how='left')
    dh.CastDataFramesDate()
    gdf = GeoDataFrame(dh.contamezzi_df.to_pandas(), geometry=points_from_xy(dh.contamezzi_df["longitudine"],dh.contamezzi_df["latitudine"]),crs =int_crs)
    gdf.drop(columns=["longitudine", "latitudine","_right"], inplace=True)
    gdf.rename(columns={"direzione_right":"direzione"}, inplace=True)
    gdf["aggregated_count"] = gdf.apply(lambda x: x["cl1"] + x["cl2"] + x["cl3"] + x["cl4"] + x["cl5"] + x["cl6"] + x["cl7"] + x["nonrilevato"],axis=1)

    return gdf