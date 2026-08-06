import polars as pl
from data_preparation.diffusion.constant_names_variables import *

## FILTERING AND AGGREGATION FUNCTIONS ##
def aggregate_presences_new_version(df: pl.DataFrame, 
                        list_columns_groupby: list, 
                        str_col_trips_to_be_aggregated: str, 
                        str_col_name_aggregated: str,
                        method_aggregation: str = "sum"):
    if method_aggregation == "sum":
        print("Aggregating by sum keeping fixed columns: ", list_columns_groupby)
        return aggregate_presences_by_sum(df, 
                           list_columns_groupby, 
                           str_col_trips_to_be_aggregated, 
                           str_col_name_aggregated)
    elif method_aggregation == "average":
        print("Aggregating by average keeping fixed columns: ", list_columns_groupby)
        return aggregate_presences_by_average(df, 
                    list_columns_groupby,
                    str_col_trips_to_be_aggregated,
                    str_col_name_aggregated)
    else:
        raise ValueError(f"Method {method_aggregation} not recognized. Use 'sum' or 'average'.")
    

def aggregate_presences_by_sum(df: pl.DataFrame, 
                           list_columns_groupby: list, 
                           str_col_trips_to_be_aggregated: str, 
                           str_col_name_aggregated: str):
    """
    Function to initialize the aggregation of trips based on specified filters and grouping columns.
    It starts from the raw dataframe from Vodafone and applies the filters to:
        - Group by the specified columns and aggregate the trips
    Parameters:
    - df: Polars DataFrame containing the raw trip data.
    - tuple_filters: Tuple of Polars expressions to filter the DataFrame.
    - list_columns_groupby: List of column names to group by.
    - str_col_trips_to_be_aggregated: Name of the column containing the trip counts to be aggregated.
    - str_col_name_aggregated: Name of the new column to store the aggregated trip counts.
    Returns:
        - df_agg: Polars DataFrame with aggregated trip counts NOTE: over all the classes that are not specified in the group by. (i.e. TRIP_TYPE,NATIONALITY_CLASS_ID) 
        
    """
    for col in list_columns_groupby:
        if col not in df.columns:
            raise ValueError(f"Column {col} not found in DataFrame")
    df_sum = df.group_by(list_columns_groupby).agg(
        pl.col(str_col_trips_to_be_aggregated).sum().alias(str_col_name_aggregated)
    )
    return df_sum

def aggregate_presences_by_average(df: pl.DataFrame, 
                            columns_to_aggregate_over: list,
                            str_col_trips_to_be_aggregated: str,
                            str_col_name_aggregated: str):
    """
    Function to aggregate trips by summing over specified columns and computing the average over days.
    Parameters:
    - df: Polars DataFrame containing the trip data.
    - columns_to_aggregate_over: List of column names to group by for aggregation.
    - col_output_total_trips: Name of the column containing the trip counts to be summed.
    Returns:
        - df_agg: Polars DataFrame with aggregated trip counts and average trips over days
    """

    return df.group_by(columns_to_aggregate_over).agg(
                                                        pl.col(str_col_trips_to_be_aggregated).mean().floor().alias(str_col_name_aggregated)                                                               # 3. compute average over days
                                                        )



def compute_presences_average(
                            df_presenze_null_days:pl.DataFrame,
                            str_area_id_presenze: str,
                            str_presences_presenze: str,
                            col_out_presenze:str,
                            is_group_by_hour: bool,
                            col_hour_id: str,
                            hour_id: int,
                            is_nationality_markowitz_considered:bool,
                            nationality_col: str,
                            nation = None        
):
    """
        Compute the average number of presences for each AREA_ID
        If is_nationality_markowitz_considered is True, then the average is computed only for the specified nation
        If is_nationality_markowitz_considered is False, then the average is computed for all nations
        Output:
            pl.DataFrame with columns:
                - AREA_ID
                - col_out_presenze: average number of presences for each AREA_ID
        @Description:
            This function computes the average number of presences for each AREA_ID.
            - it is thought to be used in a loop over hour_id and nations of users
        @Params:
            df_presenze_null_days: pl.DataFrame -> DataFrame containing the presences data with null days
            col_str_average_presences_null_day: str -> Name of the column to store the average number of presences for each AREA_ID
            str_area_id_presenze: str -> Name of the column containing the AREA_ID
            str_presences_presenze: str -> Name of the column containing the presences data
            col_out_presenze: str -> Name of the column to store the average number of presences for each AREA_ID
            is_group_by_hour: bool -> If True, the aggregation is done by hour
            col_hour_id: str -> Name of the column containing the hour ID
            hour_id: int -> Hour ID to filter the data
    """
    # NOTE: Filter the analysis by time of the day if is_group_by_hour is True
    # NOTE: Filter the analysis by time of the day if is_group_by_hour is True
    if is_group_by_hour:
        df_presenze_null_days = df_presenze_null_days.filter(pl.col(col_hour_id) == hour_id)
    else:
        pass
    if is_nationality_markowitz_considered:
        if nation is None:
            raise ValueError("If is_nationality_markowitz_considered is True, then nation must be specified")
        df_presenze_null_days = df_presenze_null_days.filter(pl.col(nationality_col) == nation)
    else:
        pass

        df_presenze_null_days = df_presenze_null_days.group_by(str_area_id_presenze).agg(
            pl.col(str_presences_presenze).mean().alias(col_out_presenze)
        ).select([str_area_id_presenze, col_out_presenze])
    return df_presenze_null_days


