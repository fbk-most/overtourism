# SPDX-License-Identifier: Apache-2.0
import pandas as pd
import datetime as dt
from data_preparation.utils import get_dataframe, put_dataframe, log_dataframe, get_s3
import json 
from pathlib import Path
import logging
import numpy as np
from unidecode import unidecode

logging.basicConfig(level=logging.INFO)

## Define constants 
EXCEPT_BOOLEAN = False # utility functions
MOLVENO = "MOLVENO" # ISPAT location encoding in dataset presenze
# Vodafone location encoding
locId_LAGO_MOLVENO = "LAGO_MOLV"
locId_MOLVENO = "27"
locId_ANDALO = "166"
locID_ALTOPIANO_TUTTO = "105"

## Columns of the dfs
CATEGORIA_ALBERGHIERE = "alberghieri strutture"
CATEGORIA_EXTRA_ALBERGHIERE = "extra alb. Strutture"
CATEGORIA_TOT_CONVENZIONALI = "tot convenzionali strutture"
CATEGORIA_ALLOGGI_PRIVATI = "all. privati numero"
CATEGORIA_ALLOGGI_DISPOSIZIONE = "all.disposizione numero"
CATEGORIA_TOT_TUTTI = "COMPLESSIVO numero"
CATEGORIA_ALBERGHIERE_LETTI = "alberghieri posti_letto"
CATEGORIA_EXTRA_ALBERGHIERE_LETTI = "extra alb. Posti_letto"
CATEGORIA_TOT_CONVENZIONALI_LETTI = "tot convenzionali posti_letto"
CATEGORIA_ALLOGGI_PRIVATI_LETTI = "all. privati posti_letto"
CATEGORIA_ALLOGGI_DISPOSIZIONE_LETTI = "all. disposizione posti_letto"
CATEGORIA_TOT_TUTTI_LETTI = "COMPLESSIVO posti_letto"

PATH_MAPPING = Path(__file__).parent.resolve() / "mapping"

# Open geojson about "confini comunali"
geojson_comuni_json_data = json.load(get_s3("TRENTINO-comuni_Vodafone_2023.geojson"))

def get_Vodafone_location_name(locId):
    features = geojson_comuni_json_data["features"]
    for f in features:
        if f["properties"]["id"] == locId:
            return f["properties"]["name"].upper()

def get_available_years(df1, pop_df):
    """function that returns the list of years for which the index can be computed (depends on available data)"""
    pop_years = pop_df["anno"].unique().astype(int)  # years for which population data are available
    df1_years = df1["anno"].unique().astype(int)
    return [year for year in pop_years if year in df1_years]

def aggregate_popToAmbito(df_comuni, df_ambiti):
    """Adds a column 'popolazione' (sum of each comune), for each aggregation"""

    def compute_popolazione(row): 
        anno = row['anno']
        ids = row['ID'] 
        df_ID = df_comuni[df_comuni['ID'].isin(ids) & (df_comuni['anno'] == anno)]
        if df_ID.empty:
            return np.nan
        return df_ID['popolazione'].sum()
    
    df_ambiti['popolazione'] = df_ambiti.apply(
        lambda row: compute_popolazione(row), axis=1
    )
    return df_ambiti

def customize_unidecode(x):
    """
    Convert the input string, removing accents, converting to uppercase, and stripping whitespace. 
    """
    if x.endswith("'"):  # removes also trailing apostrophe if present
        x = x.removesuffix("'")
    return unidecode(x.strip().upper())



## Index calculation 
## ------------------------------------------
##  INDICI DI IMPATTO DEL TURISMO
## ------------------------------------------

## ------------------------------------------
# INCIDENZA DEL NUMERO DI STRUTTURE RICETTIVE NON CONVENZIONALI (alloggi turistici e alloggi a disposizione) 
# rispetto al numero totale di STRUTTURE RICETTIVE
# Calcolato come: Numero strutture non convenziali / numero totale strutture ricettive
# INCIDENZA DEL NUMERO DI POSTI LETTO NON CONVENZIONALI (alloggi turistici e alloggi a disposizione) 
# rispetto al numero totale di POSTI LETTO
# Calcolato come: Numero posti letto in strutture non convenziali / numero totale posti letto
## ------------------------------------------

