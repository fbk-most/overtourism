import argparse
import configparser
import gc
from data_preparation.diffusion.global_import import *

# ============================================================
# Argument parser for Markowitz pipeline control
# ============================================================

parser = argparse.ArgumentParser(
    description=(
        "Run the overtourism Markowitz pipeline.\n\n"
        "Available case_pipelines:\n"
        "  - _\n"
        "  - time\n"
        "  - visitor\n"
        "  - country\n"
        "  - weekday\n"
        "  - time_visitor\n"
        "  - time_country\n"
        "  - time_weekday\n"
        "  - visitor_country\n"
        "  - visitor_weekday\n"
        "  - country_weekday\n"
        "  - time_visitor_country\n"
        "  - time_visitor_weekday\n"
        "  - time_country_weekday\n"
        "  - visitor_country_weekday\n"
        "  - time_visitor_country_weekday\n\n"
        "Use --choose_case_pipeline to run only the specified case."
    ),
    formatter_class=argparse.RawTextHelpFormatter
)

parser.add_argument(
    "--choose_case_pipeline",
    action="store_true",
    help="If set, only the specified case_pipeline will be executed (default: run all)."
)
parser.add_argument(
    "--case_pipeline",
    type=str,
    default="time_visitor_country_weekday",
    help="The case_pipeline to execute when --choose_case_pipeline is set."
)

args = parser.parse_args()

# ============================================================
# Validate user input
# ============================================================

valid_cases = [
    "_", "time", "visitor", "country", "weekday",
    "time_visitor", "time_country", "time_weekday",
    "visitor_country", "visitor_weekday", "country_weekday",
    "time_visitor_country", "time_visitor_weekday",
    "time_country_weekday", "visitor_country_weekday",
    "time_visitor_country_weekday",
]

if args.choose_case_pipeline and args.case_pipeline not in valid_cases:
    raise ValueError(
        f"Invalid case_pipeline '{args.case_pipeline}'.\n"
        f"Must be one of: {valid_cases}"
    )


# --- Setup ---
from data_preparation.utils import init_s3, DATA_PREFIX, BASE_DIR

s3, bucket = init_s3()

# Load static shapefile ONCE (was reloaded inside loop in original)
cities_shp_path = os.path.join(
    BASE_DIR,
    "Data",
    "mavfa-fbk_AIxPA_tourism-delivery_2025.08.22-zoning",
    "fbk-aixpa-turismo.shp",
)
cities_gdf = gpd.read_file(cities_shp_path)

print("Extract list of files from bucket...")
list_files_od, list_files_presenze, list_str_dates_yyyymm = extract_filenames_and_date_from_bucket(bucket)

date_in_file_2_skip = {
    f'{DATA_PREFIX}vodafone-aixpa/od-mask_202407.parquet': "2024-08-08",
    f'{DATA_PREFIX}vodafone-aixpa/od-mask_202408.parquet': "2024-07-23",
}

# NOTE: Extract the null day
print("Initialize null day OD-presenze...")
df_presenze_null_days = extract_presences_vodafone_from_bucket(
    s3=s3, list_files_presenze=list_files_presenze, i=2
)
df_presenze_null_days = add_is_weekday_from_period_presenze_null_days(
    df=df_presenze_null_days,
    period_col=str_period_id_presenze,
    is_weekday_col=col_str_is_week,
)

# NOTE: Extract the stack of presences -> the overtouristic dataframe for presences
print("Stacking the presences data...")
stack_df_presenze_original = concat_presences(
    list_files_presences=list_files_presenze,
    s3=s3,
    col_str_day_od=col_str_day_od,
    col_period_id=str_period_id_presenze,
)

# NOTE: Add holiday column
stack_df_presenze_original = add_holiday_columun_df_presenze(
    stack_df_presenze=stack_df_presenze_original,
    col_str_day_od=col_str_day_od,
    public_holidays=public_holidays,
    col_str_is_week=col_str_is_week,
)

# Build lists of unique values (these are usually smallish)
list_all_hours = list(stack_df_presenze_original[str_time_block_id_presenze].unique())
list_all_visitors = list(stack_df_presenze_original[str_visitor_class_id_presenze].unique())
list_all_countries = list(stack_df_presenze_original[str_country_presenze].unique())
list_all_weekdays = list(stack_df_presenze_original[col_str_is_week].unique())
print(
    f"List all hours: {list_all_hours}, list all visitors: {list_all_visitors}, list all countries: {list_all_countries}, list all weekdays: {list_all_weekdays}"
)

case2column_names_diffusione_3 = init_dict_case2column_names_diffusione_3(
    AGGREGATION_NAMES_2_COLUMNS_AGGREGATION_PRESENCES
)

# OPTIONAL: free list_files_presenze if not needed any more (they were used to build stack_df_presenze_original)
try:
    del list_files_presenze
    gc.collect()
