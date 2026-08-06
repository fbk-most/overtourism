
import os
import sys
import pandas as pd
import geopandas as gpd
import io
import boto3
import polars as pl

from data_preparation.utils import DATA_PREFIX, BASE_DIR

BaseDir = BASE_DIR



def IfExistsOpenDf(InputFile,Separator = ","):
    """
        Return the DataFrame at Position BaseDir,InputFile and Boolean success 
    """
    File = os.path.join(BaseDir,InputFile)
    if os.path.isfile(File):
        return pd.read_csv(File,Separator),True
    else:
        return None,False

def IfExistsOpenGdf(InputFile):
    """
        Return the DataFrame at Position BaseDir,InputFile and Boolean success 
    """
    File = os.path.join(BaseDir,InputFile)
    if os.path.isfile(File):
        return gpd.read_file(File),True
    else:
        return None,False
    
def JoinCompletePathFromBaseFile(CompletePath,FileInput):
    return os.path.join(CompletePath,FileInput)
    

    
def BuildCompletePathFromBaseDir(ListBranchFolder):
    """
        Input:
            ListBranchFolder: list -> Branching the BaseDir; Example: ListBranchFolder = [level0,level1] ->/BaseDir/level0/level1
        NOTE:
            Handles the case in which the user gives a string in input.
    """
    CompleteFolder = BaseDir
    try:
        if len(ListBranchFolder)>0:
            for Level in ListBranchFolder:
                if type(Level) == str:
                    CompleteFolder = os.path.join(CompleteFolder,Level)
                else:
                    CompleteFolder = os.path.join(CompleteFolder,str(Level))
    except:
        if type(ListBranchFolder) == str:
            CompleteFolder = os.path.join(CompleteFolder,ListBranchFolder)
        else:
            CompleteFolder = os.path.join(CompleteFolder,str(ListBranchFolder))
    os.makedirs(CompleteFolder,exist_ok = True)
    return CompleteFolder


                    
def SaveGeopandas(Gdf,CompletePathSaveFile):
    Gdf.to_file(CompletePathSaveFile)
    
def SavePandas(Df,CompletePathSaveFile):
    Df.reset_index(drop=True).to_csv(CompletePathSaveFile, index=False)