def get_index_incidenza_strutture_non_convenz(strutture_ospitalita_trentino_df, year):
    """ function that computes the index "incidenza strutture non convenzionali" """
    df_res = strutture_ospitalita_trentino_df[strutture_ospitalita_trentino_df['anno'] == year].copy()
    df_res['tot_strutture'] = df_res[CATEGORIA_TOT_CONVENZIONALI] + df_res[CATEGORIA_ALLOGGI_PRIVATI]
    assert (df_res['tot_strutture'] >= df_res[CATEGORIA_ALLOGGI_PRIVATI]).all(), f"Errore: strutture ricettive totali < strutture non convenzionali per il comune {df_res[df_res['tot_strutture'] < df_res[CATEGORIA_ALLOGGI_PRIVATI]]['comune']} e anno {year}"

    if not df_res[df_res[CATEGORIA_ALLOGGI_PRIVATI].isna()].empty:
        logging.info("INCIDENZA OSPITALITA` NON CONVENZIONALE")
        logging.info("ANNO: " + str(year))
        logging.info(f"TOTALE STRUTTURE NON CONVENZIONALI NON DEFINITO PER I COMUNI: {', '.join(df_res[df_res[CATEGORIA_ALLOGGI_PRIVATI].isna()]['comune'].tolist())}")
    if not df_res[df_res['tot_strutture'].isna()].empty:
        logging.info("INCIDENZA OSPITALITA` NON CONVENZIONALE")
        logging.info("ANNO: " + str(year))
        logging.info(f"TOTALE STRUTTURE RICETTIVE NON DEFINITO PER I COMUNI: {', '.join(df_res[df_res['tot_strutture'].isna()]['comune'].tolist())}\n")
    if not df_res[df_res['tot_strutture'] == 0].empty: 
        logging.info("INCIDENZA OSPITALITA` NON CONVENZIONALE")
        logging.info("ANNO: " + str(year))
        logging.info(f"TOTALE STRUTTURE RICETTIVE = 0 PER I COMUNI: {', '.join(df_res[df_res['tot_strutture'] == 0]['comune'].tolist())} \n")

    logging.debug("Incidenza del numero di strutture ricettive non convenzionali (alloggi turistici) rispetto al numero totale di strutture ricettive (alberghi + strutture extra alberghiere + alloggi turistici)")
    df_res['incidenza_strutture_non_conv'] = np.where(
        df_res['tot_strutture'] == 0, 0, 
        df_res[CATEGORIA_ALLOGGI_PRIVATI] / df_res['tot_strutture'] 
    )
    df_res.rename(columns={CATEGORIA_ALLOGGI_PRIVATI: 'tot_strutture_non_conv'}, inplace=True)
    return df_res[['anno', 'comune', 'ID', 'tot_strutture', 'tot_strutture_non_conv', 'incidenza_strutture_non_conv']]


def get_index_incidenza_postiletto_non_convenz(strutture_ospitalita_trentino_df, year):
    """ function that computes the index "incidenza posti letto non convenzionali" """
    df_res = strutture_ospitalita_trentino_df[strutture_ospitalita_trentino_df['anno'] == year].copy()
    df_res['tot_postiletto'] = df_res[CATEGORIA_TOT_CONVENZIONALI_LETTI] + df_res[CATEGORIA_ALLOGGI_PRIVATI_LETTI]
    assert all(df_res['tot_postiletto'] >= df_res[CATEGORIA_ALLOGGI_PRIVATI_LETTI]), f"Errore: posti letto totali < posti letto non convenzionali per il comune {df_res[df_res['tot_postiletto'] >= df_res[CATEGORIA_ALLOGGI_PRIVATI_LETTI]]['comune']} e anno {year}" 

    if not df_res[df_res[CATEGORIA_ALLOGGI_PRIVATI_LETTI].isna()].empty:
        logging.info("INCIDENZA POSTI LETTO NON CONVENZIONALI")
        logging.info("ANNO: " + str(year))
        logging.info(f"TOTALE POSTI LETTO NON CONVENZIONALI NON DEFINITO PER I COMUNI: {', '.join(df_res[df_res[CATEGORIA_ALLOGGI_PRIVATI_LETTI].isna()]['comune'].tolist())}")
    if not df_res[df_res['tot_postiletto'].isna()].empty: 
        logging.info("INCIDENZA POSTI LETTO NON CONVENZIONALI")
        logging.info("ANNO: " + str(year))
        logging.info(f"TOTALE POSTI LETTO NON DEFINITO PER I COMUNI: {', '.join(df_res[df_res['tot_postiletto'].isna()]['comune'].tolist())}\n")
    if not df_res[df_res['tot_postiletto'] == 0].empty:
        logging.info("INCIDENZA POSTI LETTO NON CONVENZIONALI")
        logging.info("ANNO: " + str(year))
        logging.info(f"TOTALE POSTI LETTO = 0 PER I COMUNI: {', '.join(df_res[df_res['tot_postiletto'] == 0]['comune'].tolist())} \n")
        
    logging.debug("Incidenza del numero di posti letto in strutture ricettive non convenzionali (alloggi turistici) rispetto al numero totale di posti letto")
    df_res['incidenza_postiletto_non_conv'] = np.where(
        df_res['tot_postiletto'] == 0, 0,
        df_res[CATEGORIA_ALLOGGI_PRIVATI_LETTI] / df_res['tot_postiletto']
    )
    df_res.rename(columns={CATEGORIA_ALLOGGI_PRIVATI_LETTI: 'tot_postiletto_non_conv'}, inplace=True)
    return df_res[['anno', 'comune', 'ID', 'tot_postiletto', 'tot_postiletto_non_conv', 'incidenza_postiletto_non_conv']]