def aggregate_presences(
                            df_presenze:pl.DataFrame,
                            col_str_day: str,
                            str_area_id_presenze: str,
                            str_presences_presenze: str,
                            col_out_presenze:str,
                            is_group_by_hour: bool,
                            col_hour_id: str,
                            hour_id: int,
                            is_nationality_markowitz_considered:bool,
                            nationality_col: str,
                            nation = None        
                        ):
    """
        Aggregate the presences data by AREA_ID and compute the average number of presences for each AREA_ID
        If is_nationality_markowitz_considered is True, then the total sum is computed only for the specified nation
        If is_nationality_markowitz_considered is False, then the total sum is computed for all nations
        @Description:
            This function aggregates the presences data by AREA_ID and computes the total number of presences for each AREA_ID.
            - it is thought to be used in a loop over hour_id and nations of users
        @Params:
            df_presenze_null_days: pl.DataFrame -> DataFrame containing the presences data with null days
            col_str_average_presences_null_day: str -> Name of the column to store the average number of presences for each AREA_ID
            str_area_id_presenze: str -> Name of the column containing the AREA_ID
            str_presences_presenze: str -> Name of the column containing the presences data
            col_out_presenze: str -> Name of the column to store the total sum of presences for each AREA_ID
            is_group_by_hour: bool -> If True, the aggregation is done by hour
            col_hour_id: str -> Name of the column containing the hour ID
            hour_id: int -> Hour ID to filter the data  
       @Returns:
            pl.DataFrame with columns:  
                - AREA_ID
                - col_out_presenze: total sum of presences for each AREA_ID
                - col_str_day: day column to keep track of the days used in the aggregation 
    """
    # NOTE: Filter the analysis by time of the day if is_group_by_hour is True
    if is_group_by_hour:
        df_presenze = df_presenze.filter(pl.col(col_hour_id) == hour_id)
    else:
        pass
    if is_nationality_markowitz_considered:
        if nation is None:
            raise ValueError("If is_nationality_markowitz_considered is True, then nation must be specified")
        df_presenze = df_presenze.filter(pl.col(nationality_col) == nation)
    else:
        pass

        df_presenze = df_presenze.group_by([str_area_id_presenze,col_str_day]).agg(
            pl.col(str_presences_presenze).sum().alias(col_out_presenze)
        ).select([str_area_id_presenze, col_out_presenze,col_str_day])
    return df_presenze


def compute_starting_risk_column_from_stack_df(df_presenze_null_days,
                                               stack_df_presenze: pl.DataFrame,
                                               str_area_id_presenze: str,
                                               col_total_presences_tour_no_hour: str,
                                               col_total_presences_oct_no_hour: str,
                                               col_return: str):
    """
        @Params:
            - df_presenze_null_days: pl.DataFrame -> DataFrame containing the average number of presences for each AREA_ID in October
            - stack_df_presenze: pl.DataFrame -> DataFrame containing the presences data aggregated by AREA_ID and day
            - str_area_id_presenze: str -> Name of the column containing the AREA_ID
            - col_total_presences_tour_no_hour: str -> Name of the column containing the total sum of presences for each AREA_ID in touristic months
            - col_total_presences_oct_no_hour: str -> Name of the column containing the total sum of presences for each AREA_ID in October
            - col_tot_diff_oct: str -> Name of the column containing the difference between total presences in October and total presences in touristic months
        @Returns:
            - stack_df_presenze: pl.DataFrame -> DataFrame containing the presences data aggregated by AREA_ID and day with the additional column col_tot_diff_oct
        @Description:
            This function computes the starting risk column for Markowitz analysis.
            It joins the presences data with the null day data to compute the difference between total presences in touristic months and total presences in October.
            - it is thought to be used after aggregating the presences data by AREA_ID and computing the average number of presences for each AREA_ID
            NOTE: That this is done as we consider the risk relative to October as the baseline
    """
    print("Compute risk column from ...")
    # Join with the null day to compute the difference
    stack_df_presenze = stack_df_presenze.join(df_presenze_null_days, on=str_area_id_presenze, how="left")
    # Compute the difference between total presences in touristic months and total presences in October P_i(t) - P_i(October)
    print("Compute DP_i(t) = P_i(October) - P_i(t)")
    stack_df_presenze = stack_df_presenze.with_columns(
                                (pl.col(col_total_presences_oct_no_hour) - pl.col(col_total_presences_tour_no_hour)).alias(col_return)                            # NOTE: For the pipeline it is fundamntal to choose october - total  since we want to minimize
                            )
    return stack_df_presenze

