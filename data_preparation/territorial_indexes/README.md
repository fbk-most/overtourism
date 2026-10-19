# Territorial indexes: data preparation pipeline

Builds the phenomenon dataframes (`phen_popolazione`, `phen_strutture`, `phen_presenze`, `phen_consumption`,
`phen_flussi_od`, `phen_provenienza`) behind the territorial indexes: a **base build** (gen) and a **yearly update**
(gen can also run the update of 2025 only, see [Running](#running-gen-and-the-2025-update)). Part of
`data_preparation/` (see its [README](../README.md)); the model pipelines live in `../model/`. All commands below are run
from this folder (`territorial_indexes/`).

```
server -> Output/data/raw_data -> normalized -> data_processed -> final_data
   (0)                   (1)            (2)            (3)
```

`Output/` is `data_preparation/Output` (`output_dir: ../Output`), shared with the model pipelines.
The json **mappings** are in a single place, `Output/mapping/` (`paths.mapping`), used by the base build and by the update.

Every step reads the output of the previous one. **Directories, file format and platform settings are all in
`config/settings.yaml`** (the only file to edit for them; neither script takes directories as arguments).
`type_format` (`parquet` by default) applies to every file, in the base build and in the update.

**Time window**: gen = 2022-01-01 .. 2024-12-31, update 2025 = 2025 only, nothing before 2022 (`period` in `config/settings.yaml`). Steps: [METHODOLOGY.md](METHODOLOGY.md); decisions, assumptions and **how every phenomenon is computed**: [ASSUMPTIONS.md](ASSUMPTIONS.md).

**Downloads are never repeated**: in the base build and in the update, step 0 checks file by file whether the object is
already in `Output/data/raw_data/` (or `Output/mapping/`) and, if so, does not download it (`--force-download` overrides
the check). `--skip-download` skips step 0 altogether.

## Layout

```
territorial_indexes/
├── README.md, METHODOLOGY.md, ASSUMPTIONS.md
├── gen_phenomenon_dataframes.py     # entry point: base build, ALL steps (download -> final parquet); --with-update / --update-only: also the 2025 update
├── update_phenomenon_dataframes.py  # entry point: yearly update
├── config/
│   ├── settings.yaml                     # directories, file format, period, platform (edit here)
│   └── updates/                          # one yaml per yearly update: datasets, files, adapters
├── tests/
└── utils/
    ├── config.py          loads config/settings.yaml, exposes it as constants
    ├── cleaning.py        names / ids / frame helpers
    ├── io.py              read / write dataframes, output-dir guard
    ├── remote.py          S3 + DigitalHub (lazy imports: boto3, geopandas, digitalhub)
    ├── readers.py         low-level file readers
    ├── datasets.py        registry: datasets, value columns, references, phenomena
    ├── window.py          time window (period in settings.yaml): clip(df, window)
    ├── disaggregation.py  space / time disaggregation
    ├── steps/             download_data, standardize_raw_data, process_std_data, create_phenomena_df (base build; shared by the update)
    │                      standardize_update_raw_data, process_update_std_data (update; compute_phenomena is shared)
    ├── flows.py           OD co-visits -> yearly flow indicators (areas -> comuni), tourists + visitors combined
    ├── adapters/          year-specific layouts -> aligned layout (registry)
    ├── provenienza.py     normalized HHI of the source markets (areas -> comuni)
    └── update/            sources (readers), spec (config, parts)
```

## Base build: `gen_phenomenon_dataframes.py`

Runs all the steps, from the download to the final files:

| Step | Module | Input | Output |
|------|--------|-------|--------|
| 0 Download | `utils/steps/download_data.py` (`download_raw_base_data`) | server (S3); files already in raw_data are skipped | `Output/data/raw_data/` |
| 1 Standardization | `utils/steps/standardize_raw_data.py` | raw_data | `Output/data/normalized/` |
| 2 Processing | `utils/steps/process_std_data.py` | normalized (+ mappings in `Output/mapping`) | `Output/data/data_processed/` |
| 3 Phenomena | `utils/steps/create_phenomena_df.py` | data_processed | `Output/data/final_data/` (+ platform with `--upload`) |

* **Download** saves data as they arrive: no renaming, no normalization. The mappings go to `Output/mapping/`, not to raw_data. The 2024 strutture ODS is part of the base build; later annual strutture files remain update inputs.
* **Standardization** uniforms column names, `DATA`/`LOCATION` schema, dates and comune names (no filtering/aggregation).
  Output: `popolazione_std`, `strutture_std`, `vodafone_std`, `ee_prelievi_std`, `gas_prelievi_std`,
  `ee_totale_std`, `gas_totale_std`, `vodafone_covisits_std`. (`vodafone_std` keeps `userCountry` and `userProfile`; it also feeds
  `phen_provenienza`.)
  The ISPAT arrivals / presences (alb, extralb) are **not normalized**. Electricity and gas category CSVs
  from `Energia/ee_prelievi/` and `Energia/gas_prelievi/` are each stacked into one normalized file;
  category rows remain separate at this step.
* **Processing**: `ID_COMUNE` resolution/padding, filtering, column selection, spatial/temporal disaggregation
  (comune x day). Output: `*_pr`. The presences are processed **in this order**:
  1. `vodafone`: areas mapping to more than one comune are split linearly to the beds (`tot_postiletto` of
     `strutture_pr`, same year or nearest); single-comune areas are unchanged.
  2. `presenze_alb` / 3. `presenze_extralb`: read as downloaded from `raw_data`
     (`Presenze/<arrivi|presenze>_<alb|exalb>_<year>.csv`; base build: 2022–2024, updates: later years).
     alb: only the `<APT> - Totale` columns are used; extralb: only the first and the last column (provincial
     total); the `Anno` row and the empty row are dropped. Monthly area presences are distributed over the days
     with the **average stay** of the month (presences / arrivals): the arrivals of a month are uniform over its
     days and each arrival adds presences on the following days, also across the end of the month. Daily values
     are rescaled and rounded so that each area-month sums exactly to the official presences. Then area x day
     is split over comuni proportionally to the beds of the normalized strutture (`alberghieri posti_letto` for
     alb, `extra alb. Posti_letto` for extralb; same year or nearest). Arrivals are not in the output.
     The sums are checked (ValueError otherwise). Details: `utils/stay_distribution.py`.
  Every vodafone / ISPAT step checks that summing back gives the original totals.
  `vodafone_covisits` (OD co-visits between Vodafone areas) is aggregated **per year** into flow indicators, see below.
* **Phenomena**: `phen_popolazione`, `phen_strutture`, `phen_presenze` (alb + xalb + vodafone unified).
  `phen_consumption` has the columns `DATA`, `ID_COMUNE`, `ee_services`, `ee_total`, `gas_services`, `gas_total`
  (daily consumption per comune; electricity in kWh, gas in Smc). `*_services` come from the category files
  (`Energia/<ee_prelievi|gas_prelievi>/*.csv`, tourism-related usage categories summed); `*_total` come from the two
  files `Energia/ee_prelievi/totale_ee.csv` and `Energia/gas_prelievi/totale_gas.csv` (all the usages). For each of the four measures the monthly value of a
  comune is divided evenly across the calendar days of the month (including leap days) and the four are combined
  on `DATA` + `ID_COMUNE` (outer join). In the update they are read with the `energy_csv` reader and the
  `energia_categorie` adapter (same layout as the base files, see `utils/adapters/energia.py` and assumptions
  U1 / A11 in `ASSUMPTIONS.md`).
* **Provenienza** (`phen_provenienza`, index "Provenienza - Indice di concentrazione mercati provenienza"): per comune and **year**,
  `hhi_provenienza` = normalized Herfindahl-Hirschman index of the **TOURIST** presences by country of origin
  (0 = evenly spread over the markets, 1 = a single market) and `giorni_coperti`. Computed in `utils/provenienza.py` from
  `vodafone_std` (same raw files of the presences, so nothing more to download); the formula and the assumptions are in
  `ASSUMPTIONS.md` (A12). Dataset `vodafone_provenienza` -> `vodafone_provenienza_pr`.
* **Flow indicators** (`phen_flussi_od`): see the next section.

### Flow indicators (`vodafone_covisits` -> `phen_flussi_od`)

The Vodafone OD co-visits (`vodafone_covisits.csv`: day x source area x target area, `covisitType` ND / UD,
profile, country) are turned into **yearly** indicators per comune. The computation is the one of
`notebooks/flow_indicators.ipynb`, in `utils/flows.py`; thresholds and filters are constants in `utils/datasets.py`
(`COVISITS_*`).

| Step | What happens |
|------|--------------|
| 1 Standardization | the file is read in chunks and only the rows used by the indicators are kept: area level (`TN_MKT_AL_3`), `TOURIST` / `VISITOR`, empty `userCountry` (total over the countries). Output `vodafone_covisits_std` (`DATA`, source/target id and ambito, `covisitType`, `userProfile`, `value`). |
| 2 Processing | per year and profile: quota in ingresso `UD(*->j)/T(j)`, quota in uscita `UD(j->*)/T(j)`, quota intra-ambito, PageRank of the UD network; then areas -> comuni (an area passes its value to all its comuni, a comune with several areas gets the weighted mean). Output `vodafone_covisits_pr`: `DATA` (year), `ID_COMUNE`, `<metric>_<tourist, visitor or combined>` for the 4 metrics, `giorni_coperti`. The `_combined` columns merge the two profiles with a fixed weight each (VISITOR 0.5), see below. |
| 3 Phenomena | `phen_flussi_od` = `vodafone_covisits_pr` |

* A year with fewer than `COVISITS_FULL_YEAR_DAYS` (360) days is **partial**: it is kept, flagged by `giorni_coperti` and by a warning.
* The mobility shares are `NaN` where `T < COVISITS_MIN_T`; the shares can exceed 1 (users counted in several areas).
* In the **update** the indicators are yearly, so they are recomputed on all the days of the year: the base
  `vodafone_covisits_std` + every part of the update (on common dates the later data win). Only the years touched by the
  update are written in `vodafone_covisits_update_pr`. Config example (`update_2025.yaml`):
  ```yaml
  vodafone_covisits:
    sources:
      - file: vodafone_covisits.csv
        reader: covisits_csv                 # chunked, keeps only the rows of the update period
        adapter: vodafone_covisits_raw       # columns of KIND_SCHEMAS["vodafone_covisits"]
  ```
* In the backend the four indicators are `quota-mobilita-ingresso`, `quota-mobilita-uscita`, `quota-intra-ambito`
  and `pagerank-discretizzato` (PageRank in quantile classes, 10 by default: `PAGERANK_N_CLASSES` in
  `trentino_indicators.py`). They read the `_combined` columns; the tourist / visitor ones are returned next to them.

#### Tourists and visitors: weighted union (`*_combined`, VISITOR weight 0.5)

A tourist-day (overnight stay) and a visitor-day (excursionist) do not weigh the same on a territory, so the
indicators of the backend use their **weighted union**. The weights are applied on the user-days BEFORE the indicators
are computed (`utils/flows.py: combine_profiles`): with weights `w_T = 1`, `w_V`, the shares are
`sum_p w_p UD_p / sum_p w_p T_p` (a profile counts in proportion to its volume AND its weight) and the PageRank is
computed on the network of the weighted flows. With equal weights this is the plain pooled share; with `w_V = 0` it is
the tourist indicator. The reliability threshold `COVISITS_MIN_T` always refers to the raw user-days.

The weights are fixed in `utils/datasets.py`: `COVISITS_PROFILE_WEIGHTS = {"TOURIST": 1.0, "VISITOR": 0.5}`
(`COVISITS_VISITOR_COEFFICIENT = 0.5`), i.e. a visitor-day counts half of a tourist-day. They are not estimated from the
energy / gas consumption any more (nothing is saved, nothing is reused by the update): change the coefficient and rerun
the base build and the update to recompute the `_combined` columns.

**Areas -> comuni.** An area that covers several comuni passes its value to **all** of them (`flows.build_area_comune`
keeps every (area, comune) pair); a comune with several areas gets the weighted mean.

### Running gen and the 2025 update

```bash
python -m gen_phenomenon_dataframes                   # base build 2022-2024, all steps, parquet
python -m gen_phenomenon_dataframes --with-update     # base build, then the update of 2025 only (appended)
python -m gen_phenomenon_dataframes --update-only     # ONLY the update of 2025 (the base build must already exist)
python -m gen_phenomenon_dataframes --update-config config/updates/update_2025.yaml   # yaml used by the two options above (default)
python -m gen_phenomenon_dataframes --skip-download   # reuse Output/data/raw_data, step 0 not run
python -m gen_phenomenon_dataframes --force-download  # download again also the files already in raw_data
python -m gen_phenomenon_dataframes --upload          # also log final data to the platform
```
In every mode the download step skips the files already in `raw_data` (e.g. `vodafone_attendences_new.csv`, read by the
base build and by the 2025 update, is downloaded once). Each step can also be run alone, e.g.
`python -m utils.steps.process_std_data`. From Python: `main_compute_phenomena_dfs(with_update=True)` or
`run_update_2025()`.

## Yearly update: `update_phenomenon_dataframes.py`

Same steps of the base build, with update-specific versions of standardize and process:

| Step | Module | Input | Output |
|------|--------|-------|--------|
| 0 Download | `utils/steps/download_data.py` (`download_update_raw_data`) | server (S3) or `update.local_source_dir`; files already in raw_data are skipped | `Output/data/raw_data/` + `Output/mapping/` |
| 1 Standardization | `utils/steps/standardize_update_raw_data.py` | raw_data | `Output/data/normalized/<dataset>_update_std` |
| 2 Processing | `utils/steps/process_update_std_data.py` | normalized (+ mappings) | `Output/data/data_processed/<dataset>_update_pr` |
| 3 Phenomena | `utils/steps/create_phenomena_df.py` (`datasets=[...]`) | `<dataset>_update_pr` + existing `final_data` | `Output/data/final_data/` (appended) |

* **Download**: `download_raw_base_data` and `download_update_raw_data` live in the same module and share
  `download_mappings`: the mapping json files and the geojson go to `Output/mapping/` in both cases.
  The update downloads the files listed in the update config, except the ones already in `raw_data` (checked file by file;
  `--force-download` downloads them again).
* **Standardization**: for each source it first **checks that the column structure is compatible with the
  expected one** (the adapter of the source, then the columns required by its kind, `KIND_SCHEMAS`), renames the
  columns to the standard names, and applies **the same standardize functions of the base build**.
  The result is saved with the standard name `<dataset>_update_std` (`<dataset>_<label>_update_std` for labeled sources).
* **Processing**: the same `process_*` functions of the base build, so `<dataset>_update_pr` has the same format of
  `<dataset>_pr` (`DATA`, zero-padded `ID_COMUNE`, value columns; comune x day for the presences).
  Sources of the same dataset are stacked, later ones win on a duplicated `DATA` + `ID_COMUNE`.
* **Phenomena**: `compute_phenomena` creates the phenomenon dataframes in the base build; in the update it
  **appends** the new ones to the existing files in `final_data`. On a duplicated `DATA` + `ID_COMUNE` the
  update row is kept. A phenomenon is computed only if **all** its datasets are in the update
  (`phen_presenze` needs `vodafone`, `presenze_alb` and `presenze_extralb`; `phen_consumption` needs `ee_prelievi`,
  `gas_prelievi`, `ee_totale` and `gas_totale`); the others are skipped with a warning. In `update_2025.yaml` the four
  energy datasets are `enabled: false` for now (no 2025 energy files confirmed, U1 / A11), so `phen_consumption` is
  not appended by the 2025 update until they are enabled together.
  The final data of the base build must already exist (and it must have the same columns: after the addition of
  `ee_total` / `gas_total` the base build has to be rerun once).

```bash
python -m update_phenomenon_dataframes --config config/updates/update_2026.yaml
python -m update_phenomenon_dataframes --config ... --skip-download   # reuse raw_data and mappings
python -m update_phenomenon_dataframes --config ... --force-download  # download again the files already in raw_data
python -m update_phenomenon_dataframes --config ... --upload          # also log final data to the platform
```
To read source files from a local folder instead of S3 set `update.local_source_dir` in `settings.yaml`.
`--no-strict` turns an adapter schema mismatch into a warning. Directories, reference files and format come from
`settings.yaml`, datasets from the update yaml. From Python: `update_pipeline(config)`.
Each step can also be run alone: `python -m utils.steps.process_update_std_data --config ...`.

### The update config (`config/updates/<round>.yaml`)

Nothing year-specific is in the code: **which datasets**, file names, years, column names and the adapter to use
are here (`update_2025.yaml` reproduces the previous hard-coded behaviour).

```yaml
datasets:                                      # only these are updated
  popolazione:
    enabled: false                             # optional (default true): skip it this round
    sources: [...]
  strutture:
    sources:                                   # several sources are stacked (e.g. one per year)
      - file: numero_strutture_ISPAT_2026.xlsx
        reader: excel                          # csv | excel | ispat_apt_tsv | ispat_grouped_tsv
        reader_kwargs: {header: [0, 1]}        # passed to the reader
        adapter: strutture_annuario            # default handler: 2025 two-row-header layout
        adapter_kwargs: {year: 2026}
        # label: "2026"                        # optional: keeps this source separate until the processed parts are stacked
```
      Sources without a label share the `<dataset>_update` part. A labeled source is kept separate during processing
      (e.g. two strutture years) and parts of the same dataset are stacked in `<dataset>_update_pr` (later sources win on overlap).
To update a subset, list only those datasets or set `enabled: false` on the others; their final data remain unchanged. A phenomenon is appended only if all its datasets are in the update (see Step 3).

### Disclaimer

For now data have been retrieved on request and we cannot make assumptions about the layout the files will have in
future yearly updates. The update needs the output of the base build (final data, normalized strutture and co-visits,
profile weights, 2024 ISPAT files), see `ASSUMPTIONS.md` (U1–U7).

### Outputs

Update files are kept next to the base ones: raw sources in `raw_data`, `<dataset>_update_std` in `normalized`,
`<dataset>_update_pr` in `data_processed` (the base `<dataset>_pr` are **not** modified), and the final
phenomenon files (`phen_popolazione`, `phen_strutture`, `phen_presenze`, `phen_consumption`, `phen_flussi_od`, `phen_provenienza`) in
`final_data`, with the update rows appended (only for the phenomena whose datasets are all in the update).

### Strutture and popolazione

* **strutture**: the base build combines the historical CSV with the 2024 ODS variant, using
  `strutture_annuario_2024` (`Comuni`). Yearly updates use the default `strutture_annuario` adapter, which
  expects the 2025 XLSX layout (two-row header and `Comune`). If a file does not match its selected
  handler, validation stops and asks for a dedicated adapter rather than guessing its layout. The adapters rename
  columns (`Alloggi turistici` → `all. privati`, `Alloggi a disposizione` → `all. disposizione`,
  `Totale` → `tot convenzionali`) and converts `-` to 0. In processed data (base and update) the raw
  `tot convenzionali strutture / posti_letto` are **discarded**: conv is recomputed as alberghieri + extralberghieri,
  total = conv + `all. privati` (the `all. disposizione` are kept as separate columns but are not part of the totals,
  see A5).
* **popolazione**: the value is the column `Popolazione residente al 1.1.<year>` (`year: 2025` → second column of the file).

### A new year arrives

1. Upload the raw files to the data lake.
2. Copy `config/updates/update_2025.yaml` → `update_2026.yaml`; change file names, `year`, column names.
3. If the provider changed a layout, add an adapter (function + decorator) in `utils/adapters/` — nothing else:
   ```python
   @register_adapter("popolazione_ispat_2027", kind="popolazione")
   def popolazione_ispat_2027(raw: RawData, *, year: int) -> pd.DataFrame:
       return raw.df.rename(columns={"Territorio": "comune", "Residenti": "popolazione"}).assign(anno=year)
   ```
   The output must contain the columns of its `kind` (`KIND_SCHEMAS` in `utils/adapters/base.py`); a mismatch
   stops the standardization step with a clear error. Config errors (unknown dataset/adapter/reader, wrong adapter
   parameters) are reported before anything is downloaded.
4. Run the update and inspect `Output/data/data_processed/<dataset>_update_pr` and the appended phenomena in `Output/data/final_data/`.