def compute_df_incidenza_ospit_non_convenz_trentino(strutture_ospitalita_trentino_df):
    """function that computes a dataframe containing the index "incidenza strutture non convenzionali" """
    logging.info("## creazione tabella incidenza non convenzionale Trentino in corso ")
    years = strutture_ospitalita_trentino_df["anno"].unique()
    results1, results2 = [], []
    for year in years:
        df_incidenza_strutture = get_index_incidenza_strutture_non_convenz(strutture_ospitalita_trentino_df, year)  
        results1.append(df_incidenza_strutture[df_incidenza_strutture['incidenza_strutture_non_conv'].notna()])  
        df_incidenza_postiletto = get_index_incidenza_postiletto_non_convenz(strutture_ospitalita_trentino_df, year)
        results2.append(df_incidenza_postiletto[df_incidenza_postiletto['incidenza_postiletto_non_conv'].notna()])  

    d1 = pd.concat(results1, ignore_index=True)
    d2 = pd.concat(results2, ignore_index=True)
    logging.debug("completato")
    return pd.DataFrame(data=d1).set_index(["comune", "anno"]).sort_index(level="comune"), pd.DataFrame(data=d2).set_index(["comune", "anno"]).sort_index(level="comune")


## ------------------------------------------
# TASSO DI RICETTIVITA`
# Il TASSO DI RICETTIVITA’ è ottenuto dividendo il numero dei letti negli esercizi ricettivi 
# (esclusi gli alloggi a disposizione) per gli abitanti della stessa area. 
# Esso rappresenta la potenzialità turistica di un’area relativamente alle altre 
# risorse economiche.
## ------------------------------------------

def get_index_tasso_ricettivita(year, strutture_ospitalita_trentino_df, trentino_pop_df):
    """ function that computes the index "tasso di ricettività" """
    df_year_res = trentino_pop_df[
        (trentino_pop_df["anno"] == year)
    ].copy()
    strutture_osp_year = strutture_ospitalita_trentino_df[  
        (strutture_ospitalita_trentino_df["anno"] == year)
    ].copy()
    strutture_osp_year['posti_letto'] = strutture_osp_year[CATEGORIA_TOT_CONVENZIONALI_LETTI] + strutture_osp_year[CATEGORIA_ALLOGGI_PRIVATI_LETTI]
    # df_year_res.merge(strutture_osp_year[['comune', 'posti_letto']], on = 'comune', how ='left')
    df_year_res = df_year_res.merge(strutture_osp_year[['comune', 'posti_letto']], on = 'comune', how ='left')
    
    if not df_year_res[df_year_res['popolazione'].isna()].empty:
        logging.info("TASSO DI RICETTIVITA`")
        logging.info("ANNO: " + str(year))
        logging.info(f"POPOLAZIONE NON DEFINITA PER I COMUNI: {', '.join(df_year_res[df_year_res['popolazione'].isna()]['comune'].tolist())}")
    if not df_year_res[df_year_res['posti_letto'].isna()].empty:
        logging.info("TASSO DI RICETTIVITA`")
        logging.info("ANNO: " + str(year))
        logging.info(f"POSTI LETTO NON DEFINITI PER I COMUNI: {', '.join(df_year_res[df_year_res['posti_letto'].isna()]['comune'].tolist())}\n")
    if not df_year_res[df_year_res['popolazione'] == 0].empty:
        logging.info("TASSO DI RICETTIVITA`")
        logging.info("ANNO: " + str(year))
        logging.info(f"POPOLAZIONE = 0 PER I COMUNI: {', '.join(df_year_res[df_year_res['popolazione'] == 0]['comune'].tolist())} \n")  

    logging.debug("Il tasso di ricettività è ottenuto dividendo il numero dei letti negli esercizi ricettivi (esclusi gli alloggi a disposizione) per gli abitanti della stessa area.")
    logging.debug("Esso rappresenta la potenzialità turistica di un’area relativamente alle altre risorse economiche.")
    df_year_res['ricettivita'] = np.where(
        df_year_res['popolazione'] == 0, np.nan,
        df_year_res['posti_letto'] / df_year_res['popolazione']
    )
    return df_year_res[['anno', 'comune', 'popolazione', 'ID', 'posti_letto', 'ricettivita']]


def compute_df_tasso_ricettivita_trentino(strutture_ospitalita_trentino_df, trentino_pop_df):
    """function that computes a dataframe collecting the values of the index "tasso di ricettività" """
    logging.info("## creazione tabella tasso di ricettività Trentino in corso")
    years = get_available_years(strutture_ospitalita_trentino_df, trentino_pop_df)

    results = []
    for year in years:
        df_ricettivita = get_index_tasso_ricettivita(year, strutture_ospitalita_trentino_df, trentino_pop_df)
        results.append(df_ricettivita[df_ricettivita['ricettivita'].notna()]) 
    d = pd.concat(results, ignore_index=True)
    logging.debug("completato")
    return pd.DataFrame(data=d).set_index(["comune", "anno"]).sort_index(level="comune")


## ------------------------------------------
# TASSO DI TURISTICITA`
# Il TASSO DI TURISTICITA` è ottenuto dividendo il numero medio di turisti negli esercizi 
# ricettivi (esclusi gli alloggi a disposizione) per gli abitanti della stessa area. 
# Esso rappresenta quindi l’effettivo peso del turismo rispetto alle dimensioni della zona.
## ------------------------------------------

