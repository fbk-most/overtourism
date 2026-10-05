import pandas as pd 
from data_preparation.utils.utils import (
    get_mapping, get_s3
)
from data_preparation.utils.common import (
    _read_grouped_presenze_tsv
)
import geopandas as geopd

UPDATE_S3_OBJECTS = {
    "popolazione": "popolazione_2026_ISPAT.csv",
    "vodafone": "vodafone_attendences_new.csv",
    "strutture_2024": "strutture_annuario_2024.ods",
    "strutture_2025": "numero_strutture_ISPAT_2025.xlsx",
    "presenze_alb_2025": "presenze_alb_2025.csv",
    "presenze_xalb_2025_apt": "presenze_xalb_2025.csv",
    "presenze_xalb_2025_prov": "presenze_xalb_2025_prov.csv",
    "comuni_trentino_geojson": "TRENTINO-comuni_Vodafone_2023.geojson",
}

# ---------------------------------------------------------------------------
# FETCH / DOWNLOAD RAW DATA HELPERS
# ---------------------------------------------------------------------------

def fetch_reference_maps(datasets=None):
    """Load only reference files needed by the selected update datasets."""
    datasets = set(datasets or {"popolazione", "strutture", "vodafone", "presenze_alb", "presenze_extralb"})
    needs_comuni = bool(datasets & {"popolazione", "strutture", "presenze_extralb"})
    needs_apt = bool(datasets & {"presenze_alb", "presenze_extralb"})
    mapping_vodafone = (
        get_mapping("mapping_comuni_into_vodafone_Trento.json")
        if "vodafone" in datasets
        else None
    )
    mapping_comuni = get_mapping("mapping_comuni_ISTAT.json") if needs_comuni else None
    mapping_apt = get_mapping("map_comuni_into_apt.json") if needs_apt else None
    geojson = (
        geopd.read_file(get_s3(UPDATE_S3_OBJECTS["comuni_trentino_geojson"]))
        if "vodafone" in datasets
        else None
    )
    return mapping_vodafone, mapping_comuni, mapping_apt, geojson


def fetch_raw_popolazione():
    """Download raw popolazione dataset."""
    return pd.read_csv(get_s3(UPDATE_S3_OBJECTS["popolazione"]))


def fetch_raw_strutture():
    """Download raw strutture datasets for 2024 and 2025."""
    strutture_24 = pd.read_excel(get_s3(UPDATE_S3_OBJECTS["strutture_2024"]), engine="odf")
    strutture_25 = pd.read_excel(get_s3(UPDATE_S3_OBJECTS["strutture_2025"]), header=[0, 1])
    return strutture_24, strutture_25


def fetch_raw_vodafone():
    """Download raw vodafone dataset."""
    return pd.read_csv(get_s3(UPDATE_S3_OBJECTS["vodafone"]))


def _fetch_raw_presenze_ispat_apt(s3_key):
    """Internal helper to download and parse ISPAT TSV files at APT level."""
    buffer = get_s3(UPDATE_S3_OBJECTS[s3_key])
    df = pd.read_csv(buffer, sep="\t", header=None, skiprows=2, dtype=str)
    apts = [x.strip() for x in buffer.getvalue().decode("utf-8").splitlines()[0].split("\t")]
    return df, apts


def fetch_raw_presenze_alb():
    """Download raw presenze alberghiere dataset."""
    return _fetch_raw_presenze_ispat_apt("presenze_alb_2025")


def fetch_raw_presenze_extralb():
    """Download raw presenze extralberghiere datasets (APT and provincial)."""
    raw_xalb_apt, apts_xalb = _fetch_raw_presenze_ispat_apt("presenze_xalb_2025_apt")
    raw_xalb_prov = _read_grouped_presenze_tsv(get_s3(UPDATE_S3_OBJECTS["presenze_xalb_2025_prov"]))
    return raw_xalb_apt, apts_xalb, raw_xalb_prov