"""
    In this module we 
"""

import datetime
import numpy as np
def date_to_timestamp(date_str):
    """
    Convert a date string in "%Y-%m-%d" format to a timestamp.
    
    Parameters:
    date_str (str): The date string in "%Y-%m-%d" format.
    
    Returns:
    float: The corresponding timestamp.
    """
    # Parse the date string into a datetime object
    date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    # Convert the datetime object to a timestamp
    timestamp = date_obj.timestamp()
    return timestamp

def ConvertMinuteVectorToSeconds(VectorMinutes):
    """
        @param VectorMinutes: Vector with minutes
        @return VectorSeconds: Vector with seconds
    """
    VectorSeconds = [minutes*60 for minutes in VectorMinutes]
    return np.array(VectorSeconds)

def ConvertVectorMinutesToDatetime(VectorMinutes,Start_Day_In_Hour,Day = "2023-08-15"):
    """
        @param VectorMinutes: Vector with minutes
        @return VectorDatetime: Vector with datetime
    """
    StartTimeStamp = date_to_timestamp(Day)
    ShiftFromMidnight = Start_Day_In_Hour*3600
    VectorSeconds = ConvertMinuteVectorToSeconds(VectorMinutes)
    # Vector [timestamp(Day,Shift),..,timestamp(Day,Shift) + N*dt)]
    VectorSeconds = VectorSeconds + StartTimeStamp + ShiftFromMidnight
    # [datetime(Day,Shift),..,datetime(Day,Shift) + N*dt]
    VectorDatetime = [datetime.datetime.fromtimestamp(seconds).strftime('%Y-%m-%d %H:%M:%S') for seconds in VectorSeconds]
    return VectorDatetime

