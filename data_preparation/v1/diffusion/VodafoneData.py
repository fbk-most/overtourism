import re
import polars as pl
import pandas as pd
from datetime import timedelta, date

from data_preparation.diffusion.OsAndFileHandling import extract_od_vodafone_from_bucket, extract_presences_vodafone_from_bucket
from data_preparation.diffusion.constant_names_variables import date_in_file_2_skip

## Diffusione 1,2 -> extract days ###############


def extract_date_info(period_id,is_match_version=True):
    """
    Extract date and weekday info from PERIOD_ID format like '202407 01-15 - Feriale'
    Returns middle date of the period and whether it's a weekday
    """
    if is_match_version:
        # Parse the period_id
        match = re.match(r'(\d{6})\s+(\d{2})-(\d{2})\s+-\s+(.*)', period_id)
        if match:
            year_month = match.group(1)  # e.g., '202407'
            start_day = int(match.group(2))  # e.g., 1 or 16
            end_day = int(match.group(3))    # e.g., 15 or 31
            day_type = match.group(4).strip()  # e.g., 'Feriale', 'Festivo', 'Prefestivo'
            
            # Extract year and month
            year = int(year_month[:4])
            month = int(year_month[4:])
            
            # Use middle day of the period
            middle_day = (start_day + end_day) // 2
            
            # Create date string
            date_str = f"{year:04d}-{month:02d}-{middle_day:02d}"
            
            # Determine if it's a weekday
            # Return the day_type as string: "Feriale", "Prefestivo", "Festivo"
            is_weekday = day_type
            
            return date_str, is_weekday
        else:
            return None, None
    



def extract_date_and_weekday_case_null_day(period_id_str):
    """Extract date and weekday status from period_id string"""
    try:
        # Split the period_id string
        parts = period_id_str.split(" - ")
        
        if len(parts) != 2:
            return None, None
        
        date_part = parts[0].strip()  # e.g., "202410"
        day_type = parts[1].strip()   # e.g., "Feriale", "Prefestive", "Festive"
        
        # Extract year and month
        if len(date_part) == 6:
            year = date_part[:4]
            month = date_part[4:6]
            
            # Create date string in YYYY-MM-DD format (always use 01 as day)
            str_day = f"{year}-{month}-01"
            
            # Determine if it's a weekday
            # Return the day_type as string: "Feriale", "Prefestivo", "Festivo"
            is_weekday = day_type
            
            return str_day, is_weekday
        else:
            return None, None
            
    except Exception as e:
        print(f"Error processing period_id '{period_id_str}': {e}")
        return None, None



## --------------------------------
def concat_presences(list_files_presences, s3, col_str_day_od, col_period_id = "PERIOD_ID"):
    """ 
        Concatenate presences from multiple files, skipping files with '202410' in their name 
    """
    for i,file_presences in enumerate(list_files_presences):
        if "202410" in file_presences:
            continue
        else:
            df_presenze = extract_presences_vodafone_from_bucket(s3, list_files_presences, i) 
            df_presenze = add_column_str_day_presenze(df_presenze, col_period_id, col_str_day_od)
            if i == 0:                                                                                                     # NOTE: download the file from the bucket
                stack_df_presenze = df_presenze
            else:
                stack_df_presenze = pl.concat([stack_df_presenze, df_presenze], how="vertical")
    return stack_df_presenze


def add_column_is_week_and_str_day(df_od: pd.DataFrame | pl.DataFrame,
                                  str_period_id_presenze: str,
                                  col_str_day_od: str,
                                  col_str_is_week: str,
                                  is_null_day:bool = False) -> pd.DataFrame | pl.DataFrame:
    """
        Goal: Add two columns to the dataframe:
            - col_str_day_od: day of the trip (yyyy-mm-dd)
            - col_str_is_week: is the day a weekday?
        Input:
            df_od: DataFrame with OD data
            str_period_id_presenze: column with the period id (yyyymmdd)
            col_str_day_od: column with the day of the trip (yyyy-mm-dd)
            col_str_is_week: column with the is_weekday
        Output:
            df_od: DataFrame with the new columns
        NOTE: In the main Diffusione 1,2: this function is used to choose the days of the analysis.
            It is important since we cannot choose the days of the analysis from the presenze since
            they are much richer than OD data.
    """
    if isinstance(df_od, pd.DataFrame):
        df_od = pl.from_pandas(df_od)  # Convert to Polars DataFrame if it's a Pandas DataFrame
    else:
        pass
    if is_null_day:
        # Apply the function to extract both values
        df_od = df_od.with_columns([
            # Extract date
            pl.col(str_period_id_presenze).map_elements(
                lambda x: extract_date_and_weekday_case_null_day(x)[0] if x is not None else None,
                return_dtype=pl.Utf8
            ).alias(col_str_day_od),
            
            # Extract weekday status
            pl.col(str_period_id_presenze).map_elements(
                lambda x: extract_date_and_weekday_case_null_day(x)[1] if x is not None else None,
                return_dtype=pl.Utf8
            ).alias(col_str_is_week)
        ])
        return df_od
    else:        
        df_od = df_od.with_columns([
            pl.col(str_period_id_presenze).map_elements(
                lambda x: extract_date_info(x)[0] if extract_date_info(x) is not None else None, 
                return_dtype=pl.Utf8
            ).alias(col_str_day_od),
            pl.col(str_period_id_presenze).map_elements(
                lambda x: extract_date_info(x)[1] if extract_date_info(x) is not None else None, 
                return_dtype=pl.Utf8
            ).alias(col_str_is_week)
        ])
    
    return df_od

