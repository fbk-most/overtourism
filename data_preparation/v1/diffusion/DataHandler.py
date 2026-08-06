import os
import seaborn as sns
from data_preparation.diffusion.OsAndFileHandling import *
import polars as pl
class DataHandler:
    """
        This class must be created by calling:
            %run datasets_load.py
        All the DataFrame Needed are in this way loaded.
        Example:
            DH = DataHandler(contamezzi_df,
                manifestazioni_df,
                meteotrentino_bollettino_df,
                contamezzi_descrizione_sensore_df,
                contapersone_passaggi_df,
                contapersone_presenze_df,
                statistiche_parcheggi_molveno_df,
                movimento_turistico_df,
                extra_strutture_df,
                survey_df,
                vodafone_aree_df,
                vodafone_attendences_df,
                vodafone_attendences_STR_df,
                movimento_turistico_molveno_df)
            
        Description:
            contamezzi_df: Cols -> {data: str,sensore: str,direzione: int,comune: str,cl1: int64 ,cl2: ,cl3: ,cl4: ,cl5: ,cl6: ,cl7: ,nonrilevato: int64}
            manifestazioni_df:  Cols -> {'nr': , 'richiedente': , 'manifestazione': , 'luogo': , 'data_manifestazione_inizio': , 'data_manifestazione_fine': ,
                                         'partecipanti_dichiarati': , 'spesa ': , 'spesa_ritenuta_ammissibile': ,'doc_tm_sra_200000': , 'punti': , 
                                         'percentuale_intervento': ,'contributo': ,    'typology': }
            meteotrentino_bollettino_df: Cols -> {data: ,comune: ,ambito: ,meteo: ,tmin: ,tmax: ,probprec06-12: ,intprec06-12: ,probtemp06-12: ,probprec12-18: ,
                                                    intprec12-18: ,probtemp12-18}
            
            contamezzi_descrizione_sensore_df: Cols -> {sensore:str ,direzione: int (1,2),latitudine: float,longitudine: float,descrizione_direzione:str} 
            
            contapersone_passaggi_df: Cols -> {data: ,varco: str (Varco 1,..., Varco 9),presenze: int}
            
            contapersone_presenze_df: Cols -> {data: ,varco: str (Varco 1,..., Varco 9),presenze: int}
            
            statistiche_parcheggi_molveno_df: Cols -> {20 MIN: float,40 MIN: ,1 ORA: ,1 ORA E 20 MIN: ,1 ORA E 40 MIN: ,2 ORE: ,3 ORE: ,4 ORE: ,5 ORE: ,6 ORE
            ...1 GIORNO: ,2 GIORNI: ,3 GIORNI: ,4 GIORNI: ,5 GIORNI: ,6 GIORNI: ,7 GIORNI: ,8 GIORNI: ,TOTALE: float ,date: }
                Description: the time people pay the parking.
            movimento_turistico_df: Cols -> {giorno: str,ente_promozione: str,arrivi: int,presenze: int}
            
            extra_strutture_df: Cols -> {bagni: ,camere: int,posti_letto: int,strutture: int ,year: 1980...}
            
            survey_df: Cols -> {zone: str ,satisfaction: str (seems to e an error as cycle throgh the same),value: 0.15,typology: (parcheggi,accoglienza)}
            
            vodafone_aree_df: Cols -> {locId: ,locName: , locType: ,locDescr}
            
            vodafone_attendences_df: Cols -> {date: ,locType: ,locId: ,userCountry: ,userProfile: ,userCluster: ,value}
            
            vodafone_attendences_STR_df: Cols -> {date: ,locType: ,locId: ,userCountry: ,userProfile: ,userCluster: ,value}
            
            movimento_turistico_molveno_df: Cols -> {anno: ,mese: ,date: ,territorio_comunale: ,arrivi: ,presenze}
            
    """
    def __init__(self,
                contamezzi_df,
                manifestazioni_df,
                meteotrentino_bollettino_df,
                contamezzi_descrizione_sensore_df,
                contapersone_passaggi_df,
                contapersone_presenze_df,
                statistiche_parcheggi_molveno_df,
                movimento_turistico_df,
                extra_strutture_df,
                survey_df,
                vodafone_aree_df,
                vodafone_attendences_df,
                vodafone_attendences_STR_df,
                movimento_turistico_molveno_df
                ):
        self.contamezzi_df = contamezzi_df
        self.manifestazioni_df = manifestazioni_df
        self.meteotrentino_bollettino_df = meteotrentino_bollettino_df 
        self.contamezzi_descrizione_sensore_df = contamezzi_descrizione_sensore_df 
        self.contapersone_passaggi_df = contapersone_passaggi_df 
        self.contapersone_presenze_df = contapersone_presenze_df 
        self.statistiche_parcheggi_molveno_df = statistiche_parcheggi_molveno_df 
        self.movimento_turistico_df = movimento_turistico_df 
        self.extra_strutture_df = extra_strutture_df 
        self.survey_df = survey_df 
        self.vodafone_aree_df = vodafone_aree_df 
        self.vodafone_attendences_df = vodafone_attendences_df 
        self.vodafone_attendences_STR_df = vodafone_attendences_STR_df 
        self.movimento_turistico_molveno_df = movimento_turistico_molveno_df  
        self.BaseDir = BaseDir
        self.format_datetime_hour = "%Y-%m-%d %H:%M:%S"
        self.format_datetime_day = "%Y-%m-%d"
        

    def CastDataFramesDate(self):
        """
            NOTE: Every column that contain dates in string will be cast to datetime as 
                1) "date_dt" if date of an event that does not last in time
                2) "date_dt_begin" if begin of event that lasts in time
                3) "date_dt_end" if end of event
        """
        if type(self.contamezzi_df) == pd.DataFrame:      
            self.meteotrentino_bollettino_df["date_dt"] = pd.to_datetime(self.meteotrentino_bollettino_df["data"],format = self.format_datetime_day)
            self.contamezzi_df["date_dt"] = pd.to_datetime(self.contamezzi_df["data"],format = self.format_datetime_hour)
            self.manifestazioni_df["date_dt_begin"] = pd.to_datetime(self.manifestazioni_df["data_manifestazione_inizio"],format = self.format_datetime_hour)
            self.manifestazioni_df["date_dt_end"] = pd.to_datetime(self.manifestazioni_df["data_manifestazione_fine"],format = self.format_datetime_hour)
            self.contapersone_passaggi_df["date_dt"] = pd.to_datetime(self.contapersone_passaggi_df["data"],format = self.format_datetime_day)
            self.contapersone_presenze_df["date_dt"] = pd.to_datetime(self.contapersone_presenze_df["data"],format = self.format_datetime_day)
            self.statistiche_parcheggi_molveno_df["date_dt"] = pd.to_datetime(self.statistiche_parcheggi_molveno_df["data"],format = self.format_datetime_day)
            self.movimento_turistico_df["date_dt"] = pd.to_datetime(self.movimento_turistico_df["giorno"],format = self.format_datetime_day)
            self.extra_strutture_df["date_dt"] = pd.to_datetime(self.extra_strutture_df["year"],format = "%Y")
            self.vodafone_attendences_df["date_dt"] = pd.to_datetime(self.vodafone_attendences_df["date"],format = self.format_datetime_day)
            self.vodafone_attendences_STR_df["date_dt"] = pd.to_datetime(self.vodafone_attendences_STR_df["date"],format = self.format_datetime_day)
            self.movimento_turistico_molveno_df["date_dt"] = pd.to_datetime(self.movimento_turistico_molveno_df["date"],format = self.format_datetime_day)    
        else:
            self.meteotrentino_bollettino_df = self.meteotrentino_bollettino_df.with_columns(
                pl.col("data").str.strptime(pl.Date, format=self.format_datetime_day, strict=False).alias("date_dt")
            )
            self.contamezzi_df = self.contamezzi_df.with_columns(
                pl.col("data").str.strptime(pl.Datetime, format=self.format_datetime_hour, strict=False).alias("date_dt")
            )
            self.manifestazioni_df = self.manifestazioni_df.with_columns([
                pl.col("data_manifestazione_inizio").str.strptime(pl.Datetime, format=self.format_datetime_hour, strict=False).alias("date_dt_begin"),
                pl.col("data_manifestazione_fine").str.strptime(pl.Datetime, format=self.format_datetime_hour, strict=False).alias("date_dt_end")
            ])
            self.contapersone_passaggi_df = self.contapersone_passaggi_df.with_columns(
                pl.col("data").str.strptime(pl.Date, format=self.format_datetime_day, strict=False).alias("date_dt")
            )
            self.contapersone_presenze_df = self.contapersone_presenze_df.with_columns(
                pl.col("data").str.strptime(pl.Date, format=self.format_datetime_day, strict=False).alias("date_dt")
            )
            self.statistiche_parcheggi_molveno_df = self.statistiche_parcheggi_molveno_df.with_columns(
                pl.col("date").str.strptime(pl.Date, format=self.format_datetime_day, strict=False).alias("date_dt")
            )
            self.movimento_turistico_df = self.movimento_turistico_df.with_columns(
                pl.col("giorno").str.strptime(pl.Date, format=self.format_datetime_day, strict=False).alias("date_dt")
            )
            self.vodafone_attendences_df = self.vodafone_attendences_df.with_columns(
                pl.col("date").str.strptime(pl.Date, format=self.format_datetime_day, strict=False).alias("date_dt")
            )
            self.vodafone_attendences_STR_df = self.vodafone_attendences_STR_df.with_columns(
                pl.col("date").str.strptime(pl.Date, format=self.format_datetime_day, strict=False).alias("date_dt")
            )
            self.movimento_turistico_molveno_df = self.movimento_turistico_molveno_df.with_columns(
                pl.col("date").str.strptime(pl.Date, format=self.format_datetime_day, strict=False).alias("date_dt")
            )
    def GetMolvenoPresencesFromVodaFone(self):
        """

        """
        self.vodafone_attendences_df = self.vodafone_attendences_df.astype({'value': 'int'})
        molvenoId = self.vodafone_aree.query('locDescr == "Molveno"')['locId'].values[0]
        molvenoPresences = self.vodafone_attendances_df.query('locId ==@molvenoId')
        self.vodafone_attendances_df.query('locId=="27" and userProfile=="TOURIST"')
        