import os

# os.environ["PROJECT_NAME"] = "testot"
# os.environ["DATA_PREFIX"] = "testot/inputdata/"
# os.environ["CLI_ENV"] = "t1"
import pandas as pd

from data_preparation.utils import get_dataframe, get_s3, log_dataframe


def process_all_data():
    '''
    Minilally required input datasets:
    - vodafone_attendences.parquet
    - popolazione_2020_2024.parquet
    - presenze_Trentino_ISPAT_alb_xalb.csv
    - presenze_Trentino_ISPAT.csv
    - ComuniTrentini.geojson
    - TRENTINO-comuni_Vodafone_2023.geojson
    - TRENTINO-apt_2023.geojson
    - arrivi_trentino_ISPAT.csv
    - Annuario-TavXIII-per-comune-csv.csv
    - Elenco-comuni-italiani.csv
    - POSAS_2024_it_022_Trento.csv
    - mavfa-fbk_AIxPA_tourism-delivery_2025.08.22-zoning/*
    - vodafone-aixpa/*
    '''
    # ensure datasets are registered
    try:
        get_dataframe("vodafone_attendences")
    except:
        vodafone_attendences_df = pd.read_parquet(get_s3("vodafone_attendences.parquet"))
        log_dataframe(vodafone_attendences_df, "vodafone_attendences")

    # ensure datasets are registered
    try:
        get_dataframe("popolazione_2020_2024")
    except:
        popolazione_df = pd.read_parquet(get_s3("popolazione_2020_2024.parquet"))  # REFACTORING: revert to original file
        log_dataframe(popolazione_df, "popolazione_2020_2024")

    import data_preparation.diffusion.gen_diffusion as gd
    import data_preparation.gen_all_indexes as gai
    import data_preparation.gen_presence_stats as gps

    print("process diffusion data...")
    gd.prepare_data()
    print("process indexes...")
    gai.main()
    print("process presence stats...")
    gps.main()
    
if __name__ == "__main__":
    process_all_data()