def add_holiday_columun_df_presenze(stack_df_presenze: pl.DataFrame, 
                                    col_str_day_od: str,
                                    public_holidays: set[date],
                                    col_str_is_week: str) -> pl.DataFrame:
    """
    Add a column to the DataFrame classifying each day as "Feriale", "Prefestivo", or "Festivo".
    Parameters:
    - stack_df_presenze: Input DataFrame containing a column with date strings.
    - col_str_day_od: Name of the column in stack_df_presenze containing date strings in "YYYY-MM-DD" format.
    - public_holidays: A set of datetime.date objects representing public holidays.
    Returns:
    - Updated DataFrame with an additional column "is_weekday" classifying each day.
    """
    # Add classification column based on day_parsed
    stack_df_presenze = stack_df_presenze.with_columns([
        # Parse str_day into a proper Date column
        pl.col(col_str_day_od).str.strptime(pl.Date, format="%Y-%m-%d").alias("day_parsed")
    ])
    stack_df_presenze = stack_df_presenze.with_columns([
        pl.when(
            (pl.col("day_parsed").dt.weekday() >= 5) | pl.col("day_parsed").is_in(public_holidays)
        ).then(pl.lit("Festivo"))
        .when(
            (pl.col("day_parsed").dt.weekday() == 4)
            | (pl.col("day_parsed") + timedelta(days=1)).is_in(public_holidays)
        ).then(pl.lit("Prefestivo"))
        .otherwise(pl.lit("Feriale"))
        .alias(col_str_is_week)
    ])

    # Drop the temporary parsed column
    stack_df_presenze = stack_df_presenze.drop("day_parsed")
    return stack_df_presenze

def add_is_weekday_from_period_presenze_null_days(df: pl.DataFrame, period_col: str = "PERIOD_ID",is_weekday_col:str = "is_weekday") -> pl.DataFrame:
    """
    Extract 'Feriale', 'Festivo', or 'Prefestivo' from PERIOD_ID and store in 'is_weekday'.

    Parameters
    ----------
    df : pl.DataFrame
        Input Polars DataFrame
    period_col : str
        Column containing strings like "202410 - Feriale" or "202410 - Prefestivo"

    Returns
    -------
    pl.DataFrame
        New DataFrame with added column 'is_weekday'
    """
    return df.with_columns([
        pl.col(period_col)
        .str.extract(r"(Feriale|Festivo|Prefestivo)$", 1)  # extract last word
        .alias(is_weekday_col)
    ])



def extract_all_days_available_analysis_flows_from_raw_dataset(list_files_od,col_str_day_od,str_period_id_presenze,col_str_is_week,s3):
    """
        Extract all unique days available for analysis flows from the raw dataset.
        Args:
            list_files_od (list): List of OD files.
            col_str_day_od (str): Column name for the day in the OD data.
            str_period_id_presenze (str): Period ID for presences.
            col_str_is_week (str): Column name indicating if it's a week.
            s3: S3 client for accessing the bucket.
        Returns:
            list_all_days_available_analysis_flows (list): List of all unique days available for analysis flows.
    """
    list_all_days_available_analysis_flows = []
    for i,file in enumerate(list_files_od):
        df_od = extract_od_vodafone_from_bucket(s3,list_files_od, i) 
        df_od = add_column_is_week_and_str_day(df_od = df_od,
                                        str_period_id_presenze = str_period_id_presenze,
                                        col_str_day_od = col_str_day_od,
                                        col_str_is_week = col_str_is_week,
                                        is_null_day = False)  
        list_unique_days_od = df_od[col_str_day_od].unique().to_list()
        # NOTE: Do not consider the error files if they are found in the date_in_file_2_skip dictionary
        try:
            date_in_file_2_skip.get(file, [])
            list_unique_days_od = [day for day in list_unique_days_od if day not in date_in_file_2_skip.get(file, [])]
        except:
            pass
        list_all_days_available_analysis_flows.extend(list_unique_days_od)
    return list_all_days_available_analysis_flows



## ----------------- PRESENZE MARKOWITZ ANALYSIS ----------------- ##
def convert_yyyymmdd_to_yyyy_mm_dd(date_str):
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

def add_column_str_day_presenze(df_presenze, col_period_id, col_str_day):
    # Add the column col_str_day that is obtained from col_period_id by converting YYYYMMDD to YYYY-MM-DD using polars, noting that polars has not apply method
    df_presenze = df_presenze.with_columns(
        pl.col(col_period_id).map_elements(convert_yyyymmdd_to_yyyy_mm_dd,
                                           return_dtype=pl.Utf8).alias(col_str_day)
    )
    return df_presenze


