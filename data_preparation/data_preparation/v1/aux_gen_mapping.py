# SPDX-License-Identifier: Apache-2.0
import pandas as pd
import json 
from pathlib import Path
from unidecode import unidecode
from utils import get_dataframe, get_s3
import logging 
import geopandas as gpd
from shapely.geometry import Point

logging.basicConfig(level=logging.INFO)

PATH_MAPPING = Path(__file__).parent.resolve() / "mapping"

REGIONE = 'Denominazione Regione'
PROVINCIA = "Denominazione dell'Unità territoriale sovracomunale \n(valida a fini statistici)"
CODICE_ISTAT = 'Codice Comune formato alfanumerico'
COMUNE = 'Denominazione in italiano'

## Define some helper functions 
def split_comuni(comune, list_com):
    """
    Helper function to separate "comuni" that are represented with a dash (-) in their name is a double language name
    """
    assert "-" in comune, f"Il comune {comune} non contiene il carattere '-'"
    if not comune in list_com:
        parts = comune.split("-")
        for p in parts:
            if p in list_com:
                return p.strip()
    return None 


def customize_unidecode(x):
    """
    Convert the input string, removing accents, converting to uppercase, and stripping whitespace. 
    """
    if x.endswith("'"):  # removes also trailing apostrophe if present
        x = x.removesuffix("'")
    return unidecode(x.strip().upper())


def extract_comuni_from_geojson_comuni(geojson_data):
    print("Estrazione comuni presenti nel geojson dei confini comunali del Trentino:")

    features = geojson_data["features"]
    name = []
    for f in features:
        if 'name' in f["properties"].keys():
            name.append(f["properties"]["name"].upper())
        elif 'com_name_upper' in f["properties"].keys():
            name.append(f["properties"]["com_name_upper"].upper())
        else:
            print("warning: no name key in the geojson")
    return name 


## Define the main functions 

def generate_ISTAT_mapping(istat_csv, output_json = PATH_MAPPING / "mapping_comuni_ISTAT.json"):
    """
    Generates a reference json mapping comuni and ISTAT codes.

    Parameters:
        istat_csv : csv
            Path to the CSV file containing ISTAT data.
        output_json : str, optional
            Path to save the output mapping JSON file"

    Returns:
        dict
            A dictionary mapping each comune to its ISTAT code.
    """
    logging.info("Generazione del mapping di riferimento COMUNI ISTAT -> IDS")

    # Load ISTAT data
    output_json.parent.mkdir(parents=True, exist_ok=True)
    table = pd.read_csv(get_s3(istat_csv), encoding='latin1', sep=';')
    df_trento = table[table[PROVINCIA] == 'Trento'] 
    map_cc = {customize_unidecode(comune): codice for comune, codice in zip(df_trento[COMUNE], df_trento[CODICE_ISTAT])}
    
    # Save to JSON
    with open(output_json, 'w') as f:
        logging.info(f"Salvataggio mapping ISTAT in {output_json}")
        json.dump(map_cc, f, indent=4, ensure_ascii=False)
    logging.info("Mapping generato con successo.\n")

    return map_cc


def check_comune_in_mapping(comune, mapping):
    """
    Helper functions which checks if a "comune" is in the reference json map (and returns its ISTAT code). 
    If comune is not found, it tries to find a match by finding dash (-) and splitting the name. 
    If not found, it saves "NA" as ISTAT code (and it is left to manual completion).

    Parameters: 
        comune : str
            the name of the comune to check
        mapping : json
            the reference mapping json with comuni and ISTAT codes

    Returns:
        str
            the ISTAT code of the comune (or "NA" if not found)
    """ 
    comune = customize_unidecode(comune)
    if comune in mapping:
        return mapping[comune]
    elif "-" in comune:   # checks if comune is an aggregation with a dash (-)
        c = split_comuni(comune, mapping.keys())
        if c is not None:
            return mapping[c]
        else: 
            logging.info(f"Warning: non trovato il comune: {comune} Aggiunto NA come codice ISTAT (da modificare manualmente).")
            return "NA"
    else:
        logging.info(f"Comune {comune} non trovato in mapping ISTAT. Aggiunto 'NA' come codice ISTAT (da modificare manualmente).")
        return "NA"


