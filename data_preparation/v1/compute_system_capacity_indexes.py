# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import pandas as pd
from sklearn.linear_model import LinearRegression

from data_preparation.utils import get_s3, get_dataframe

START_DATE = "2023-06-01"
END_DATE = "2023-09-30"

def get_parcheggi(start_date=START_DATE, end_date=END_DATE):
    parcheggi = pd.read_excel(get_s3('Statistiche_parcheggi_Molveno.xlsx'), index_col=0).transpose()
    parcheggi.index.name = "DATA"
    parcheggi = parcheggi.reset_index()
    parcheggi = parcheggi[["DATA", "TOTALE"]]
    parcheggi.rename(columns={"TOTALE": "PARCHEGGI"}, inplace=True)
    parcheggi = parcheggi[(parcheggi["DATA"] >= start_date) & (parcheggi["DATA"] <= end_date)]
    return parcheggi.set_index("DATA")

def get_spiaggia():
    input_zip = ZipFile(get_s3('BS4_contapersone.zip'))
    files = {name: input_zip.read(name) for name in input_zip.namelist()}
    spiaggia = pd.read_csv(BytesIO(files['contapersone_presenze_Molveno.csv']))
    spiaggia = spiaggia[["data", "presenze"]].groupby("data").sum().reset_index()
    spiaggia["data"] = pd.to_datetime(spiaggia["data"])
    spiaggia.rename(columns={"data": "DATA", "presenze": "SPIAGGIA"}, inplace=True)
    return spiaggia.set_index("DATA")

def get_presenze_vodafone(start_date=START_DATE, end_date=END_DATE):
    locId_MOLVENO = "27"
    userProfile_TOURISTS = "TOURIST"
    userProfile_EXCURSIONISTS = "VISITOR"
    presenze = get_dataframe("vodafone_attendences")
    presenze = presenze[(presenze["locId"] == locId_MOLVENO) &
            ((presenze["userProfile"] == userProfile_TOURISTS) | (presenze["userProfile"] == userProfile_EXCURSIONISTS))]
    presenze = presenze[["date", "value", "userProfile"]].groupby(["date","userProfile"]).sum().reset_index()
    presenze["date"] = pd.to_datetime(presenze["date"])
    presenze = presenze.pivot_table(values="value", index="date", columns="userProfile").reset_index()
    presenze.columns.name = None
    presenze.rename(columns={"date": "DATA", userProfile_TOURISTS:"TURISTI", userProfile_EXCURSIONISTS:"ESCURSIONISTI"}, inplace=True)
    presenze = presenze[(presenze["DATA"] >= start_date) & (presenze["DATA"] <= end_date)]
    return presenze.set_index("DATA")[["TURISTI", "ESCURSIONISTI"]]

def model_parcheggi(parcheggi, presenze):
    reg = LinearRegression(fit_intercept=False, positive=True).fit(presenze, parcheggi)
    return reg

def model_spiaggia(spiaggia, presenze):
    reg = LinearRegression(fit_intercept=False, positive=True).fit(presenze, spiaggia)
    return reg

if __name__ == "__main__":
    parcheggi = get_parcheggi()
    presenze = get_presenze_vodafone()
    reg = model_parcheggi(parcheggi, presenze)
    coef_t, coef_e =  reg.coef_[0,0], reg.coef_[0,1]
    print("MOELLO PARCHEGGI")
    print(f"- Coefficiente turisti      : {coef_t:.4f}")
    print(f"- Coefficiente escursionisti: {coef_e:.4f}")

    spiaggia = get_spiaggia()
    presenze_spiaggia = presenze[presenze.index.isin(spiaggia.index)]
    reg = model_spiaggia(spiaggia, presenze_spiaggia)
    coef_t, coef_e =  reg.coef_[0,0], reg.coef_[0,1]
    print("MOELLO SPIAGGIA")
    print(f"- Coefficiente turisti      : {coef_t:.4f}")
    print(f"- Coefficiente escursionisti: {coef_e:.4f}")

