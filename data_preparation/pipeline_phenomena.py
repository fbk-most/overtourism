"""
PIPELINE: 

Input : Server (S3)
Output: Output/final_data/   (phen_popolazione, phen_strutture, phen_presenze)
        or upload to the platform 

The entire pipeline is executed, generating phenomena from scratch. 
The intermediate steps save the intermediate results (standardized, processed)
"""
import logging
from data_preparation.download_raw_data import download_raw_data
from data_preparation.standardize_raw_data import standardize_raw_data
from data_preparation.process_std_data import process_data
from data_preparation.gen_base_phenomenon_dataframes import main_compute_phenomena_dfs

if __name__ == "__main__":
    type_format = "csv"

    logging.info("Step 0: download raw data into Output/raw_data")
    download_raw_data(type_format = type_format)
    logging.info("Step 1: uniform raw data into Output/normalized")
    standardize_raw_data(type_format = type_format)
    logging.info("Step 2: process normalized data into Output/data_processed")
    process_data(type_format = type_format)
    logging.info("Step 3: saves final phenomena into Output/final_data")
    main_compute_phenomena_dfs(type_format = type_format)
    logging.info("Pipeline finished!")