def compute_expected_return_from_stack_df(stack_df_presenze: pl.DataFrame,
                                          col_return: str,                                      # NOTE: This is expected i markowitz to be: col_tot_diff_oct
                                          col_expected_return: str,
                                          str_area_id_presenze: str,
                                          is_return_standardized: bool,
                                          col_std = "std_day",
                                          ) -> pl.DataFrame:
    """

    """
    if is_return_standardized:
        print("Compute <DP> = <DP_i(t)>_t")
        # <DP> = <P_i(t) - <P_i(October)>_t
        df_mean = stack_df_presenze.group_by([str_area_id_presenze]).agg(
                                                                            pl.col(col_return).mean().alias(col_expected_return)
                                                                        )
        # (P_i(t) - <DP>) / std(P_i(t) - <DP>)
        print("Compute std(DP_i(t))")
        df_var = stack_df_presenze.group_by([str_area_id_presenze]).agg(
                                                                        pl.col(col_return).std().alias(col_std)
                                                                        )
        print("Compute (P_i(t) - <DP>) and (P_i(t) - <DP>) / std(P_i(t) - <DP>)")
        df_var = df_var.with_columns(
            pl.when(pl.col(col_std) == 0).then(1).otherwise(pl.col(col_std)).alias(col_std)
        )
        df_mean = df_mean.join(df_var, on=[str_area_id_presenze], how="left")
        print("Compute <DP> / std(DP_i(t))")
        df_mean = df_mean.with_columns((pl.col(col_expected_return) / pl.col(col_std)).alias(col_expected_return))
    else:
        print("Compute <DP> = <DP_i(t)>_t")
        # <DP> = <P_i(t) - <P_i(October)>_t
        df_mean = stack_df_presenze.group_by([str_area_id_presenze]).agg(
                                                                            pl.col(col_return).mean().alias(col_expected_return)
                                                                        )
        df_var = stack_df_presenze.group_by([str_area_id_presenze]).agg(
                                                                        pl.col(col_return).std().alias(col_std)
                                                                        )
        df_var = df_var.with_columns(
            pl.when(pl.col(col_std) == 0).then(1).otherwise(pl.col(col_std)).alias(col_std)
        )
        df_mean = df_mean.join(df_var, on=[str_area_id_presenze], how="left")

    return df_mean


def standardize_return_stack_df(stack_df_presenze: pl.DataFrame,
                                df_mean: pl.DataFrame,
                                col_return:str,
                                str_area_id_presenze: str,
                                is_standardize_return: bool,
                                col_std = "std_day") -> pl.DataFrame:
    """
        Standardize the return column in the stack_df_presenze DataFrame
        @Params:
            - stack_df_presenze: pl.DataFrame -> DataFrame containing the presences data aggregated by AREA_ID and day
            - df_mean: pl.DataFrame -> DataFrame containing the mean of the return for each AREA_ID
            - col_return: str -> Name of the column containing the return
            - str_area_id_presenze: str -> Name of the column containing the AREA_ID
            - is_standardize_return: bool -> If True, the return is standardized
            - col_std: str -> Name of the column containing the standard deviation of the return
        @Returns:
            - stack_df_presenze_mean_var: pl.DataFrame -> DataFrame containing the presences data aggregated by AREA_ID and day with the standardized return column
        @Description:
            This function standardizes the return column in the stack_df_presenze DataFrame.
            - it is thought to be used after computing the expected return for each AREA_ID
    """
    assert col_return in stack_df_presenze.columns, f"{col_return} not in stack_df_presenze columns"
    if is_standardize_return:
        assert col_std in df_mean.columns, f"{col_std} not in df_mean columns"
        stack_df_presenze_mean_var = stack_df_presenze.join(df_mean, on=[str_area_id_presenze], how="left")
        stack_df_presenze_mean_var = stack_df_presenze_mean_var.with_columns(
                                    (pl.col(col_return) / pl.col(col_std)).alias(col_return)
                                )
    else:
        stack_df_presenze_mean_var = stack_df_presenze.join(df_mean, on=[str_area_id_presenze], how="left")    
    return stack_df_presenze_mean_var
    


