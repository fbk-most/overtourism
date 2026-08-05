import sys
import pandas as pd

from data_preparation.utils import get_dataframe, put_dataframe, log_dataframe, get_s3

def get_presenze():
    alb_xalb_df = 'presenze_Trentino_ISPAT_alb_xalb.csv'
    alb_xalb = pd.read_csv(get_s3(alb_xalb_df))

    alb_xalb["Rapporto xalb-alb"] = alb_xalb["Presenze extra-alberghi"] / alb_xalb["Presenze alberghi"]

    presenze_df = 'presenze_Trentino_ISPAT.csv'
    presenze = pd.read_csv(get_s3(presenze_df))

    presenze.rename(columns={"Presenze": "Presenze alberghi"}, inplace=True)
    presenze = presenze.merge(alb_xalb[["Anno", "Mese", "Rapporto xalb-alb"]],on=["Anno", "Mese"])
    presenze["Presenze extra-alberghi"] = (presenze["Presenze alberghi"] * presenze["Rapporto xalb-alb"]).astype(int)
    presenze["Presenze"] = presenze["Presenze alberghi"] + presenze["Presenze extra-alberghi"]
    presenze.drop(columns=["Presenze alberghi", "Presenze extra-alberghi", "Rapporto xalb-alb"], inplace=True)

    presenze = presenze[presenze["Anno"].isin([2022,2023])]
    presenze.rename(columns={"Presenze":"presenze", "Anno":"anno", "Mese":"mese", "Ambito":"ambito"}, inplace=True)

    return presenze

def get_presenze_vodafone():
    locType_APT = "TN_MKT_AM_22"
    userProfile_TOURISTS = "TOURIST"
    apt_map={
        "100":"San Martino di Castrozza, Primiero e Vanoi",
        "101":"Val di Non",
        "102":"Rovereto, Vallagarina e Monte Baldo",
        "103":"Val di Fassa",
        "104":"Val di Sole",
        "105":"Altopiano della Paganella, Piana della Rotaliana e San Lorenzo Dorsino",
        "106":"Madonna di Campiglio, Pinzolo, Val Rendena, Giudicarie centrali e Valle del Chiese",
        "107":"Val di Fiemme e Val di Cembra",
        "108":"Valsugana, Tesino e Valle dei Mocheni",
        "109":"Trento, Monte Bondone e Altopiano di Pinè",
        "110":"Garda trentino, Valle di Ledro, Terme di Comano e Valle dei Laghi",
        "111":"Altipiani cimbri e Vigolana",
    }

    vodafone = get_dataframe("vodafone_attendences")
    vodafone = vodafone[(vodafone["locType"] == locType_APT) & (vodafone["userProfile"] == userProfile_TOURISTS)]
    vodafone = vodafone[["date", "locId", "value"]].groupby(["date", "locId"]).sum().reset_index()
    vodafone["ambito"] = vodafone["locId"].map(apt_map)
    vodafone.drop(columns=["locId"], inplace=True)
    vodafone.rename(columns={"date":"data", "value":"presenze"}, inplace=True)
    vodafone["data"] = pd.to_datetime(vodafone["data"])
    vodafone["anno"] = vodafone["data"].dt.year
    vodafone["mese"] = vodafone["data"].dt.month
    vodafone.drop(columns=["data"], inplace=True)
    vodafone = vodafone[vodafone["anno"].isin([2022,2023])]
    vodafone = vodafone.groupby(["anno", "mese", "ambito"]).sum().reset_index()
    return vodafone

def prepare_presenze():
    df_presenze = get_presenze()
    df_presenze_vodafone = get_presenze_vodafone()
    df = df_presenze.merge(df_presenze_vodafone.rename(columns={"presenze":"presenze_vodafone"}),
                           how="inner", on=["ambito", "anno", "mese"])
    return df

def compute_df_turismo_sommerso():
      
    df_ht = prepare_presenze()

    summer_months = [6,7,8,9]

    df_ht_year = df_ht.drop(columns=["mese"]).groupby(["ambito", "anno"]).sum().reset_index()
    df_ht_year["ratio"] = df_ht_year["presenze_vodafone"]/df_ht_year["presenze"]
    df_ht_summer = df_ht[df_ht["mese"].isin(summer_months)].drop(columns=["mese"])
    df_ht_summer = df_ht_summer.groupby(["ambito", "anno"]).sum().reset_index()
    df_ht_summer.rename(columns={"presenze":"presenze_estate",
                                "presenze_vodafone":"presenze_vodafone_estate"}, inplace=True)
    df_ht_summer["ratio_estate"] = df_ht_summer["presenze_vodafone_estate"]/df_ht_summer["presenze_estate"]

    df_ht_index = df_ht_year.merge(df_ht_summer, how="inner", on=["anno", "ambito"])

    df_ht_index.rename(columns={"ambito":"comune"}, inplace=True)
    df_ht_index.set_index(["comune", "anno"], inplace=True)

    return df_ht_index

def local():
    DF_TURISMO_SOMMERSO = compute_df_turismo_sommerso()
    put_dataframe(DF_TURISMO_SOMMERSO, "df_turismo_sommerso", type = "parquet")

def main():
    DF_TURISMO_SOMMERSO = compute_df_turismo_sommerso()
    log_dataframe(DF_TURISMO_SOMMERSO.reset_index(), "df_turismo_sommerso")

if __name__ == "__main__":      
    local()