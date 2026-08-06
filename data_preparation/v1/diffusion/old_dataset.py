"""
This script loads various datasets from a Digital Hub project related to tourism analysis.
These data are of 2023, they are not used for the project but can be useful for future analysis.    
They were given to start testing
"""
import digitalhub as dh
import os

PROJECT = os.environ.get("PROJECT_NAME", "overtourism1")

project_tourism = dh.get_or_create_project(PROJECT)

contamezzi_df = project_tourism.get_dataitem("contamezzi").as_df()
manifestazioni_df = project_tourism.get_dataitem("manifestazioni").as_df()
meteotrentino_bollettino_df = project_tourism.get_dataitem("meteotrentino_bollettino").as_df()
contamezzi_descrizione_sensore_df = project_tourism.get_dataitem("contamezzi_descrizione_sensore").as_df()
contapersone_passaggi_df = project_tourism.get_dataitem("contapersone_passaggi").as_df()
contapersone_presenze_df = project_tourism.get_dataitem("contapersone_presenze").as_df()
statistiche_parcheggi_molveno_df = project_tourism.get_dataitem("statistiche_parcheggi_molveno").as_df()
movimento_turistico_df = project_tourism.get_dataitem("movimento_turistico").as_df()
extra_strutture_df = project_tourism.get_dataitem("extra_strutture").as_df()
survey_df = project_tourism.get_dataitem("survey").as_df()
vodafone_aree_df = project_tourism.get_dataitem("vodafone_aree").as_df()
vodafone_attendences_df = project_tourism.get_dataitem("vodafone_attendences").as_df()
vodafone_attendences_STR_df = project_tourism.get_dataitem("vodafone_attendences_STR").as_df()
movimento_turistico_molveno_df = project_tourism.get_dataitem("movimento_turistico_molveno").as_df()
dati_pioggia_df = project_tourism.get_dataitem("dati_pioggia").as_df()
depuratore_df = project_tourism.get_dataitem("depuratore").as_df()
parcheggi_posti_molveno_df = project_tourism.get_dataitem("parcheggi_posti").as_df()
ristoranti_df = project_tourism.get_dataitem("ristoranti").as_df()
print("Loading data from the DataLake")
# Note: Uncomment and load dataframes when needed
data_handler = DataHandler(pl.DataFrame(contamezzi_df), pl.DataFrame(manifestazioni_df), ...)
