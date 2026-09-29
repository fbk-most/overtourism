"""
PIPELINE: 

Input : Server (S3)
Output: Output/final_data/   (phen_popolazione, phen_strutture, phen_presenze)
        or upload to the platform 

The entire pipeline is executed, generating phenomena from scratch. 
The intermediate steps save the intermediate results (standardized, processed)
"""
import logging
from download_raw_data import download_raw_data
from standardize_raw_data import standardize_raw_data
from process_data import process_data
from gen_base_phenomenon_dataframes import compute_phenomenon_dataframes

if __name__ == "__main__":
    logging.info("Step 0: download raw data into Output/raw_data")
    download_raw_data()
    logging.info("Step 1: uniform raw data into Output/normalized")
    standardize_raw_data()
    logging.info("Step 2: process normalized data into Output/data_processed")
    process_data()
    logging.info("Step 3: saves final phenomena into Output/final_data")
    compute_phenomenon_dataframes()
    logging.info("Pipeline finished!")
