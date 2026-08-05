import os
import pandas as pd
import numpy as np
import geopandas as gpd

from data_preparation.utils import put_dataframe, log_dataframe, put_geojson, log_geojson, BASE_DIR

def extract_diffusion_1_2():
    try:
        path = f"{BASE_DIR}/Output/Vodafone-Data/"
        df_uw = pd.read_parquet(path + "grid_all_columns_user_weekday.parquet")
        df_u = pd.read_parquet(path + "grid_all_columns_user.parquet")
        df_w = pd.read_parquet(path + "grid_all_columns_weekday.parquet")
        df_ = pd.read_parquet(path + "grid_all_columns__.parquet")
    except FileNotFoundError:
        print("Diffusion 1 2 files missing!")
        exit(1)

    df = df_[['AREA_ID', 'AREA_LABEL']].copy()
    df = df[df['AREA_ID'].str.startswith('ITA.04.022.', na=False)]
    df.rename(columns={'AREA_ID': 'ID', 'AREA_LABEL': 'comune'}, inplace=True)
    df['comune'] = df['comune'].str.upper()

    df_uw_map = {
        'tot_in_flows_VISITOR_t_0_0_w_Feriale_d_' : 'flows_in_escursionisti_feriali',
        'tot_in_flows_VISITOR_t_0_0_w_Prefestivo_d_' : 'flows_in_escursionisti_prefestivi',
        'tot_in_flows_VISITOR_t_0_0_w_Festivo_d_' : 'flows_in_escursionisti_festivi',
        'tot_out_flows_VISITOR_t_0_0_w_Feriale_d_' : 'flows_out_escursionisti_feriali',
        'tot_out_flows_VISITOR_t_0_0_w_Prefestivo_d_' : 'flows_out_escursionisti_prefestivi',
        'tot_out_flows_VISITOR_t_0_0_w_Festivo_d_' : 'flows_out_escursionisti_festivi',
        'hotspot_level_tot_in_flows_VISITOR_t_0_0_w_Feriale_d_' : 'level_in_escursionisti_feriali',
        'hotspot_level_tot_in_flows_VISITOR_t_0_0_w_Prefestivo_d_' : 'level_in_escursionisti_prefestivi',
        'hotspot_level_tot_in_flows_VISITOR_t_0_0_w_Festivo_d_' : 'level_in_escursionisti_festivi',
        'hotspot_level_tot_out_flows_VISITOR_t_0_0_w_Feriale_d_' : 'level_out_escursionisti_feriali',
        'hotspot_level_tot_out_flows_VISITOR_t_0_0_w_Prefestivo_d_' : 'level_out_escursionisti_prefestivi',
        'hotspot_level_tot_out_flows_VISITOR_t_0_0_w_Festivo_d_' : 'level_out_escursionisti_festivi',
    }

    for k in df_uw_map:
        df[df_uw_map[k]] = df_uw[k]

    df_u_map = {
        'tot_in_flows_VISITOR_t_0_0_w_all_days_d_' : 'flows_in_escursionisti_sempre',
        'tot_out_flows_VISITOR_t_0_0_w_all_days_d_' : 'flows_out_escursionisti_sempre',
        'hotspot_level_tot_in_flows_VISITOR_t_0_0_w_all_days_d_' : 'level_in_escursionisti_sempre',
        'hotspot_level_tot_out_flows_VISITOR_t_0_0_w_all_days_d_' : 'level_out_escursionisti_sempre',
    }

    for k in df_u_map:
        df[df_u_map[k]] = df_u[k]

    df_w_map = {
        'tot_in_flows_t_0_0_w_Feriale_d_' : 'flows_in_tutti_feriali',
        'tot_in_flows_t_0_0_w_Prefestivo_d_' : 'flows_in_tutti_prefestivi',
        'tot_in_flows_t_0_0_w_Festivo_d_' : 'flows_in_tutti_festivi',
        'tot_out_flows_t_0_0_w_Feriale_d_' : 'flows_out_tutti_feriali',
        'tot_out_flows_t_0_0_w_Prefestivo_d_' : 'flows_out_tutti_prefestivi',
        'tot_out_flows_t_0_0_w_Festivo_d_' : 'flows_out_tutti_festivi',
        'hotspot_level_tot_in_flows_t_0_0_w_Feriale_d_' : 'level_in_tutti_feriali',
        'hotspot_level_tot_in_flows_t_0_0_w_Prefestivo_d_' : 'level_in_tutti_prefestivi',
        'hotspot_level_tot_in_flows_t_0_0_w_Festivo_d_' : 'level_in_tutti_festivi',
        'hotspot_level_tot_out_flows_t_0_0_w_Feriale_d_' : 'level_out_tutti_feriali',
        'hotspot_level_tot_out_flows_t_0_0_w_Prefestivo_d_' : 'level_out_tutti_prefestivi',
        'hotspot_level_tot_out_flows_t_0_0_w_Festivo_d_' : 'level_out_tutti_festivi',
    }
    df_w_fix = ['tot_in_flows_t_0_0_w_Feriale_d_',
                'tot_in_flows_t_0_0_w_Prefestivo_d_',
                'tot_in_flows_t_0_0_w_Festivo_d_',
                'tot_out_flows_t_0_0_w_Feriale_d_',
                'tot_out_flows_t_0_0_w_Prefestivo_d_',
                'tot_out_flows_t_0_0_w_Festivo_d_',
                ]
    # TODO: Manage this fix differently
    for k in df_w_fix:
        df_w[k] = df_w[k]*4
    for k in df_w_map:
        df[df_w_map[k]] = df_w[k]


    df__map = {
        'tot_in_flows_t_0_0_w_all_days_d_' : 'flows_in_tutti_sempre',
        'tot_out_flows_t_0_0_w_all_days_d_' : 'flows_out_tutti_sempre',
        'hotspot_level_tot_in_flows_t_0_0_w_all_days_d_' : 'level_in_tutti_sempre',
        'hotspot_level_tot_out_flows_t_0_0_w_all_days_d_' : 'level_out_tutti_sempre',
    }
    df__fix = ['tot_in_flows_t_0_0_w_all_days_d_',
               'tot_out_flows_t_0_0_w_all_days_d_',
               ]
    # TODO: Manage this fix differently
    for k in df__fix:
        df_[k] = df_[k]*4
    for k in df__map:
        df[df__map[k]] = df_[k]

    for r,e,t in (
        ('flows_in_ratio_feriali', 'flows_in_escursionisti_feriali', 'flows_in_tutti_feriali'),
        ('flows_in_ratio_prefestivi', 'flows_in_escursionisti_prefestivi', 'flows_in_tutti_prefestivi'),
        ('flows_in_ratio_festivi', 'flows_in_escursionisti_festivi', 'flows_in_tutti_festivi'),
        ('flows_in_ratio_sempre', 'flows_in_escursionisti_sempre', 'flows_in_tutti_sempre'),
        ('flows_out_ratio_feriali', 'flows_out_escursionisti_feriali', 'flows_out_tutti_feriali'),
        ('flows_out_ratio_prefestivi', 'flows_out_escursionisti_prefestivi', 'flows_out_tutti_prefestivi'),
        ('flows_out_ratio_festivi', 'flows_out_escursionisti_festivi', 'flows_out_tutti_festivi'),
        ('flows_out_ratio_sempre', 'flows_out_escursionisti_sempre', 'flows_out_tutti_sempre'),
    ):
        df[r] = df[e] / df[t]

    for h in (
        'level_in_escursionisti_feriali', 'level_in_escursionisti_prefestivi',
        'level_in_escursionisti_festivi', 'level_in_escursionisti_sempre',
        'level_in_tutti_feriali', 'level_in_tutti_prefestivi',
        'level_in_tutti_festivi', 'level_in_tutti_sempre',
        'level_out_escursionisti_feriali', 'level_out_escursionisti_prefestivi',
        'level_out_escursionisti_festivi', 'level_out_escursionisti_sempre',
        'level_out_tutti_feriali', 'level_out_tutti_prefestivi',
        'level_out_tutti_festivi', 'level_out_tutti_sempre',
    ):
        hl = h + '_label'
        df[hl] = np.where(df[h] == -1, "N/A", "LIV_" + (10 - df[h]).astype(str))
        df[h] = np.where(df[h] == -1, 1, 7 - df[h])

    df['anno'] = 2024
    df.set_index(['comune', 'anno'], inplace=True)

    return df 