import numpy as np
from sklearn.impute import SimpleImputer
import warnings

def compute_correlation_matrix_df_from_time_series(
    stack_df_presenze_mean_var: pl.DataFrame,
    str_area_id_presenze: str,
    col_str_day_od: str,
    col_return: str,
    str_column_cov: str = "cov"
) -> tuple[pl.DataFrame, bool]:
    """
    Compute the empirical covariance matrix based on the time evolution of presences.
    Each row represents an area, each column represents a day.
    Covariance measures how areas co-vary over time.

    Returns
    -------
    cov_df : pl.DataFrame
        Columns:
            - AREA_ID_i
            - AREA_ID_j
            - cov : covariance between AREA_ID_i and AREA_ID_j

    is_valid_computation : bool
        True if computation succeeded (no NaN, correct size); False otherwise.
    """
    print("Computing empirical covariance matrix based on time evolution...")

    # Select relevant data
    time_series_data = stack_df_presenze_mean_var.select([
        str_area_id_presenze,
        col_str_day_od,
        col_return
    ]).unique()

    # Pivot to area × day matrix
    time_series_matrix = time_series_data.pivot(
        index=str_area_id_presenze,
        on=col_str_day_od,
        values=col_return,
        aggregate_function="first"
    )

    area_ids = time_series_matrix.select(str_area_id_presenze).to_numpy().flatten()
    presences_time_series = time_series_matrix.select(pl.exclude(str_area_id_presenze)).to_numpy()

    n_areas = len(area_ids)
    print(f"Number of areas: {n_areas}")
    print(f"Presences time series shape: {presences_time_series.shape}")

    # === Validation: enough data? ===
    if presences_time_series.size == 0 or presences_time_series.shape[1] < 2:
        print("Invalid computation: not enough data points to compute covariance.")
        return pl.DataFrame(), False

    # === Handle missing data ===
    imputer = SimpleImputer(strategy='mean')
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        presences_clean = imputer.fit_transform(presences_time_series)

    # If any NaNs remain → invalid computation
    if np.isnan(presences_clean).any():
        print("Invalid computation: NaNs detected after imputation.")
        return pl.DataFrame(), False

    # === Compute covariance ===
    with np.errstate(divide='ignore', invalid='ignore'):
        cov_matrix = np.cov(presences_clean)

    # If np.cov fails or returns invalid shape → invalid
    if np.ndim(cov_matrix) != 2 or cov_matrix.shape != (n_areas, n_areas):
        print("Invalid computation: covariance matrix shape mismatch.")
        return pl.DataFrame(), False

    if not np.isfinite(cov_matrix).all():
        print("Invalid computation: covariance matrix contains NaN or inf.")
        return pl.DataFrame(), False

    # === Build output DataFrame ===
    area_i, area_j, cov_list = [], [], []
    for i in range(n_areas):
        for j in range(n_areas):
            area_i.append(area_ids[i])
            area_j.append(area_ids[j])
            cov_list.append(float(cov_matrix[i, j]))

    cov_df = pl.DataFrame({
        str_area_id_presenze + "_i": area_i,
        str_area_id_presenze + "_j": area_j,
        str_column_cov: cov_list
    })

    # Final validation
    expected_size = n_areas ** 2
    is_valid_computation = (
        cov_df.height == expected_size
        and np.isfinite(cov_df[str_column_cov].to_numpy()).all()
    )

    print(f"Covariance DataFrame shape: {cov_df.shape}")
    print(f"Computation valid: {is_valid_computation}")

    return (cov_df if is_valid_computation else pl.DataFrame(), is_valid_computation)


def get_area_id_to_idx_mapping(cov_df, str_area_id_presenze):
    """
    Given a covariance DataFrame, create a mapping from area IDs to integer indices and vice versa.
    Args:
        cov_df (pd.DataFrame): DataFrame containing covariance data with area IDs.
        str_area_id_presenze (str): Column name prefix for area IDs in the DataFrame.
    Returns:
        area_to_index (dict): Mapping from area_id to integer index. (to pass from dataframe to numpy matrix)
        index_to_area (dict): Mapping from integer index to area_id. (to pass from numpy matrix to dataframe)
    """
    unique_areas = sorted(list(set(cov_df[str_area_id_presenze + "_i"].unique().to_list())))
    area_to_index = {area: idx for idx, area in enumerate(unique_areas)}
    index_to_area = {idx: area for idx, area in enumerate(unique_areas)}
    return area_to_index, index_to_area