def get_index_tasso_turisticita(trentino_pop_df, vodafone_attendences_df, start_date, end_date):
    ## notice: the function for the moment does not support the case of start date and end date in different years
    year = int(end_date.split("-")[0])
    days = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days + 1
    assert days > 0, "Errore nelle date in ingresso"
    
    presenze_df = vodafone_attendences_df[
            (vodafone_attendences_df["userProfile"] == "TOURIST") &
            (vodafone_attendences_df['comune'].notna()) &
            (vodafone_attendences_df["date"] >= start_date) & 
            (vodafone_attendences_df["date"] <= end_date)]
    assert presenze_df['locType'].iloc[0] == 'TN_MKT_AL_3' and presenze_df['locType'].nunique() == 1, "Attenzione: alcuni codici nella colonna locType non rappresentano comuni"
    aggregations = {
        "anno": "last",
        "ID": "first", 
        "value": "sum"        
    }
    presenze_df_aggregated = presenze_df.groupby("comune").agg(aggregations).reset_index()
    presenze_df_aggregated.rename(columns={'value': 'presenze_totali'}, inplace=True)
    presenze_df_aggregated['mean_tourists'] = presenze_df_aggregated["presenze_totali"] / days  
    presenze_df_aggregated = aggregate_popToAmbito(trentino_pop_df, presenze_df_aggregated) # add population column
    assert presenze_df_aggregated['ID'].notna().all(), "Errore: alcuni comuni non hanno ID associato" # it should not pass here, since at least one id should be present (also if it is NA)

    if not presenze_df_aggregated[presenze_df_aggregated['ID'].apply(lambda x: 'NA' in x)].empty:
        logging.info("TASSO DI TURISTICITA`")
        logging.info("ANNO: " + str(year))
        logging.info(f"COMUNI CON ID 'NA': {', '.join(presenze_df_aggregated[presenze_df_aggregated['ID'].apply(lambda x: 'NA' in x)]['comune'].tolist())} \n")
        presenze_df_aggregated = presenze_df_aggregated[
            presenze_df_aggregated['ID'].apply(lambda x: 'NA' not in x)
        ]  # remove rows with ID 'NA'

    if not presenze_df_aggregated[presenze_df_aggregated['popolazione'].isna()].empty:
        logging.info("TASSO DI TURISTICITA`")
        logging.info("ANNO: " + str(year))
        logging.info(f"COMUNI CON POPOLAZIONE NON DEFINITA: {', '.join(presenze_df_aggregated[presenze_df_aggregated['popolazione'].isna()]['comune'].tolist())} \n")   
    
    if not presenze_df_aggregated[presenze_df_aggregated['popolazione'] == 0].empty:
        logging.info("TASSO DI TURISTICITA`")   
        logging.info("ANNO: " + str(year))
        logging.info(f"COMUNI CON POPOLAZIONE = 0: {', '.join(presenze_df_aggregated[presenze_df_aggregated['popolazione'] == 0]['comune'].tolist())} \n")

    presenze_df_aggregated['turisticita'] = np.where(
        (presenze_df_aggregated['popolazione'] == 0), np.nan,
        presenze_df_aggregated['mean_tourists'] / presenze_df_aggregated['popolazione'])

    return presenze_df_aggregated[['anno', 'comune', 'ID', 'popolazione', 'turisticita']]
    

def compute_df_tasso_turisticita_trentino_Vodafone(start_date, end_date, vodafone_attendences_df, trentino_pop_df):
    """function that computes a dataframe collecting the value of the index "tasso di turisticita`" """
    logging.info(f"## creazione tabella tasso di turisticità Trentino in corso ({start_date}, {end_date})")
    years = get_available_years(vodafone_attendences_df, trentino_pop_df)
    assert int(start_date.split("-")[0]) in years, "Errore: anno di inizio non disponibile"
    assert int(end_date.split("-")[0]) in years, "Errore: anno di fine non disponibile"
    df_turisticita = get_index_tasso_turisticita(trentino_pop_df, vodafone_attendences_df, start_date, end_date) 
    df_turisticita = df_turisticita[df_turisticita['turisticita'].notna()]

    ids_pop_df = trentino_pop_df['ID'].explode().dropna().unique()
    ids_vodafone = vodafone_attendences_df['ID'].explode().dropna().unique()
    difference = [ind for ind in ids_pop_df if ind not in ids_vodafone]
    if difference:
        logging.info("TASSO DI TURISTICITA`")
        missing_data = trentino_pop_df[trentino_pop_df['ID'].isin(difference)]
        missing_data = missing_data[['comune', 'ID']].drop_duplicates()
        logging.info(f"COMUNI CON ID NON PRESENTI NEL DATASET VODAFONE: {', '.join(missing_data['comune'].tolist())} \n")
    logging.debug(f"## Completato")
    return pd.DataFrame(data=df_turisticita).set_index(["comune", "anno"])


## ------------------------------------------
# TASSO DI VARIAZIONE PERCENTUALE
# Il TASSO DI VARIAZIONE PERCENTUALE è calcolato come la variazione percentuale 
# media annua degli arrivi turistici su un certo numero di anni.
## ------------------------------------------
def get_tasso_di_variazione_percentuale(area, years, turisti_df):
    assert area in turisti_df['comune'].unique(), f"{area} non e' presente nel dataset"
    turisti_df_filtered = turisti_df[
        (turisti_df["comune"] == area) &
        (turisti_df['anno'].isin(years))
    ]
    annual_arrival_rates = turisti_df_filtered.groupby(['anno'])['arrivi'].sum()
    annual_arrival_change_rate = annual_arrival_rates.pct_change() * 100

    return annual_arrival_change_rate.dropna().mean(), {y:annual_arrival_rates[y] for y in years}


