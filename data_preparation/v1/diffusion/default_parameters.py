# Time constraints
str_start_time_window_interest = "07:00:00"                                    # start time of the time window of interest -> HH:MM:SS window of time for which we are interested about trips
str_end_time_window_interest = "19:00:00"                                      # end time of the time window of interest -> HH:MM:SS window of time for which we are interested about trips
int_hour_start_window_interest = 7                                             # start time of the time window of interest -> hours
int_hour_end_window_interest = 19                                              # end time of the time window of interest -> hours
int_min_aggregation_OD = 60
list_time_intervals = [[7,8],[8,9],[10,11],[16,17],[18,19],[25,26]]            # time intervals of interest in hours
hour_ids = [7,8,10,16,18]
week_days = ["Feriale","Prefestivo","Festivo"]

# NUMERIC PARAMETERS GRID
Lx = 2000                                                                           # size of x of a cell in the grid in meters
Ly = 2000                                                                           # size of y of a cell in the grid in meters

# Cases analysis Diffusione 3
case_analysis_diffusione_3 = ["bus","difference","default"]
case_analysis_diffusion_2 = ["aggregated"]

# Bus parameters
int_number_people_per_bus = 50                                                      # number of people per bus
threshold_n_stops = 2                                                               # threshold for the number of stops in a grid cell
# Join Parameter
buffer_distance = 50                                                                 # buffer distance for the join operation ("inner","distance"), stop points bus to roads

# parameter of the gravity model -> if False 
is_generate_fluxes = False

# Divide analysis markowitz ti different kinds of users
is_nationality_markowitz_considered = False

SAVE_SINGLE_GEOSPATIAL_FILES = False
WORK_IN_PROGRESS = False  # Set to True does not recompute the already computed days



# Markowitz
nation = None                                                                               # NOTE: If not None we are going to compute the Markowitz for each nation
is_covariance_standardized = True                                                           # NOTE: This is the C_ij = X^T X is normalized by 1: That is: X_it = X_it / \sum{(X_it - <X_i>)^2} -> the variance of single stock is 1

