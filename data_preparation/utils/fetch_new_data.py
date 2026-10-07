import pandas as pd 
from pathlib import Path
from data_preparation.utils.utils import (
    get_mapping, get_s3
)
from data_preparation.utils.common import (
    _read_grouped_presenze_tsv, OUTPUT_DIR 
)
UPDATE_PROCESSED_DIR = OUTPUT_DIR / "data_update" / "data_raw"

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

def _save_raw(buffer, filename, raw_dir):
    """Helper to save raw data downloaded from S3 in the specified folder."""
    if raw_dir and buffer:
        path = Path(raw_dir)
        path.mkdir(parents=True, exist_ok=True)
        (path / filename).write_bytes(buffer.getvalue())

def fetch_reference_maps(datasets=None, raw_dir=UPDATE_PROCESSED_DIR):
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
    filename = UPDATE_S3_OBJECTS["comuni_trentino_geojson"]
    buffer = get_s3(filename)
    _save_raw(buffer, filename, raw_dir)
    geojson = geopd.read_file(buffer)
    return mapping_vodafone, mapping_comuni, mapping_apt, geojson


def fetch_raw_popolazione(raw_dir=UPDATE_PROCESSED_DIR):
    """Download raw popolazione dataset."""
    raw_popolazione = get_s3( UPDATE_S3_OBJECTS["popolazione"])
    _save_raw(raw_popolazione,  UPDATE_S3_OBJECTS["popolazione"], raw_dir)
    return pd.read_csv(raw_popolazione)


def fetch_raw_strutture(raw_dir=UPDATE_PROCESSED_DIR):
    """Download raw strutture datasets for 2024 and 2025."""
    buf24 = get_s3(UPDATE_S3_OBJECTS["strutture_2024"])
    buf25 = get_s3(UPDATE_S3_OBJECTS["strutture_2025"])
    
    _save_raw(buf24, UPDATE_S3_OBJECTS["strutture_2024"], raw_dir)
    _save_raw(buf25, UPDATE_S3_OBJECTS["strutture_2025"], raw_dir)
    
    strutture_24 = pd.read_excel(buf24, engine="odf")
    strutture_25 = pd.read_excel(buf25, header=[0, 1])
    return strutture_24, strutture_25


def fetch_raw_vodafone(raw_dir=UPDATE_PROCESSED_DIR):
    """Download raw vodafone dataset."""
    raw_vodafone = get_s3(UPDATE_S3_OBJECTS["vodafone"])
    _save_raw(raw_vodafone, UPDATE_S3_OBJECTS["vodafone"], raw_dir)
    return pd.read_csv(raw_vodafone)


def _fetch_raw_presenze_ispat_apt(s3_key, raw_dir=UPDATE_PROCESSED_DIR):
    """Internal helper to download and parse ISPAT TSV files at APT level."""
    buffer = get_s3(UPDATE_S3_OBJECTS[s3_key])
    _save_raw(buffer, UPDATE_S3_OBJECTS[s3_key], raw_dir)
    df = pd.read_csv(buffer, sep="\t", header=None, skiprows=2, dtype=str)
    apts = [x.strip() for x in buffer.getvalue().decode("utf-8").splitlines()[0].split("\t")]
    return df, apts


def fetch_raw_presenze_alb(raw_dir=UPDATE_PROCESSED_DIR):
    """Download raw presenze alberghiere dataset."""
    return _fetch_raw_presenze_ispat_apt("presenze_alb_2025", raw_dir)


def fetch_raw_presenze_extralb(raw_dir=UPDATE_PROCESSED_DIR):
    """Download raw presenze extralberghiere datasets (APT and provincial)."""
    raw_xalb_apt, apts_xalb = _fetch_raw_presenze_ispat_apt("presenze_xalb_2025_apt", raw_dir)
    raw_xalb_prov = get_s3(UPDATE_S3_OBJECTS["presenze_xalb_2025_prov"])
    _save_raw(raw_xalb_prov, UPDATE_S3_OBJECTS["presenze_xalb_2025_prov"], raw_dir)
    raw_xalb_prov = _read_grouped_presenze_tsv(raw_xalb_prov)
    
    return raw_xalb_apt, apts_xalb, raw_xalb_prov