def calculate_tasso_variazione_percentuale(df_turisti, years = None): 
    # takes the entire years available
    logging.info(f"## creazione tabella tasso di variazione percentuale")
    if years is None: 
        years = df_turisti['anno'].unique()
    else:
        assert all(x in df_turisti['anno'].unique() for x in years), f"Attenzione: i dati per gli anni ({[anno for anno in years if anno not in df_turisti['anno'].unique()]}) non sono disponibili"

    logging.info(f"Calcolo del tasso di variazione percentuale per gli anni: {years}")
    aree = df_turisti['comune'].dropna().unique()

    d = {
        "comune": [],
        "tasso_variazione_perc": [],
    } | {
        f"anno_{y}": [] for y in years
    } | {"anno": []}
    for area in aree:
        percent, year_values = get_tasso_di_variazione_percentuale(area, years, df_turisti)
        if percent is None :
            continue 
        d["comune"].append(area) 
        d["tasso_variazione_perc"].append(percent)
        for y in years:
            d[f"anno_{y}"].append(year_values[y])
        d['anno'].append(years[-1])
    logging.debug("completato")
    return pd.DataFrame(data=d).set_index(["comune", "anno"])


## ------------------------------------------
# TASSO DI STAGIONALITA'
# Il TASSO DI STAGIONALITA` è calcolato come il rapporto tra il numero di turisti
# presenti in alta stagione e il numero di turisti presenti in bassa stagione.
## ------------------------------------------
def get_index_stagionalita(movimento_turistico, bs_dates, as_dates):
    year = bs_dates[0].split("-")[0]
    df_year = movimento_turistico[movimento_turistico['anno'] == int(year)].dropna(subset=['comune']).copy()

    comuni_as = df_year.loc[(df_year['date'] >= as_dates[0]) & (df_year['date'] <= as_dates[1]), 'comune'].unique()                             # distingish no available data and zero values
    no_data_as = [c for c in df_year['comune'].unique() if c not in comuni_as]    # computed just for alta stagione because for bs they are excluded by division by 0 
    if no_data_as:
        logging.info(f"INDICE DI STAGIONALITA`: ANNO {year}")
        logging.info(f"ALTA STAGIONE ({as_dates[0]} - {as_dates[1]}): Nessun dato di alta stagione disponibile nei comuni: {', '.join(no_data_as)}")

    df_year['nturisti_alta_stagione'] = df_year['value'].where((df_year['date'] >= as_dates[0]) & (df_year['date'] <= as_dates[1]), 0)
    df_year['nturisti_bassa_stagione'] = df_year['value'].where((df_year['date'] >= bs_dates[0]) & (df_year['date'] <= bs_dates[1]) , 0)
    df_agg = df_year.groupby('comune').agg(
        nturisti_alta_stagione=('nturisti_alta_stagione', 'sum'),
        nturisti_bassa_stagione=('nturisti_bassa_stagione', 'sum')
    ).reset_index()
    no_bs = df_agg[df_agg['nturisti_bassa_stagione'] == 0]
    no_as = df_agg[df_agg['nturisti_alta_stagione'] == 0]

    # values zero logging
    if not no_bs.empty: 
        logging.info(f"INDICE DI STAGIONALITA`: ANNO {year}")
        logging.info(f"BASSA STAGIONE ({bs_dates[0]} - {bs_dates[1]}): MOVIMENTO TURISTICO = 0 nei comuni: {', '.join(no_bs['comune'].tolist())}")   # division by 0 produces NaN
    if not no_as.empty:         
        logging.info(f"INDICE DI STAGIONALITA`: ANNO {year}")
        logging.info(f"ALTA STAGIONE ({as_dates[0]} - {as_dates[1]}): MOVIMENTO TURISTICO = 0 nei comuni: {', '.join(no_as['comune'].tolist())}")  

    df_agg['stagionalita'] = np.where(
        (df_agg['nturisti_bassa_stagione'] == 0) | (df_agg['comune'].isin(no_data_as)), np.nan,
        df_agg['nturisti_alta_stagione'] / df_agg['nturisti_bassa_stagione']
    )
    assert all(df_year.loc[df_year['comune'].notna(), "locType"] == 'TN_MKT_AL_3'), "Attenzione: alcuni codici nella colonna locType non rappresentano comuni"
    return df_agg