## ------------- JSON Interface for Data Lake ------------- ##
import numpy as np
def make_json_serializable(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    return obj

## ---------- DHCLI Interface for Data Lake ---------- ##

def extract_filenames_and_date_from_bucket(bucket):
    """
        Extract filenames and dates from the S3 bucket.
        Returns a dictionary with keys 'od' and 'presenze' containing filenames indexed by date.
        NOTE The dataset we have -> pay attention that other files of this kind may exist in the bucket.:
        - Available dates: ['202407', '202408', '202410']
        - OD files: ['.../vodafone-aixpa/od-mask_01_202407.parquet',
                '.../vodafone-aixpa/od-mask_01_202408.parquet', 
                '.../vodafone-aixpa/od-mask_01_202410.parquet']
        - Presenze files: ['.../vodafone-aixpa/presenze-mask_02-202407.parquet',
                        '.../vodafone-aixpa/presenze-mask_02-202408.parquet',
                        '.../vodafone-aixpa/presenze-mask_02-202410.parquet']
        Returns:
            list_files_od: List of OD files ordered by date.
            list_files_presenze: List of Presenze files ordered by date.
            list_str_dates: List of dates corresponding to the files in 'yyyymm' format.
    """

    list_files_od = []
    list_files_presenze = []
    list_str_dates = []

    # Collect files and dates
    file_info = {'od': {}, 'presenze': {}}

    for obj in bucket.objects.filter(Prefix=f'{DATA_PREFIX}vodafone-aixpa'):
        # NOTE: choose just parquet files -> od-mask, presenze-mask 
        if obj.key.endswith('.parquet'):
            if "od-mask" in obj.key and "01" not in obj.key:
    #            print(obj.key.split('/')[-1].split('_')[2].split(".")[0])#.split('_')[0])#.split("-")#[1].split(".")[0])
    #            date_str = obj.key.split('/')[-1].split('_')[2].split(".")[0]  # Extract date from the filename yyyymm
                date_str = obj.key.split('/')[-1].split('_')[1].split(".")[0]  # Extract date from the filename yyyymm
                file_info['od'][date_str] = obj.key
            elif "presenze-mask" in obj.key and "01" not in obj.key:
                print(obj.key.split('/')[-1].split('_')[1].split("-")[1].split(".")[0])
                date_str = obj.key.split('/')[-1].split('_')[1].split("-")[1].split(".")[0]
                file_info['presenze'][date_str] = obj.key

    # Find common dates between od and presenze files
    common_dates = set(file_info['od'].keys()) & set(file_info['presenze'].keys())

    # Sort dates to ensure consistent ordering
    sorted_dates = sorted(list(common_dates))

    # Create ordered lists
    for date_str in sorted_dates:
        list_files_od.append(file_info['od'][date_str])
        list_files_presenze.append(file_info['presenze'][date_str])
        list_str_dates.append(date_str)

    return list_files_od, list_files_presenze, list_str_dates


def extract_presences_vodafone_from_bucket(s3,list_files_presenze:list[str], i:int) -> pl.DataFrame:
    """
        Extract presences data from the Vodafone bucket.
    """
    print(f"Extracting presenze data from file {list_files_presenze[i]}")                                                                                                  # print the file name
    object_presenze = s3.Object('datalake', list_files_presenze[i])                                                                                                      # NOTE: download the file from the bucket
    buffer=io.BytesIO()
    object_presenze.download_fileobj(buffer)
    df_presenze = pl.read_parquet(buffer)
    return df_presenze

def extract_od_vodafone_from_bucket(s3,list_files_od:list[str], i:int) -> pl.DataFrame:
    """
        Extract OD data from the Vodafone bucket.
    """
    print(f"Extracting OD data from file {list_files_od[i]}")                                                                                                              # print the file name
    object_od = s3.Object('datalake', list_files_od[i])                                                                                                                  # NOTE: download the file from the bucket
    buffer=io.BytesIO()
    object_od.download_fileobj(buffer)
    df_od = pl.read_parquet(buffer)
    return df_od


## -------------------- PRESENZE MARKOWITZ -------------------- ##


from typing import List
def merge_flows_and_grid_with_global_to_obtain_unique_dfs(global_Tij_holding_all_columns_flows: pl.DataFrame | pd.DataFrame | None,
                                                          flows_2_be_merged: pl.DataFrame | pd.DataFrame,
                                                          global_cities_gdf_holding_all_columns_flows: gpd.GeoDataFrame | pd.DataFrame,
                                                          grid_single_case_2_be_merged: gpd.GeoDataFrame,
                                                          columns_join_global_geopandas:List[str],
                                                          columns_flows_2_be_merged_2_keep:List[str],
                                                          on_columns_flows_2_join:List[str], 
                                                          on_columns_grid_2_join:List[str],
                                                          message_geojson: str,
                                                          message_flows: str,
                                                          is_join_flows: bool = True,
                                                          is_join_grid: bool = True
                                                          ):
    """
        Merge flows and grid with global datasets to obtain unique DataFrames.
    """
    if is_join_flows:
        if global_Tij_holding_all_columns_flows is None:
            global_Tij_holding_all_columns_flows = flows_2_be_merged
        else:
            print(f"Joining flows ... {message_flows}")
            print(f" - n flows before join: {len(global_Tij_holding_all_columns_flows)}")
            global_Tij_holding_all_columns_flows = global_Tij_holding_all_columns_flows.join(flows_2_be_merged[columns_flows_2_be_merged_2_keep],
                                                                                            on=on_columns_flows_2_join, 
                                                                                            how="left")
            print(f" - n flows after join: {len(global_Tij_holding_all_columns_flows)}")
    if is_join_grid:
        print(f"Joining geojson ... {message_geojson}")
        print(f" - n grid before join: {len(global_cities_gdf_holding_all_columns_flows)}")
        # Use merge instead of join for more explicit control over join keys
        global_cities_gdf_holding_all_columns_flows = global_cities_gdf_holding_all_columns_flows.merge(
            grid_single_case_2_be_merged[columns_join_global_geopandas], 
            on=on_columns_grid_2_join,
            how="left",
            suffixes=("", "_right") # Add suffix to handle potential duplicate columns
        )
        # Drop duplicate columns that may have been added from the merge
        cols_to_drop = [col for col in global_cities_gdf_holding_all_columns_flows.columns if col.endswith('_right')]
        if cols_to_drop:
            global_cities_gdf_holding_all_columns_flows = global_cities_gdf_holding_all_columns_flows.drop(columns=cols_to_drop) 
        print(f" - n grid after join: {len(global_cities_gdf_holding_all_columns_flows)}")
    return global_Tij_holding_all_columns_flows, global_cities_gdf_holding_all_columns_flows