def compare_mapping(column, mapping_json_ISTAT, saving = False, savepath = PATH_MAPPING / "compared.json"):
    """
    Compares a list of "comuni" and checks if all comuni have ISTAT code in the reference map JSON, using the helper funciton check_comune_in_mapping.

    Parameters
        column : list
            the list containing the names of the comuni 
        mapping_json_ISTAT : json
            Path to the JSON file containing the reference map
        saving : bool, optional
            Whether to save the output mapping to a JSON file. Default is False.
        savepath : str, optional
            Path to save the output mapping JSON file if saving is True. Default is "compared.json".
    
    Returns:
        dict
            A dictionary mapping each comune to its ISTAT code (or "NA" if not found). 
    """
    # Load mapping data
    with open(mapping_json_ISTAT, 'r') as f:
        reference_mapping = json.load(f)
    
    new = {} 
    for comune in column:
        new[comune] = check_comune_in_mapping(comune, reference_mapping)
            
    if saving:
        logging.info(f"Salvataggio mapping in {savepath}")
        with open(savepath, 'w') as f:
            json.dump(new, f, indent=4, ensure_ascii=False)
    logging.info("Mapping generato con successo.\n")

    return new 

def compare_mapping_Vodafone(column, mapping_json_ISTAT, saving = False, savepath = PATH_MAPPING / "compared_Vodafone.json"):
    """
    Compares a list of "comuni" from Vodafone data (or any data containing aggregations with '+' in their names) and checks if all comuni have ISTAT code in the reference map JSON, using the helper funciton check_comune_in_mapping.  
    
    Parameters
        column : list
            the list containing the names of the comuni 
        mapping_json_ISTAT : json
            Path to the JSON file containing the reference map
        saving : bool, optional
            Whether to save the output mapping to a JSON file. Default is False.
        savepath : str, optional
            Path to save the output mapping JSON file if saving is True. Default is "compared_Vodafone.json".
    Returns:
        dict     
            A dictionary of list, mapping each comune (or aggregation of comuni) to its ISTAT codes (or ["NA"] if not found).
    """
    logging.info("Associazione comuni VODAFONE (o aggregazioni) -> IDS:")

    # Load mapping data
    with open(mapping_json_ISTAT, 'r') as f:
        reference_mapping = json.load(f)
    new = {} 

    for comune in column:
        if pd.notna(comune):
            if '+' in comune:   # checks if comune is an aggregation 
                logging.debug("Comune aggregato trovato: ", comune)
                parts = comune.split('+')
                for p in parts:
                    if comune not in new:
                        new[comune] = [check_comune_in_mapping(p, reference_mapping)]
                    else: 
                        new[comune].extend([check_comune_in_mapping(p, reference_mapping)])
            else:
                new[comune] = [check_comune_in_mapping(comune, reference_mapping)]
        else:
            logging.info("Comune None trovato in Vodafone, ignorato.")

    if saving:
        logging.info(f"Salvataggio mapping in {savepath}")
        with open(savepath, 'w') as f:
            json.dump(new, f, indent=4, ensure_ascii=False)
    logging.info("Mapping generato con successo.\n")

    return new 

def map_comuni_into_apt(geojson_data_comuni, geojson_data_apt, saving = False, savepath = PATH_MAPPING / "map_comuni_into_apt.json"):
    """
    Function which map a set of comuni into their corresponding apt
    """
    logging.info("Generazione del mapping COMUNI -> APT")
    gdf_apt = gpd.GeoDataFrame.from_features(geojson_data_apt)
    gdf_comuni = gpd.GeoDataFrame.from_features(geojson_data_comuni)
    cdict = {key: [] for key in gdf_apt['desc'].unique()}
    apt_match = None 

    for idx, com in gdf_comuni.iterrows():
        point = Point(com['geo_point_2d']['lon'], com['geo_point_2d']['lat'])
        id_comune = com['com_code'].lstrip('0')
        apt_match = gdf_apt[gdf_apt.contains(point)]

        if not apt_match.empty:            
            assert len(apt_match) < 2 
            apt_name = apt_match['desc'].iloc[0]

            assert apt_name in cdict
            cdict[apt_name].append(id_comune)
        else:
            print(f"No correnpondence for comune {com}")

    if saving:
        logging.info(f"Salvataggio mapping in {savepath}")
        with open(savepath, 'w') as f:
            json.dump(cdict, f, indent=4, ensure_ascii=False)
    logging.info("Mapping generato con successo.\n")

    return cdict 