def compute_stagionalita_presenze(bs_dates: tuple , as_dates: tuple, movimento_turistico: pd.DataFrame, json_vodafone: json, years = None):
    if years is None: 
        years = movimento_turistico['anno'].unique()
    else: 
        assert all(x in movimento_turistico['anno'].unique() for x in years), f"Attenzione: i dati per gli anni ({[anno for anno in years if anno not in movimento_turistico['anno'].unique()]}) non sono disponibili"
    logging.info(f"## creazione tabella stagionalita' delle presenze")
        
    movimento_turistico = movimento_turistico[
            ((movimento_turistico["userProfile"] == "TOURIST") |
            (movimento_turistico["userProfile"] == "VISITOR")) ] 
    
    results = []
    for year in years: 
        alta_stagione_year = (f"{year}-{as_dates[0]}", f"{year}-{as_dates[1]}")
        bassa_stagione_year = (f"{year}-{bs_dates[0]}", f"{year}-{bs_dates[1]}")
        df_index_stagionalita = get_index_stagionalita(movimento_turistico, bassa_stagione_year, alta_stagione_year)
        df_index_stagionalita = df_index_stagionalita[df_index_stagionalita['stagionalita'].notna()]
        if not df_index_stagionalita.empty:
            df_index_stagionalita['anno'] = year
            df_index_stagionalita['ID'] = df_index_stagionalita['comune'].map(json_vodafone)
            results.append(df_index_stagionalita[df_index_stagionalita["stagionalita"].notna()])  
        else:
            logging.info(f"Nessun dato disponibile per l'anno {year} nell'intervallo {bs_dates} - {as_dates}")

    d = pd.concat(results, ignore_index=True)
    logging.debug(f"## Completato")
    return pd.DataFrame(data=d).set_index(["comune", "anno"]).sort_index(level="comune")


## ------------------------------------------
# indice di MASSIMA ANTROPIZZAZIONE
## ------------------------------------------
# def get_population(location, year, trentino_pop_df):      
#     """ function that returns the population for a certain year and location """
#     try:
#         if (location in trentino_pop_df["comune"].unique()) and (year in trentino_pop_df["anno"].unique()):
#             pop = trentino_pop_df[ (trentino_pop_df["anno"] == year) & 
#                      (trentino_pop_df["comune"] == location) 
#                    ]["popolazione"].item()
#             return pop
#         return None
#     except: 
#         logging.info(f"Nessun dato *popolazione* disponibile per il comune {location} e anno {year}" )
#         return None
    
# def get_index_massima_antropizzazione(location, year, movimento_turistico, popolazione_df):
#     """ function that computes the index "indice di massima antropizzazione" """
#     assert location in movimento_turistico['territorio_comunale'].unique()
#     if location in popolazione_df["comune"].unique():
#         popolazione = get_population(location, year, popolazione_df)
#         if popolazione is None:
#             logging.info("INDICE MASSIMA ANTROPIZZAZIONE")
#             logging.info("LOCALITA': " + location)
#             logging.info("ANNO: " + str(year))
#             logging.info("POPOLAZIONE NON DEFINITA \n")
#             return location, None, None
#         elif popolazione == 0:
#             logging.info("INDICE MASSIMA ANTROPIZZAZIONE")
#             logging.info("LOCALITA': " + location)
#             logging.info("ANNO: " + str(year))
#             logging.info("POPOLAZIONE = 0 \n")
#             return location, popolazione, 0
        
#         movimento_turistico = movimento_turistico[
#             (movimento_turistico["territorio_comunale"] == location ) & 
#             (movimento_turistico["anno"] == str(year)) 
#         ]
#         max_value = movimento_turistico['arrivi'].max()   # maximum value of arrivals in year 
#         return location, popolazione, max_value, max_value / popolazione

#     else: 
#         logging.info("INDICE MASSIMA ANTROPIZZAZIONE")
#         logging.info("LOCALITA': " + location)
#         logging.info("ANNO: " + str(year))
#         if location not in movimento_turistico["territorio_comunale"].unique():
#             logging.info("COMUNE NON PRESENTE NEL DATASET DEL MOVIMENTO TURISTICO \n")
#             return location, None, None
#         elif location not in popolazione_df["comune"].unique():
#             logging.info("COMUNE NON PRESENTE NEL DATASET DELLA POPOLAZIONE \n")
#             return location, None, None
        
    
# def compute_df_massima_antropizzazione(movimento_turistico, popolazione_df, mturistico_json):
#     """function that computes a dataframe collecting the values of the index "indice di massima antropizzazione" """
#     years = get_available_years(movimento_turistico, popolazione_df)
#     comuni = movimento_turistico["territorio_comunale"].unique()
#     d = {
#           "comune": [],
#           "anno": [],
#           "ID": [], 
#           "popolazione": [],
#           "massimo_arrivi": [],
#           "massima_antropizzazione": [],
#      }
#     for comune in comuni:
#         id = str(mturistico_json(comune))
#         for year in years:
#             comune, popolazione, massimo_arrivi, massima_antropizzazione = (
#                 get_index_massima_antropizzazione(comune, year,
#                                                     movimento_turistico, popolazione_df))
#             if massima_antropizzazione is None:
#                 continue
#             d["comune"].append(comune)
#             d["anno"].append(year)
#             d["ID"].append(id)
#             d["popolazione"].append(popolazione)
#             d["massimo_arrivi"].append(massimo_arrivi)
#             d["massima_antropizzazione"].append(massima_antropizzazione)
    
#     return pd.DataFrame(data=d).set_index(["comune", "anno"])


