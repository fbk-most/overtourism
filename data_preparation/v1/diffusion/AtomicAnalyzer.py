from typing import Tuple, Dict, List
import pandas as pd
import polars as pl
import geopandas as gpd
class AtomicAnalyzer:
    def __init__(self,
                 grid: gpd.GeoDataFrame,
                 flows: pl.DataFrame|pd.DataFrame,
                 presences: pl.DataFrame|pd.DataFrame,
                 str_population_col_grid: str,
                 ):
        self.flows = flows
        self.grid = grid
        self.df_presences = 