except Exception:
    pass


# ============================================================
# Determine which pipelines to run
# ============================================================

if args.choose_case_pipeline:
    chosen_pipelines = [args.case_pipeline]
    print(f"[INFO] Running only the chosen case_pipeline: {args.case_pipeline}")
else:
    chosen_pipelines = list(case2column_names_diffusione_3.keys())
    print(f"[INFO] Exploring all case_pipelines: {chosen_pipelines}")


for case_pipeline in chosen_pipelines:
    print(f"Initialize dict presences output for case_pipeline {case_pipeline}...")

    dict_presences_output, case_2iterable_values = initialize_dict_presences_output_diffusione_3(
        dict_case2column_names=case2column_names_diffusione_3,
        list_all_hours=list_all_hours,
        list_all_visitors=list_all_visitors,
        list_all_countries=list_all_countries,
        list_all_weekdays=list_all_weekdays,
        case_pipeline=case_pipeline,
    )

    dict_iterable_name_2_iterable_values = case_2iterable_values[case_pipeline]
    iterable_names = list(dict_iterable_name_2_iterable_values.keys())
    iterable_values = [dict_iterable_name_2_iterable_values[k] for k in iterable_names]

    print(f"\tIterating over {iterable_names}")

    for combo in product(*iterable_values):
        combo_dict = dict(zip(iterable_names, combo))

        # Extract values (or defaults if not present)
        time = combo_dict.get("time", None)
        visitor = combo_dict.get("visitor", None)
        country = combo_dict.get("country", None)
        is_weekday = combo_dict.get("weekday", None)

        print(f"\tCombination: {combo_dict}")
        # Update dict_presences_output in place
        dict_presences_output = nested_set_dict_column_names_presences_analysis(
            case_2iterable_values=case_2iterable_values,
            dict_presences_output=dict_presences_output,
            time=time,
            visitor=visitor,
            country=country,
            is_weekday=is_weekday,
            case_pipeline=case_pipeline,
        )

        # Get column names for this iteration
        col_aggregated_presences = nested_get_output_from_key_presences_analysis(
            case_2iterable_values=case_2iterable_values,
            dict_presences_output=dict_presences_output,
            name_key="column_presences_no_baseline",
            case_pipeline=case_pipeline,
        )
        col_aggregated_presences_baseline = nested_get_output_from_key_presences_analysis(
            case_2iterable_values=case_2iterable_values,
            dict_presences_output=dict_presences_output,
            name_key="column_presences_baseline",
            case_pipeline=case_pipeline,
        )
        try:
            # Aggregate: try to keep intermediate DataFrames minimal and delete as soon as possible
            stack_df_presenze_original_week_day_base = aggregate_presences_new_version(
                df=stack_df_presenze_original,
                list_columns_groupby=case2column_names_diffusione_3[case_pipeline] + [col_str_day_od],
                str_col_trips_to_be_aggregated="PRESENCES",
                str_col_name_aggregated=col_aggregated_presences,
                method_aggregation="sum",
            )
            is_case_aggregation_non_touristic_df_has_working_with_data = True
        except Exception as e:
            is_case_aggregation_non_touristic_df_has_working_with_data = False
        try:
            df_presenze_null_days_week_day_base = aggregate_presences_new_version(
                df=df_presenze_null_days,
                list_columns_groupby= case2column_names_diffusione_3[case_pipeline],
                str_col_trips_to_be_aggregated="PRESENCES",
                str_col_name_aggregated=col_aggregated_presences_baseline,
                method_aggregation="sum",
            )

            # Average over (30) days and floor -> convert to a compact structure if possible
            df_presenze_null_days_week_day_base = df_presenze_null_days_week_day_base.with_columns(
                (pl.col(col_aggregated_presences_baseline) / 30).floor()
            )
            is_case_aggregation_baseline_working_with_data = True
        except Exception as e:
            is_case_aggregation_baseline_working_with_data = False
        # Free df_presenze_null_days if it won't be used elsewhere (we have null-day base now)
        gc.collect()
        is_possible_to_proceed = is_case_aggregation_baseline_working_with_data and is_case_aggregation_non_touristic_df_has_working_with_data
        if not is_possible_to_proceed:
            print(f"Skipping combination {combo_dict} due to lack of data after aggregation")
            continue
        else:
            print("Aggregations successful, proceeding with analysis...")
            is_covariance_standardized = True

            # compute filters
            dict_case_2_tuple_filters, dict_case_message = compute_filters_and_messages_for_case_analysis_diffusione_3(
                dict_case2column_names=case2column_names_diffusione_3,
                time_of_interest=time,
                visitor_of_interest=visitor,
                country_of_interest=country,
                is_weekday=is_weekday,
            )

            # Filter the aggregated data (these filtered dataframes are used below)
            stack_df_presenze_week_day = stack_df_presenze_original_week_day_base.filter(
                dict_case_2_tuple_filters[case_pipeline]
            )
            df_presenze_null_days_week_day = df_presenze_null_days_week_day_base.filter(
                dict_case_2_tuple_filters[case_pipeline]
            )

            # We can delete base versions now
            try:
                del stack_df_presenze_original_week_day_base
                del df_presenze_null_days_week_day_base
            except Exception:
                pass
            gc.collect()

            ########################################################
            ############### NULL DAY INITIALIZATION ################
            ########################################################

            print("Compute the total number of presences for each AREA_ID...")

            #############################################################
            ############ PREPROCESS RAW DATA TO MARKOWITZ ###############
            #############################################################

            column_return = nested_get_output_from_key_presences_analysis(
                case_2iterable_values=case_2iterable_values,
                dict_presences_output=dict_presences_output,
                name_key="column_portfolio",
                case_pipeline=case_pipeline,
            )
            col_expected_return = nested_get_output_from_key_presences_analysis(
                case_2iterable_values=case_2iterable_values,
                dict_presences_output=dict_presences_output,
                name_key="column_expected_return",
                case_pipeline=case_pipeline,
            )
            col_std = nested_get_output_from_key_presences_analysis(
                case_2iterable_values=case_2iterable_values,
                dict_presences_output=dict_presences_output,
                name_key="column_std",
                case_pipeline=case_pipeline,
            )
            str_column_cov = nested_get_output_from_key_presences_analysis(
                case_2iterable_values=case_2iterable_values,
                dict_presences_output=dict_presences_output,
                name_key="column_cov",
                case_pipeline=case_pipeline,
            )
            str_col_portfolio = nested_get_output_from_key_presences_analysis(
                case_2iterable_values=case_2iterable_values,
                dict_presences_output=dict_presences_output,
                name_key="column_portfolio",
                case_pipeline=case_pipeline,
            )

            # Extract the list of days (should be relatively small)
            list_str_days = list(stack_df_presenze_original[col_str_day_od].unique())

            # Compute normalized covariance / starting risk
            stack_df_presenze = compute_starting_risk_column_from_stack_df(
                df_presenze_null_days=df_presenze_null_days_week_day,
                stack_df_presenze=stack_df_presenze_week_day,
                str_area_id_presenze=str_area_id_presenze,
                col_total_presences_tour_no_hour=col_aggregated_presences,
                col_total_presences_oct_no_hour=col_aggregated_presences_baseline,
                col_return=column_return,
            )

            # free filtered inputs if not used afterwards
            try:
                del stack_df_presenze_week_day
                del df_presenze_null_days_week_day
            except Exception:
                pass
            gc.collect()

            # Compute expected return and immediately extract the needed numpy array to free DataFrame
            df_mean = compute_expected_return_from_stack_df(
                stack_df_presenze=stack_df_presenze,
                col_return=column_return,
                col_expected_return=col_expected_return,
                str_area_id_presenze=str_area_id_presenze,
                is_return_standardized=is_covariance_standardized,
                col_std=col_std,
            )

            # Prepare expected_return as numpy and delete df_mean later when safe
            expected_return = np.nan_to_num(df_mean[col_expected_return].to_numpy(), nan=0.0)
            # Standardize and prepare covariance
            stack_df_presenze_mean_var = standardize_return_stack_df(
                stack_df_presenze=stack_df_presenze,
                df_mean=df_mean,
                col_return=column_return,
                str_area_id_presenze=str_area_id_presenze,
                is_standardize_return=is_covariance_standardized,
                col_std=col_std,
            )
            if len(stack_df_presenze_mean_var) == 0:
                print(f"Skipping combination {combo_dict} due to empty standardized stack")
                is_valid_correlation_matrix = False
            else:    
                correlation_df, is_valid_correlation_matrix = compute_correlation_matrix_df_from_time_series(
                    stack_df_presenze_mean_var=stack_df_presenze_mean_var,
                    str_area_id_presenze=str_area_id_presenze,
                    col_str_day_od=col_str_day_od,
                    col_return=column_return,
                    str_column_cov=str_column_cov,
                )

            # We don't need the stack_df_presenze and stack_df_presenze_mean_var anymore
            try:
                del stack_df_presenze
                del stack_df_presenze_mean_var
            except Exception:
                pass
            gc.collect()

            if not is_valid_correlation_matrix:
                print(f"Skipping combination {combo_dict} due to invalid correlation matrix")
                continue
            else:
                print(f"Correlation matrix valid with shape {correlation_df.shape}")
                ##############################################################
                ####################### RMT Clean Matrix #####################
                ##############################################################
                # Map area <-> index
                area_to_index, index_to_area = get_area_id_to_idx_mapping(
                    cov_df=correlation_df, str_area_id_presenze=str_area_id_presenze
                )

                q = from_areas_and_times_to_q(area_to_index=area_to_index, list_str_days=list_str_days)

                cov_matrix_numpy = from_df_correlation_to_numpy_matrix(
                    cov_df=correlation_df,
                    str_area_id_presenze=str_area_id_presenze,
                    str_column_cov=str_column_cov,
                    area_to_index=area_to_index,
                )

                # correlation_df no longer needed -> free it
                try:
                    del correlation_df
                except Exception:
                    pass
                gc.collect()

                C_clean, eigvals_clean, eigvecs = rmt_clean_correlation_matrix(
                                                                                C=cov_matrix_numpy, 
                                                                                q=q,
                                                                                is_bulk_mean=True
                                                                                )

                # compute MP limits and mask
                if is_covariance_standardized:
                    sigma = None
                else:
                    sigma = np.mean(df_mean[col_std].to_numpy())

                lambda_minus, lambda_plus, mask_eigvals = compute_MP_limits_and_mask(
                    eigvals_clean,
                    q,
                    is_covariance_standardized=is_covariance_standardized,
                    sigma=sigma,
                )

                # free cov_matrix_numpy and eigvals arrays if not needed
                try:
                    del cov_matrix_numpy
                except Exception:
                    pass
                gc.collect()

                ##############################################################
                #################### Markowitz procedure #####################
                ##############################################################

                # portfolio_weights is a numpy array - smallish
                portfolio_weights = extract_portfolio_from_eigenpairs(
                    C_clean=C_clean,
                    eigvals_clean=eigvals_clean,
                    eigvecs=eigvecs,
                    expected_return=expected_return,
                    sum_w=1,
                    is_normalize_portfolio=True,
                )

                # Map portfolio to the already-loaded cities_gdf copy (use a shallow copy to avoid altering original if needed)
                # Note: map_portfolio_numpy_to_cities_gdf probably returns a GeoDataFrame; reuse variable but avoid keeping extra copies
                cities_gdf_portfolio = map_portfolio_numpy_to_cities_gdf(
                    cities_gdf=cities_gdf,
                    portfolio_weights=portfolio_weights,
                    index_to_area=index_to_area,
                    str_area_id_presenze=str_area_id_presenze,
                    str_col_portfolio=str_col_portfolio,
                )

                # Merge df_mean into cities geodataframe - convert df_mean to pandas only for merging (and free after)
                cities_gdf_portfolio = cities_gdf_portfolio.merge(df_mean.to_pandas(), on=str_area_id_presenze)

                # free df_mean now
                try:
                    del df_mean
                except Exception:
                    pass
                gc.collect()

                # prepare output folders
                path_output_base = os.path.join(BASE_DIR, "Output")
                path_base_portfolio = path_output_base
                for branch in dict_presences_output.keys():
                    path_base_portfolio = os.path.join(path_base_portfolio, f"{branch}")
                    os.makedirs(path_base_portfolio, exist_ok=True)

                # Plot and save, then close figure immediately to free memory
                fig, ax = plt.subplots(1, 1, figsize=(10, 10))
                plot_polygons_and_with_scalar_field(cities_gdf_portfolio, str_col_portfolio, ax, fig, title=f"portfolio visitor: {visitor}, Week day: {is_weekday}, Country: {country}, Time: {time}")
                plt.savefig(os.path.join(path_base_portfolio, f"{case_pipeline}_portfolio_map_{visitor}_{is_weekday}_{country}_{time}.png"), dpi=200)
                plt.close(fig)

                # Pastur plot
                fig_pst, ax_pst = plot_pastur(eigvals_clean, q)
                plt.savefig(os.path.join(path_base_portfolio, f"{case_pipeline}_pastur_distribution_eigenvalues_{visitor}_{is_weekday}_{country}_{time}.png"), dpi=200)
                plt.close(fig_pst)

                # Write geojson of the (smaller) output geodataframe
                cities_gdf_portfolio.to_file(os.path.join(path_base_portfolio, f"geodataframe_input_plots_markowitz_{case_pipeline}_{visitor}_{is_weekday}_{country}_{time}.geojson"))

                # Clean up large objects at end of iteration
                try:
                    del cities_gdf_portfolio
                    del eigvals_clean
                    del eigvecs
                    del C_clean
                    del portfolio_weights
                    del expected_return
                    del mask_eigvals
                    del lambda_minus
                    del lambda_plus
                    del area_to_index
                    del index_to_area
                    del list_str_days
                    del combo_dict
                    del combo
                except Exception:
                    pass

                # Force a collection checkpoint
                gc.collect()

# Final cleanup (keep cities_gdf loaded if you need it later; delete if not)
try:
    del stack_df_presenze_original
except Exception:
    pass
gc.collect()
print("Processing complete.")