def compute_index_dataframes():
    """ Main function to compute all the indexes for Trentino"""
    alta_stagione = ('07-01', '08-31')
    bassa_stagione = ('10-01', '12-01')

    # Upload the mapping files
    json_strutture = PATH_MAPPING / "strutture_ospitalita_Trento_2020.json"
    json_popolazione = PATH_MAPPING / "popolazione_Trento.json"
    json_vodafone = PATH_MAPPING / "vodafone_Trento.json"
    # json_comuni_to_APT = PATH_MAPPING / "map_comuni_into_apt.json"

    assert json_popolazione.exists() and json_vodafone.exists()
    logging.debug("** loading mapping files")
    json_popolazione = json.load(open(json_popolazione))
    json_vodafone = json.load(open(json_vodafone))
    json_strutture = json.load(open(json_strutture))
    # json_comuni_to_APT = json.load(open(json_comuni_to_APT))

    ## Initialization:
    logging.debug("** importing datasets")
    strutture_ospitalita_trentino_df = pd.read_csv(get_s3('Annuario-TavXIII-per-comune-csv.csv'),nrows=2000)

    ## take years from 2020
    strutture_ospitalita_from_2020 = strutture_ospitalita_trentino_df[strutture_ospitalita_trentino_df['anno'] > 2019].copy()  
    strutture_ospitalita_from_2020["comune"] = strutture_ospitalita_from_2020["comune"].apply(lambda x : customize_unidecode(x).replace("0", "-"))
    strutture_ospitalita_from_2020['ID'] = strutture_ospitalita_from_2020['comune'].map(json_strutture)

    # Dataframe popolazione dal 2020 
    popolazione_df = get_dataframe("popolazione_2020_2024")
    popolazione_df["comune"] = popolazione_df["comune"].apply(lambda x : customize_unidecode(x))
    popolazione_df['ID'] = popolazione_df['comune'].map(json_popolazione)
    logging.debug("** importing datasets")

    vodafone_attendences_df = get_dataframe("vodafone_attendences") # aggiunta di giorno della settimana al dataset Vodafone (tutto il Trentino)
    vodafone_attendences_df["anno"] = pd.to_datetime(vodafone_attendences_df["date"]).dt.year
    vodafone_attendences_df["comune"] = vodafone_attendences_df.loc[vodafone_attendences_df["locType"] == 'TN_MKT_AL_3', "locId"].apply(
        lambda x: get_Vodafone_location_name(x)
    )
    vodafone_attendences_df['ID'] = vodafone_attendences_df['comune'].map(json_vodafone)

    # movimento_turistico_molveno = get_dataframe("movimento_turistico_molveno")  
    arrivi_trentino = pd.read_csv(get_s3('arrivi_trentino_ISPAT.csv'),nrows=2000)
    arrivi_trentino.rename(columns={'Anno': 'anno', 'Ambito': 'comune'}, inplace=True)
    arrivi_trentino = pd.melt(arrivi_trentino,
             id_vars="comune",
             value_vars = ['2021', '2022', '2023', '2024'],
             value_name= "arrivi", 
             var_name = "anno")
    arrivi_trentino['anno'] = arrivi_trentino['anno'].astype(int)
    arrivi_trentino = arrivi_trentino.sort_values(by=['comune', 'anno']).reset_index(drop=True)
    logging.debug("** datasets imported")
    
    ## Aggregation of popolazione wrt APTs 
    # arrivi_trentino['ID'] = arrivi_trentino['comune'].map(json_comuni_to_APT)
    # arrivi_trentino = arrivi_trentino[arrivi_trentino['comune'] != "Provincia"]
    # popolazione_per_ambito_df = aggregate_popToAmbito(popolazione_df, arrivi_trentino)
    
    logging.info("Unification of Vigo di Fassa and Pozza di Fassa in Vodafone dataset (ID 22250)")
    vodafone_attendences_df['comune'] = vodafone_attendences_df['comune'].replace(['VIGO DI FASSA', 'POZZA DI FASSA'], 'SAN GIOVANNI DI FASSA')
    vodafone_attendences_df.loc[vodafone_attendences_df['comune'] == 'SAN GIOVANNI DI FASSA', 'ID'] = vodafone_attendences_df.loc[
        vodafone_attendences_df['comune'] == 'SAN GIOVANNI DI FASSA','ID'].apply(lambda _: [22250])
    json_vodafone['SAN GIOVANNI DI FASSA'] = [22250]

    if not popolazione_df[popolazione_df['comune'].str.startswith("PROVINCIA")].empty: 
        logging.info(f"Comune {popolazione_df[popolazione_df['comune'].str.startswith('PROVINCIA')]['comune'].unique()} is a PROVINCIA, removing it from the analysis")
        popolazione_df = popolazione_df[
            ~popolazione_df['comune'].str.startswith("PROVINCIA")
        ]

    if not strutture_ospitalita_from_2020[strutture_ospitalita_from_2020['comune'].str.startswith("PROVINCIA")].empty: 
        logging.info(f"Comune {strutture_ospitalita_from_2020[strutture_ospitalita_from_2020['comune'].str.startswith('PROVINCIA')]['comune'].unique()} is a PROVINCIA, removing it from the analysis")
        strutture_ospitalita_from_2020 = strutture_ospitalita_from_2020[
            ~strutture_ospitalita_from_2020['comune'].str.startswith("PROVINCIA")
        ]

    if not arrivi_trentino[arrivi_trentino['comune'].str.upper().str.startswith("PROVINCIA")].empty: 
        logging.info(f"Comune {arrivi_trentino[arrivi_trentino['comune'].str.upper().str.startswith('PROVINCIA')]['comune'].unique()} is a PROVINCIA, removing it from the analysis")
        arrivi_trentino = arrivi_trentino[
            ~arrivi_trentino['comune'].str.upper().str.startswith("PROVINCIA")
        ]

    DF_TASSO_VARIAZIONE_PERCENTUALE = calculate_tasso_variazione_percentuale(arrivi_trentino, [2022, 2023, 2024]) 

    DF_INCIDENZA_STRUTTURE_NON_CONVENZ_TRENTINO, DF_INCIDENZA_POSTILETTO_NON_CONVENZ_TRENTINO = compute_df_incidenza_ospit_non_convenz_trentino(strutture_ospitalita_from_2020)
    DF_TASSO_RICETTIVITA_TRENTINO = compute_df_tasso_ricettivita_trentino(strutture_ospitalita_from_2020, popolazione_df)

    DF_TASSO_TURISTICITA_TRENTINO_2022_VODAFONE = compute_df_tasso_turisticita_trentino_Vodafone("2022-01-01", "2022-12-31", vodafone_attendences_df, popolazione_df)
    DF_TASSO_TURISTICITA_TRENTINO_2023_VODAFONE = compute_df_tasso_turisticita_trentino_Vodafone("2023-01-01", "2023-12-31", vodafone_attendences_df, popolazione_df)
    DF_TASSO_TURISTICITA_TRENTINO_VODAFONE = pd.concat([DF_TASSO_TURISTICITA_TRENTINO_2022_VODAFONE, DF_TASSO_TURISTICITA_TRENTINO_2023_VODAFONE])

    DF_TASSO_TURISTICITA_TRENTINO_ESTATE2022_VODAFONE = compute_df_tasso_turisticita_trentino_Vodafone("2022-06-01", "2022-09-30",vodafone_attendences_df, popolazione_df)
    DF_TASSO_TURISTICITA_TRENTINO_ESTATE2023_VODAFONE = compute_df_tasso_turisticita_trentino_Vodafone("2023-06-01", "2023-09-30",vodafone_attendences_df, popolazione_df)
    DF_TASSO_TURISTICITA_TRENTINO_ESTATE_VODAFONE = pd.concat([DF_TASSO_TURISTICITA_TRENTINO_ESTATE2022_VODAFONE, DF_TASSO_TURISTICITA_TRENTINO_ESTATE2023_VODAFONE])

    DF_TASSO_TURISTICITA_TRENTINO_INVERNO2023_VODAFONE = compute_df_tasso_turisticita_trentino_Vodafone("2022-12-01", "2023-04-30", vodafone_attendences_df, popolazione_df)

    DF_STAGIONALITA_PRESENZE = compute_stagionalita_presenze(bassa_stagione, alta_stagione, vodafone_attendences_df, json_vodafone, [2022, 2023])

    return {
        "df_incidenza_strutture_non_conv": DF_INCIDENZA_STRUTTURE_NON_CONVENZ_TRENTINO, 
        "df_incidenza_postiletto_non_conv": DF_INCIDENZA_POSTILETTO_NON_CONVENZ_TRENTINO, 
        "df_tasso_ricettivita": DF_TASSO_RICETTIVITA_TRENTINO, 
        "df_tasso_turisticita": DF_TASSO_TURISTICITA_TRENTINO_VODAFONE,
        "df_tasso_turisticita_2022": DF_TASSO_TURISTICITA_TRENTINO_2022_VODAFONE, 
        "df_tasso_turisticita_2023": DF_TASSO_TURISTICITA_TRENTINO_2023_VODAFONE,
        "df_tasso_turisticita_estate": DF_TASSO_TURISTICITA_TRENTINO_ESTATE_VODAFONE,
        "df_tasso_turisticita_estate2022": DF_TASSO_TURISTICITA_TRENTINO_ESTATE2022_VODAFONE,
        "df_tasso_turisticita_estate2023": DF_TASSO_TURISTICITA_TRENTINO_ESTATE2023_VODAFONE,
        "df_tasso_turisticita_inverno2023": DF_TASSO_TURISTICITA_TRENTINO_INVERNO2023_VODAFONE,
        "df_tasso_variazione_pecentuale": DF_TASSO_VARIAZIONE_PERCENTUALE,
        "df_stagionalita_presenze": DF_STAGIONALITA_PRESENZE
        }

def local():
    dict_dfs = compute_index_dataframes()
    for key, value in dict_dfs.items():
        put_dataframe(value, key, type = 'csv')
    logging.info("salvataggio completato.")

def main(): 
    logging.info(f"\n## Salvataggio dei dataframe sulla piattaforma") 
    dict_dfs = compute_index_dataframes()
    for key, value in dict_dfs.items():
        log_dataframe(value.reset_index(), key)
    logging.info("salvataggio completato.")


if __name__ == "__main__":
    local()