def extract_geojson():
    try:
        path = f"{BASE_DIR}/Output/Vodafone-Data/"
        mf = gpd.read_file(path + "cities_gdf_base_columns.geojson")
    except FileNotFoundError:
        print("Diffusion 1 2 / geojson files missing!")
        exit(1)

    mf = mf[mf['AREA_ID'].str.startswith('ITA.04.022.', na=False)]

    mf = mf[['AREA_ID', 'AREA_LABEL', 'geometry']].rename(
        columns={'AREA_ID': 'ID', 'AREA_LABEL': 'comune' })

    mf['comune'] = mf['comune'].str.upper()
    return mf


def extract_diffusion_3(infile):
    if not os.path.isfile(infile):
        print(f"Diffusion 3 input {infile} missing!")
        exit(1)

    mf = gpd.read_file(infile)

    mf = mf[mf['AREA_ID'].str.startswith('ITA.04.022.', na=False)]

    portfolio = [ col for col in mf.columns if col.startswith('portfolio')]
    assert(len(portfolio) == 1)
    portfolio = portfolio[0]

    # TODO: use aggregated value,  not a specific portfolio
    mf = mf[['AREA_ID', 'AREA_LABEL', portfolio, 'geometry']].rename(
        columns={'AREA_ID': 'ID', 'AREA_LABEL': 'comune', portfolio: 'value'})

    mf['comune'] = mf['comune'].str.upper()
    mf['value'] = mf['value'] * 1000

    df = mf[['comune', 'ID', 'value']].copy()

    df['anno'] = 2024
    df.set_index(['comune', 'anno'], inplace=True)

    return df

