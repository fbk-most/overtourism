# SPDX-License-Identifier: Apache-2.0
"""
STEP 2 - Processing.

Input : Output/data/normalized/   (+ mapping json files, read from Output/mapping; the ISPAT presences
        arrivals / presences are read from Output/data/raw_data/, they are not normalized)
Output: Output/data/data_processed/   (popolazione_pr, strutture_pr, vodafone_pr,
                                       presenze_alb_pr, presenze_extralb_pr)

Transformations: ID_COMUNE resolution, filtering, selection of the columns, computation of
aggregated columns, disaggregation of the presences to comune x day (vodafone: areas -> comuni by beds;
ISPAT: APT / provincia x month -> comune x day, with the average stay of the month, see stay_distribution.py). Every row has a single ID_COMUNE.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from utils.cleaning import (
    ids_to_int,
    normalize_id_comune,
    pad_id_comune,
    remove_provincia,
    resolve_id_comune,
    standard_ordering_cols,
)
from utils.config import (
    MAPPING_DIR,
    NORMALIZED_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    TYPE_FORMAT,
    MAPPING_FILES,
    setup_logging,
)
from utils.datasets import (  # noqa: F401  (re-exported for convenience)
    DATASETS,
    PRESENZE_BASE_YEARS,
    PRESENZE_MEASURES,
    PRESENZE_SPILL_OVER,
    PRESENZE_TAGS,
    POPOLAZIONE_VALUE_COLS,
    PRESENZE_ALB_VALUE_COLS,
    PRESENZE_XALB_VALUE_COLS,
    STRUTTURE_VALUE_COLS,
    VODAFONE_VALUE_COLS,
)
from utils.adapters.presenze import MONTHS_MAPPING
from utils.disaggregation import (
    assert_sums_match,
    beds_weights,
    disaggregate,
    is_whole,
)
from utils.stay_distribution import distribute_by_stay
from utils.io import read_df, read_json, save_computed_dfs

logger = logging.getLogger(__name__)

BEDS_ALB_COL = "posti_letto_alb"
BEDS_XALB_COL = "posti_letto_xalb"


def _filtering_strutture(df, min_year, year_col="DATA"):
    """Excludes years pre-2020, geography changes for municipalities aggregations"""
    return df[df[year_col] > min_year].copy()


def _filtering_vodafone_attendences(df):
    """Filtering presences on tourists and municipalities"""
    return df[
        (df["userProfile"] == "TOURIST") & (df["locType"] == "TN_MKT_AL_3")
    ].copy()


def process_popolazione(df, mapping_comuni):
    df["ID_COMUNE"] = df["LOCATION"].apply(
        lambda x: resolve_id_comune(x, mapping_comuni)
    )
    df = remove_provincia(df, comune_col="LOCATION")
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    return standard_ordering_cols(df[["DATA", "ID_COMUNE"] + POPOLAZIONE_VALUE_COLS])


def process_strutture(df, mapping_comuni):
    df = _filtering_strutture(df, 2019)
    df = remove_provincia(df, comune_col="LOCATION")

    # CONV = alberghieri + extralberghieri (from the raw components, not from the raw CONV totals)
    df["tot_strutture_conv"] = df["alberghieri strutture"] + df["extra alb. Strutture"]
    df["tot_postiletto_conv"] = (
        df["alberghieri posti_letto"] + df["extra alb. Posti_letto"]
    )

    df["tot_strutture_non_conv"] = (
        df["all. privati numero"] + df["all.disposizione numero"]
    )
    df["tot_postiletto_non_conv"] = (
        df["all. privati posti_letto"] + df["all. disposizione posti_letto"]
    )

    # Compute total as the sum of CONV and NON CONV
    df["tot_strutture"] = df["tot_strutture_conv"] + df["tot_strutture_non_conv"]
    df["tot_postiletto"] = df["tot_postiletto_conv"] + df["tot_postiletto_non_conv"]

    # Set ID_COMUNE (resolving the bilingual overrides)
    df["ID_COMUNE"] = df["LOCATION"].apply(
        lambda x: resolve_id_comune(x, mapping_comuni)
    )
    missing = df.loc[df["ID_COMUNE"].isna(), "LOCATION"].unique()
    if len(missing) > 0:
        logger.warning(
            "[process_strutture] No ID_COMUNE found (even with overrides) for: %s",
            sorted(missing),
        )

    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    return standard_ordering_cols(df[["DATA", "ID_COMUNE"] + STRUTTURE_VALUE_COLS])


def process_vodafone(
    df, mapping_vodafone, strutture=None, bed_col="tot_postiletto", check=True
):
    """vodafone presences: vodafone areas x day -> comune x day.

    Areas that map to a single comune are unchanged. Areas that map to several comuni are split
    linearly to the beds (`bed_col` of `strutture`, year of the day or nearest year) of their comuni.
    Without `strutture` the split is uniform. With check=True the totals are summed back
    (per area and day) and a mismatch raises ValueError.
    """
    df = _filtering_vodafone_attendences(df)  # only COMUNI & TURISTI
    df["ID_COMUNE"] = df["LOCATION"].map(mapping_vodafone)
    mask = df["LOCATION"] == "SAN GIOVANNI DI FASSA"
    df.loc[mask, "ID_COMUNE"] = pd.Series(
        [[22250]] * mask.sum(), index=df.index[mask], dtype=object
    )
    if df["ID_COMUNE"].isna().any():
        locations = sorted(
            df.loc[df["ID_COMUNE"].isna(), "LOCATION"].dropna().unique().tolist()
        )
        logger.warning(
            "[process_vodafone] %d rows Vodafone (%d aree) with no mapping ID_COMUNE; "
            "rows will be excluded by groupby: %s",
            int(df["ID_COMUNE"].isna().sum()),
            len(locations),
            locations,
        )
    df["DATA"] = pd.to_datetime(df["DATA"].astype(str), errors="coerce").dt.strftime(
        "%Y-%m-%d"
    )
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"]).apply(
        normalize_id_comune
    )  # hashable

    # Sum per (day, vodafone area), then split each area over its comuni
    df = df.groupby(["DATA", "ID_COMUNE"], as_index=False)[VODAFONE_VALUE_COLS].sum()
    integer = is_whole(df, VODAFONE_VALUE_COLS)
    df["_TID"] = np.arange(len(df))

    kwargs = {}
    if strutture is not None:
        years = pd.to_datetime(df["DATA"]).dt.year.unique()
        kwargs = dict(
            space_weights=beds_weights(strutture, years, bed_col),
            space_weight_col=bed_col,
            space_time_freq="Y",  # beds are yearly
        )
    else:
        logger.warning("[process_vodafone] no strutture given: uniform split")

    out = disaggregate(
        df, cols=VODAFONE_VALUE_COLS, axis="space", integer=integer, **kwargs
    )
    if check:
        assert_sums_match(df, out, VODAFONE_VALUE_COLS, ["_TID"], name="vodafone")
        assert_sums_match(df, out, VODAFONE_VALUE_COLS, ["DATA"], name="vodafone/day")
    return standard_ordering_cols(out.drop(columns="_TID").reset_index(drop=True))


def process_beds(strutture_std, mapping_comuni):
    """Beds per comune and year from the NORMALIZED strutture: DATA (year), ID_COMUNE, posti_letto_alb
    (`alberghieri posti_letto`), posti_letto_xalb (`extra alb. Posti_letto`)."""
    df = _filtering_strutture(strutture_std, 2019)
    df = remove_provincia(df, comune_col="LOCATION")
    df["ID_COMUNE"] = df["LOCATION"].apply(
        lambda x: resolve_id_comune(x, mapping_comuni)
    )
    missing = df.loc[df["ID_COMUNE"].isna(), "LOCATION"].unique()
    if len(missing) > 0:
        logger.warning("[process_beds] No ID_COMUNE found for: %s", sorted(missing))
    df = df[df["ID_COMUNE"].notna()].copy()
    df["ID_COMUNE"] = pad_id_comune(df["ID_COMUNE"])
    df = df.rename(
        columns={
            "alberghieri posti_letto": BEDS_ALB_COL,
            "extra alb. Posti_letto": BEDS_XALB_COL,
        }
    )
    return df[["DATA", "ID_COMUNE", BEDS_ALB_COL, BEDS_XALB_COL]].reset_index(drop=True)


def read_strutture_std(normalized_dir, type_format=TYPE_FORMAT):
    """Every normalized strutture file (base `strutture_std` + the ones of the updates, e.g.
    `strutture_2024_update_std`), stacked: on a duplicated DATA + LOCATION the later file wins.
    """
    normalized_dir = Path(normalized_dir)
    base = DATASETS["strutture"].std_name
    names = sorted(
        f.stem
        for f in normalized_dir.glob(f"strutture*_std.{type_format}")
        if f.stem != base
    )
    frames = [read_df(normalized_dir, n, type_format) for n in [base, *names]]
    df = pd.concat(frames, ignore_index=True)
    return df.drop_duplicates(["DATA", "LOCATION"], keep="last").reset_index(drop=True)


# ---- ISPAT arrivals / presences: read as downloaded, no normalization
def _monthly_long(df, year, source):
    """Rows of the 12 months (the `Anno` total row and the empty row are dropped) -> long frame with
    DATA = first day of the month, `variable` (column name) and `value`."""
    first = df.columns[0]
    month = df[first].astype(str).str.strip().map(MONTHS_MAPPING)
    if month.notna().sum() != 12 or month.dropna().nunique() != 12:
        raise ValueError(
            f"{source}: expected the 12 months in the first column, found {df[first].tolist()}"
        )
    dropped = df.loc[month.isna(), first].tolist()
    logger.info("[%s] rows dropped: %s", source, dropped)
    df = df.loc[month.notna()].copy()
    df["DATA"] = [
        pd.Timestamp(year=int(year), month=int(m), day=1) for m in month[month.notna()]
    ]
    long = df.drop(columns=first).melt(
        id_vars="DATA", var_name="variable", value_name="value"
    )
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    if long["value"].isna().any():
        raise ValueError(
            f"{source}: missing / non numeric values in {sorted(long.loc[long['value'].isna(), 'variable'].unique())}"
        )
    return long


def clean_presenze_alb(df, year, source="presenze_alb"):
    """ISPAT alb table (months x APT): only the `<APT> - Totale` columns are kept (`- Italiani`,
    `- Stranieri` and the `Provincia - ...` columns are ignored). -> (AREA = APT, DATA, value).
    """
    cols = [
        c
        for c in df.columns[1:]
        if str(c).endswith(" - Totale") and not str(c).startswith("Provincia - ")
    ]
    long = _monthly_long(df[[df.columns[0], *cols]], year, source)
    long["AREA"] = long.pop("variable").str.removesuffix(" - Totale").str.strip()
    return long[["AREA", "DATA", "value"]]


def clean_presenze_exalb(df, year, source="presenze_extralb"):
    """ISPAT extra alb table (months x type of structure): only the first column and the last one
    (the provincial total, `Totale - Totale`) are kept. -> (AREA = "PROVINCIA", DATA, value).
    """
    long = _monthly_long(df.iloc[:, [0, -1]], year, source)
    long["AREA"] = "PROVINCIA"
    return long[["AREA", "DATA", "value"]]


def presenze_files(raw_dir, tag, years):
    """Convention of the file names: {(measure, year): raw_dir/<measure>_<tag>_<year>.csv} (existing files)."""
    raw_dir = Path(raw_dir)
    files = {}
    for y in years:
        for m in PRESENZE_MEASURES:
            f = raw_dir / f"{m}_{tag}_{y}.csv"
            if f.exists():
                files[(m, int(y))] = f
    return files


def process_presenze_stay(
    files,
    tag,
    years,
    area_ids,
    beds,
    *,
    bed_col,
    out_col,
    spill_over=PRESENZE_SPILL_OVER,
):
    """ISPAT arrivals + presences (month x area) of `years` -> comune x day presences (see stay_distribution.py).

    files    {(measure, year): path} with measure in ("arrivi", "presenze"); every year needs both.
             The files of the year before `years` (if present) give the stays that cross the new year.
    tag      "alb" (areas = APT, with the `- Totale` columns) or "exalb" (province).
    area_ids {area: [ids]}; beds: (DATA, ID_COMUNE, bed_col) weights of the split among comuni.
    """
    years = sorted(int(y) for y in years)
    context = years[0] - 1
    has_context = spill_over and all((m, context) in files for m in PRESENZE_MEASURES)
    use = [context, *years] if has_context else years
    if spill_over and not has_context:
        logger.warning(
            "[%s] no files of %s: the stays that cross the beginning of %s are approximated",
            out_col,
            context,
            years[0],
        )
    clean = clean_presenze_alb if tag == "alb" else clean_presenze_exalb
    tables = {m: [] for m in PRESENZE_MEASURES}
    for y in use:
        for m in PRESENZE_MEASURES:
            if (m, y) not in files:
                raise FileNotFoundError(
                    f"missing file for {m} {tag} {y}: run the download step"
                )
            raw = pd.read_csv(files[(m, y)])
            tables[m].append(clean(raw, y, source=f"{m}_{tag}_{y}"))
    arrivals, presences = (
        pd.concat(tables[m], ignore_index=True) for m in PRESENZE_MEASURES
    )

    names = set(arrivals["AREA"])
    if names != set(area_ids):
        raise ValueError(
            f"[{out_col}] areas of the files and of the mapping differ: "
            f"only in files {sorted(names - set(area_ids))}, only in mapping {sorted(set(area_ids) - names)}"
        )
    out = distribute_by_stay(
        arrivals,
        presences,
        area_ids,
        beds,
        bed_col=bed_col,
        out_col=out_col,
        keep_from=pd.Timestamp(years[0], 1, 1),
        spill_over=spill_over,
    )
    return standard_ordering_cols(out)


def presenze_alb_area_ids(mapping_apt):
    return {k: [int(i) for i in v] for k, v in mapping_apt.items()}


def presenze_exalb_area_ids(mapping_comuni):
    return {"PROVINCIA": sorted({int(i) for i in mapping_comuni.values()})}


def load_mappings(mapping_dir):
    mapping_dir = Path(mapping_dir)
    return {key: read_json(mapping_dir / fname) for key, fname in MAPPING_FILES.items()}


def process_data(
    normalized_dir=NORMALIZED_DIR,
    mapping_dir=MAPPING_DIR,
    out_dir=PROCESSED_DIR,
    type_format=TYPE_FORMAT,
    raw_dir=RAW_DIR,
):
    normalized_dir = Path(normalized_dir)

    logger.info("Reading standardized data from %s", normalized_dir)
    std = {
        name: read_df(normalized_dir, spec.std_name, type_format)
        for name, spec in DATASETS.items()
        if spec.normalized
    }
    maps = load_mappings(mapping_dir)
    mapping_comuni, mapping_vodafone, mapping_apt = (
        maps["mapping_comuni"],
        maps["mapping_vodafone"],
        maps["mapping_apt"],
    )

    # Order: strutture -> vodafone (areas with several comuni split by beds) -> alb -> extralb.
    # alb / extralb (ISPAT arrivals + presences, read from raw_data) are distributed taking the average
    # stay into account, and split among comuni by `alberghieri` / `extra alb.` beds.
    strutture_pr = process_strutture(std["strutture"], mapping_comuni)
    vodafone_pr = process_vodafone(std["vodafone"], mapping_vodafone, strutture_pr)
    beds = process_beds(read_strutture_std(normalized_dir, type_format), mapping_comuni)
    alb_pr = process_presenze_stay(
        presenze_files(raw_dir, PRESENZE_TAGS["presenze_alb"], PRESENZE_BASE_YEARS),
        "alb",
        PRESENZE_BASE_YEARS,
        presenze_alb_area_ids(mapping_apt),
        beds,
        bed_col=BEDS_ALB_COL,
        out_col=PRESENZE_ALB_VALUE_COLS[0],
    )
    extralb_pr = process_presenze_stay(
        presenze_files(raw_dir, PRESENZE_TAGS["presenze_extralb"], PRESENZE_BASE_YEARS),
        "exalb",
        PRESENZE_BASE_YEARS,
        presenze_exalb_area_ids(mapping_comuni),
        beds,
        bed_col=BEDS_XALB_COL,
        out_col=PRESENZE_XALB_VALUE_COLS[0],
    )
    dict_processed = {
        "popolazione_pr": process_popolazione(std["popolazione"], mapping_comuni),
        "strutture_pr": strutture_pr,
        "vodafone_pr": vodafone_pr,
        "presenze_alb_pr": alb_pr,
        "presenze_extralb_pr": extralb_pr,
    }

    save_computed_dfs(
        dict_processed, local=True, type_format=type_format, path_saving=out_dir
    )
    logger.info("Processed data saved in %s", out_dir)
    return dict_processed


if __name__ == "__main__":
    setup_logging()
    process_data()