if __name__ == "__main__":
    if not PATH_MAPPING.exists() or (PATH_MAPPING.is_dir() and not any(PATH_MAPPING.iterdir())):
        from gen_capacity_indexes import get_Vodafone_location_name 

        istat_csv =  "Elenco-comuni-italiani.csv"
        apt_geojson = "TRENTINO-apt_2023.geojson"
        comuni_geojson = "ComuniTrentini.geojson" # Open geojson about "confini comunali"
        annuario_csv = "Annuario-TavXIII-per-comune-csv.csv"

        geojson_data_comuni = json.load(get_s3(comuni_geojson))
        geojson_data_apt = json.load(get_s3(apt_geojson))

        popolazione_df = get_dataframe("popolazione_2020_2024")  # Dataframe popolazione dal 2020
        popolazione_df["comune"] = popolazione_df["comune"].apply(lambda x : customize_unidecode(x))

        vodafone_attendences_df = get_dataframe("vodafone_attendences")
        vodafone_attendences_df["anno"] = pd.to_datetime(vodafone_attendences_df["date"]).dt.year
        vodafone_attendences_df["comune"] = vodafone_attendences_df.loc[vodafone_attendences_df["locType"] == 'TN_MKT_AL_3', "locId"].apply(
            lambda x: get_Vodafone_location_name(x)
        )

        strutture_ospitalita_trentino_df = pd.read_csv(get_s3(annuario_csv), nrows=2000)
        strutture_ospitalita_trentino_df = strutture_ospitalita_trentino_df[strutture_ospitalita_trentino_df['anno'] > 2019].copy()  
        strutture_ospitalita_trentino_df["comune"] = strutture_ospitalita_trentino_df["comune"].apply(lambda x : customize_unidecode(x).replace("0", "-")) # consider just the years after 2019

        dict_ref = generate_ISTAT_mapping(istat_csv)
        mca = map_comuni_into_apt(geojson_data_comuni, geojson_data_apt, saving= True, savepath=PATH_MAPPING / "map_comuni_into_apt.json")
        comuni = extract_comuni_from_geojson_comuni(geojson_data_comuni)
        mc = compare_mapping_Vodafone(comuni, PATH_MAPPING / "mapping_comuni_ISTAT.json", True, PATH_MAPPING / "comuniTrentino.json")
        logging.info("Associazione POPOLAZIONE -> IDS:")
        mp = compare_mapping(popolazione_df['comune'].unique(), PATH_MAPPING / "mapping_comuni_ISTAT.json", True, PATH_MAPPING / "popolazione_Trento.json")
        mv = compare_mapping_Vodafone(vodafone_attendences_df['comune'].unique(), PATH_MAPPING / "mapping_comuni_ISTAT.json", True, PATH_MAPPING / "vodafone_Trento.json")
        logging.info("Associazione STRUTTURE OSPITALITA -> IDS:")
        compare_mapping(strutture_ospitalita_trentino_df['comune'].unique(), PATH_MAPPING / "mapping_comuni_ISTAT.json", True, PATH_MAPPING / "strutture_ospitalita_Trento_2020.json")

        print("**** THE GENERATE FILES NEED NOW TO BE EDITED BY HAND!   ****")
        exit(1)

    else:
        print("**** THE FILES GENERATED BY THIS SCRIPT NEED TO BE EDITED BY HAND!   ****")
        print("**** EXECUTE ONLY IF YOU KNOW WHAT YOU ARE DOING (AND HOW TO DO IT)! ****")
        exit(1)
