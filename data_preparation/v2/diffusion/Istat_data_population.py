import polars as pl
import pandas as pd
import re


def preprocess_city_names(name):
    """Normalize city names for better matching"""
    if pd.isna(name):
        return name
    # Convert to lowercase and remove extra spaces
    name = str(name).lower().strip()
    # Remove common prefixes/suffixes that might cause mismatches
    name = re.sub(r'\s+', ' ', name)  # Replace multiple spaces with single space
    return name

def extract_city_components(combined_name):
    """Extract individual city names from combined strings like 'Castel Ivano + Ivano-fracena'"""
    if pd.isna(combined_name):
        return []
    
    # Split by common separators
    separators = ['+', ',', '/', '&', ' e ', ' and ']
    cities = [combined_name]
    
    for sep in separators:
        new_cities = []
        for city in cities:
            new_cities.extend([c.strip() for c in city.split(sep)])
        cities = new_cities
    
    # Clean and normalize each component
    return [preprocess_city_names(city) for city in cities if city.strip()]

def simple_join_cities_with_population(cities_gdf, 
                                       population_df,
                                       str_col_comuni_istat = "Comune",
                                       str_col_popolazione_totale = "Popolazione_Totale",
                                       str_col_city_name = "city_name",
                                       is_Vodafone_Trento_ZDT = False
                                       ):
    """
        Joins information about cities with population data from ISTAT.
        
        Parameters:
        -----------
        cities_gdf : gpd.GeoDataFrame
            GeoDataFrame containing city data
        population_df : pd.DataFrame or pl.DataFrame
            DataFrame containing ISTAT population data
        str_col_comuni_istat : str
            Column name for municipality in ISTAT data
        str_col_popolazione_totale : str
            Column name for total population
        str_col_city_name : str
            Column name for city names in cities_gdf
        is_Vodafone_Trento_ZDT : bool
            If False, replaces "Trento_ZDT" variations with "Trento"
    """
    result_gdf = cities_gdf.copy()
    
    # Ad hoc functionality for Vodafone Trento ZDT
    if is_Vodafone_Trento_ZDT:
        # Apply transformation to replace Trento_ZDT variations with "Trento"
        result_gdf[str_col_city_name] = result_gdf[str_col_city_name].apply(
            lambda x: _normalize_trento_zdt(x)
        )
    
    if hasattr(population_df, 'to_pandas'):
        population_df = population_df.to_pandas()
    
    # Normalize population data
    population_df['Comune_normalized'] = population_df[str_col_comuni_istat].str.lower().str.strip()
    
    city_to_population = {}
    
    for idx, row in result_gdf.iterrows():
        city_name = row[str_col_city_name]
        city_components = extract_city_components(city_name)
        
        # Find matching comuni
        matched_population = 0
        matched_comuni = []
        
        for component in city_components:
            matches = population_df[
                population_df['Comune_normalized'] == component
            ]
            if not matches.empty:
                matched_population += matches[str_col_popolazione_totale].sum()
                matched_comuni.extend(matches[str_col_comuni_istat].tolist())
        
        city_to_population[city_name] = matched_population if matched_population > 0 else None
        
        if matched_comuni:
            print(f"'{city_name}' -> {matched_comuni} = {matched_population}")
    
    result_gdf[str_col_popolazione_totale] = result_gdf[str_col_city_name].map(city_to_population)
    
    return result_gdf


def _normalize_trento_zdt(city_name):
    """
    Helper function to normalize Trento ZDT variations to "Trento"
    
    Parameters:
    -----------
    city_name : str
        City name that might contain Trento_ZDT variations
        
    Returns:
    --------
    str
        Normalized city name with Trento_ZDT replaced by "Trento"
    """
    if pd.isna(city_name):
        return city_name
    
    city_name_str = str(city_name)
    
    # Check for various Trento ZDT patterns (case insensitive)
    trento_patterns = [
        r'Trento_ZDT_',
        r'Trento_ZDT'
    ]
    
    for pattern in trento_patterns:
        if pattern in city_name_str:
            return "Trento"
    
    return city_name_str

class Istat_population_data:
    """
    Class to handle ISTAT population data.
    """

    def __init__(self, path: str):
        """
        Initialize the Istat_population_data class.

        :param path: Path to the CSV file containing ISTAT population data.
        """
        self.path = path
        # Load Istat data, NOTE: Must be downloaded manually from: https://demo.istat.it/app/?l=it&a=2024&i=POS
        self.load_data()
        # get list of municipalities that are in the data: We are going to compare them with the ones from DataLake
        self.list_comuni = self.get_list_comuni()
        self.get_population_df()

    def load_data(self):
        """
        Load the ISTAT population data from the CSV file.
        """
        self.df_istat = pl.DataFrame(pd.read_csv(self.path,sep=";"))

    def get_list_comuni(self):
        """
        Get a list of unique municipalities from the ISTAT data.

        :return: List of unique municipalities.
        """
        return self.df_istat.select(pl.col("Comune")).unique()

    def get_population_df(self):
        """
        The obtained df contains informations about comune and total number of inhabitants independent of age and sex
        """
        self.population_by_comune = self.df_istat.group_by("Comune").agg(
        pl.col("Totale").sum().alias("Popolazione_Totale"))


