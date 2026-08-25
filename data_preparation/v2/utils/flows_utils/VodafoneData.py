import pandas as pd
import polars as pl
import re
from data_preparation.v2.utils.flows_utils.OsAndFileHandling import (
    extract_od_vodafone_from_bucket,
)
from data_preparation.v2.utils.flows_utils.constant_names_variables import (
    date_in_file_2_skip,
)

## Diffusione 1,2 -> extract days ###############


def extract_date_info(period_id, is_match_version=True):
    """
    Extract date and weekday info from PERIOD_ID format like '202407 01-15 - Feriale'
    Returns middle date of the period and whether it's a weekday
    """
    if is_match_version:
        # Parse the period_id
        match = re.match(r"(\d{6})\s+(\d{2})-(\d{2})\s+-\s+(.*)", period_id)
        if match:
            year_month = match.group(1)  # e.g., '202407'
            start_day = int(match.group(2))  # e.g., 1 or 16
            end_day = int(match.group(3))  # e.g., 15 or 31
            day_type = match.group(
                4
            ).strip()  # e.g., 'Feriale', 'Festivo', 'Prefestivo'

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
        day_type = parts[1].strip()  # e.g., "Feriale", "Prefestive", "Festive"

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


def add_column_is_week_and_str_day(
    df_od: pd.DataFrame | pl.DataFrame,
    str_period_id_presenze: str,
    col_str_day_od: str,
    col_str_is_week: str,
    is_null_day: bool = False,
) -> pd.DataFrame | pl.DataFrame:
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
        df_od = pl.from_pandas(
            df_od
        )  # Convert to Polars DataFrame if it's a Pandas DataFrame
    else:
        pass
    if is_null_day:
        # Apply the function to extract both values
        df_od = df_od.with_columns(
            [
                # Extract date
                pl.col(str_period_id_presenze)
                .map_elements(
                    lambda x: (
                        extract_date_and_weekday_case_null_day(x)[0]
                        if x is not None
                        else None
                    ),
                    return_dtype=pl.Utf8,
                )
                .alias(col_str_day_od),
                # Extract weekday status
                pl.col(str_period_id_presenze)
                .map_elements(
                    lambda x: (
                        extract_date_and_weekday_case_null_day(x)[1]
                        if x is not None
                        else None
                    ),
                    return_dtype=pl.Utf8,
                )
                .alias(col_str_is_week),
            ]
        )
        return df_od
    else:
        df_od = df_od.with_columns(
            [
                pl.col(str_period_id_presenze)
                .map_elements(
                    lambda x: (
                        extract_date_info(x)[0]
                        if extract_date_info(x) is not None
                        else None
                    ),
                    return_dtype=pl.Utf8,
                )
                .alias(col_str_day_od),
                pl.col(str_period_id_presenze)
                .map_elements(
                    lambda x: (
                        extract_date_info(x)[1]
                        if extract_date_info(x) is not None
                        else None
                    ),
                    return_dtype=pl.Utf8,
                )
                .alias(col_str_is_week),
            ]
        )

    return df_od


def extract_all_days_available_analysis_flows_from_raw_dataset(
    list_files_od, col_str_day_od, str_period_id_presenze, col_str_is_week, s3
):
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
    for i, file in enumerate(list_files_od):
        df_od = extract_od_vodafone_from_bucket(s3, list_files_od, i)
        df_od = add_column_is_week_and_str_day(
            df_od=df_od,
            str_period_id_presenze=str_period_id_presenze,
            col_str_day_od=col_str_day_od,
            col_str_is_week=col_str_is_week,
            is_null_day=False,
        )
        list_unique_days_od = df_od[col_str_day_od].unique().to_list()
        # NOTE: Do not consider the error files if they are found in the date_in_file_2_skip dictionary
        try:
            date_in_file_2_skip.get(file, [])
            list_unique_days_od = [
                day
                for day in list_unique_days_od
                if day not in date_in_file_2_skip.get(file, [])
            ]
        except:
            pass
        list_all_days_available_analysis_flows.extend(list_unique_days_od)
    return list_all_days_available_analysis_flows