def CastVectorDateTime2Hours(VectorDateTime):
    """
        @param VectorDateTime: Vector with datetime
        @return VectorHours: Vector with hours
    """
    VectorHMS = [datetime.datetime.strptime(Datetime, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S").split(" ")[1] for Datetime in VectorDateTime]
#    VectorHMS = [(datetime.datetime.strptime(Datetime, "%Y-%m-%d %H:%M:%S").hour,
#                  datetime.datetime.strptime(Datetime, "%Y-%m-%d %H:%M:%S").minute,
#                  datetime.datetime.strptime(Datetime, "%Y-%m-%d %H:%M:%S").second)
#                 for Datetime in VectorDateTime]
    return VectorHMS



# Generate a vector of times (hours, minutes, seconds)
def generate_time_vector_hour(start_hour, end_hour, step_minutes):
    """
    Generate a vector of time objects (hours, minutes, seconds) between start and end hours.

    Parameters:
        start_hour (int): Start hour (0-23).
        end_hour (int): End hour (0-23).
        step_minutes (int): Step size in minutes.

    Returns:
        list: A list of time objects (hours, minutes, seconds).
    """
    total_hours_interval = end_hour - start_hour
    total_minutes_interval = total_hours_interval * 60
    number_steps = int(total_minutes_interval / step_minutes) + 1
    v_time_delta = []
    for n_step in range(number_steps):
        # minutes are the remainder of the division of the total minutes by 60
        if n_step*step_minutes > 60:
            minutes = n_step*step_minutes%60
        # Otherwise consider just the total number of minutes
        else:
            minutes = n_step*step_minutes
        # hours are the total number of hours plus the start hour
        hours = start_hour + int(n_step*step_minutes/60)
        v_time_delta.append(datetime.timedelta(hours=hours, minutes=minutes, seconds=0))
    return v_time_delta

def generate_time_vector_second(start_hour, end_hour, step_seconds):
    for n_step in range(int((end_hour - start_hour) * 3600 / step_seconds) + 1):
        # seconds are the remainder of the division of the total seconds by 60
        yield n_step * step_seconds
def convert_str_time_to_timedelta(time_str):
    """
    Convert a time string (e.g., '07:35:00') into a timedelta object.
    
    Parameters:
        time_str (str): Time string in the format 'HH:MM:SS'.
    
    Returns:
        timedelta: Corresponding timedelta object.
    """
    if not isinstance(time_str, str):
        time_obj = datetime.datetime.strptime(time_str, "%H:%M:%S").time()
        return datetime.timedelta(hours=time_obj.hour, minutes=time_obj.minute, seconds=time_obj.second)
    else:
        return datetime.timedelta(hours=0,
                                 minutes= 0,
                                 seconds= 0)
    


def robust_date_parser(date_series, str_period_id_col):
    """
    Robust date parser that handles mixed date formats in the dataset.
    
    Args:
        date_series: pandas Series containing date values
        str_period_id_col: column name for logging purposes
    
    Returns:
        list: List of unique date strings in 'YYYY-MM-DD' format
    """
    import pandas as pd
    import re
    import numpy as np
    
    print(f"Processing dates from column: {str_period_id_col}")
    print(f"Sample values: {date_series.head().tolist()}")
    print(f"Unique values count: {date_series.nunique()}")
    
    # Function to extract date from mixed format strings
    def extract_date_from_mixed_format(date_str):
        if pd.isna(date_str):
            return None
            
        date_str = str(date_str).strip()
        
        # Case 1: Pure YYYYMMDD format (e.g., "20240708")
        if re.match(r'^\d{8}$', date_str):
            try:
                return pd.to_datetime(date_str, format='%Y%m%d')
            except:
                pass
        
        # Case 2: Mixed format like "202410 - Feriale" or "YYYYMM - text"
        # Extract the YYYYMM part and assume day 01
        date_match = re.match(r'^(\d{6})', date_str)
        if date_match:
            yyyymm = date_match.group(1)
            try:
                # Assume first day of the month for YYYYMM format
                date_with_day = yyyymm + "01"
                return pd.to_datetime(date_with_day, format='%Y%m%d')
            except:
                pass
        
        # Case 3: Try to extract any 8-digit sequence
        eight_digit_match = re.search(r'\d{8}', date_str)
        if eight_digit_match:
            try:
                return pd.to_datetime(eight_digit_match.group(0), format='%Y%m%d')
            except:
                pass
        
        # Case 4: Try pandas flexible parsing as fallback
        try:
            return pd.to_datetime(date_str, errors='coerce')
        except:
            pass
        
        print(f"Warning: Could not parse date: {date_str}")
        return None
    
    # Apply the extraction function
    print("Extracting dates from mixed format data...")
    parsed_dates = date_series.apply(extract_date_from_mixed_format)
    
    # Remove None values
    valid_dates = parsed_dates.dropna()
    
    if len(valid_dates) == 0:
        print("Warning: No valid dates found!")
        return ["2024-01-01"]  # Fallback date
    
    # Convert to string format and get unique values
    unique_dates = valid_dates.dt.strftime('%Y-%m-%d').unique()
    
    print(f"Successfully parsed {len(valid_dates)} dates")
    print(f"Unique parsed dates: {sorted(unique_dates)}")
    
    return list(unique_dates)

# Fix for the main processing loop - replace the problematic date parsing line
# Original problematic line:
# list_str_days = pd.to_datetime(df_presenze[str_period_id_presenze], format='%Y%m%d').strftime('%Y-%m-%d').unique()

# NEW ROBUST APPROACH:
def safe_extract_dates_from_presenze(df_presenze, str_period_id_presenze, col_str_day_od, df_od):
    """
    Safely extract dates from presence data with fallback to OD data.
    """
    try:
        # Try robust date parsing on presence data
        list_str_days = robust_date_parser(df_presenze[str_period_id_presenze], str_period_id_presenze)
    except Exception as e:
        print(f"Error parsing dates from presence data: {e}")
        print("Falling back to OD data for dates...")
        try:
            # Fallback to OD data
            list_str_days = list(df_od[col_str_day_od].unique())
        except Exception as e2:
            print(f"Error parsing dates from OD data: {e2}")
            print("Using default date...")
            list_str_days = ["2024-01-01"]
    
    return list_str_days