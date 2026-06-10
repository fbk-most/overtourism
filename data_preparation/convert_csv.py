
import pandas as pd
from utils import get_s3, log_dataframe, put_dataframe, get_dataframe
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
PATH_TO_DATA_PREPARATION = Path(__file__).parent.parent.resolve() / 'data_preparation'
assert PATH_TO_DATA_PREPARATION.exists(), f"Path {PATH_TO_DATA_PREPARATION} does not exist"

def download_and_convert_csv_to_parquet(input_path, local = True):
    logging.info(f"Starting the process of conversion for: {input_path}")

    if local : 
        logging.info("Reading CSV file from local path...")
        obj_df = pd.read_csv(PATH_TO_DATA_PREPARATION / input_path)
    else: 
        logging.info("Downloading CSV item from platform...")
        try:
            obj_df = get_dataframe(input_path)
        except:
            obj_df = pd.read_csv(get_s3(input_path))

    if local:
        logging.info("Saving locally in parquet format...")
        put_dataframe(obj_df, name=Path(input_path).stem, type="parquet")
    else: 
        logging.info("Saving on platform in parquet format...")
        log_dataframe(obj_df, Path(input_path).stem)
    logging.info("Process done")


if __name__ == "__main__":
    download_and_convert_csv_to_parquet("dati_transiti/dati_transito_veicolare.csv", local = True)