def main():
    DF_FLUSSI_ESTATE = extract_diffusion_1_2()
    DF_DISTRIBUZIONE_FERIALE = extract_diffusion_3(f"{BASE_DIR}/Output/weekday/geodataframe_input_plots_markowitz_weekday_None_Feriale_None_None.geojson")
    DF_DISTRIBUZIONE_PREFESTIVO = extract_diffusion_3(f"{BASE_DIR}/Output/weekday/geodataframe_input_plots_markowitz_weekday_None_Prefestivo_None_None.geojson")
    DF_DISTRIBUZIONE_FESTIVO = extract_diffusion_3(f"{BASE_DIR}/Output/weekday/geodataframe_input_plots_markowitz_weekday_None_Festivo_None_None.geojson")
    GEOJSON = extract_geojson()

    log_dataframe(DF_FLUSSI_ESTATE.reset_index(), "df_flussi_estate")
    log_dataframe(DF_DISTRIBUZIONE_FERIALE.reset_index(), "df_distribuzione_feriale")
    log_dataframe(DF_DISTRIBUZIONE_PREFESTIVO.reset_index(), "df_distribuzione_prefestivo")
    log_dataframe(DF_DISTRIBUZIONE_FESTIVO.reset_index(), "df_distribuzione_festivo")
    log_geojson(GEOJSON, "map_vodafone_2024")

def local():
    DF_FLUSSI_ESTATE = extract_diffusion_1_2()
    DF_DISTRIBUZIONE_FERIALE = extract_diffusion_3("diffusion/Output/weekday/geodataframe_input_plots_markowitz_weekday_None_Feriale_None_None.geojson")
    DF_DISTRIBUZIONE_PREFESTIVO = extract_diffusion_3("diffusion/Output/weekday/geodataframe_input_plots_markowitz_weekday_None_Prefestivo_None_None.geojson")
    DF_DISTRIBUZIONE_FESTIVO = extract_diffusion_3("diffusion/Output/weekday/geodataframe_input_plots_markowitz_weekday_None_Festivo_None_None.geojson")
    GEOJSON = extract_geojson()

    put_dataframe(DF_FLUSSI_ESTATE, "df_flussi_estate", type='parquet')
    put_dataframe(DF_DISTRIBUZIONE_FERIALE, "df_distribuzione_feriale", type='parquet')
    put_dataframe(DF_DISTRIBUZIONE_PREFESTIVO, "df_distribuzione_prefestivo", type='parquet')
    put_dataframe(DF_DISTRIBUZIONE_FESTIVO, "df_distribuzione_festivo", type='parquet')
    put_geojson(GEOJSON, "map_vodafone_2024")

if __name__ == "__main__":
    local()