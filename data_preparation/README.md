# Data preparation pipeline

```
server -> Output/data/raw_data -> normalized -> data_processed -> final_data
   (0)                   (1)            (2)            (3)
```

The json **mappings** are in a single place, `Output/mapping/` (`paths.mapping`), used by the base build and by the update.

Every step reads the output of the previous one. **Directories, file format and platform settings are all in
`config/settings.yaml`** (the only file to edit for them; neither script takes directories as arguments).
`type_format` (`parquet` by default) applies to every file, in the base build and in the update.

## Layout

```
data_preparation/
├── README.md
├── gen_phenomenon_dataframes.py     # entry point: base build, ALL steps (download -> final parquet)
├── update_phenomenon_dataframes.py       # entry point: yearly update
├── config/
│   ├── settings.yaml                     # directories, file format, platform (edit here)
│   └── updates/                          # one yaml per yearly update: datasets, files, adapters
└── utils/
    ├── config.py          loads config/settings.yaml, exposes it as constants
    ├── cleaning.py        names / ids / frame helpers
    ├── io.py              read / write dataframes, output-dir guard
    ├── remote.py          S3 + DigitalHub (lazy imports: boto3, geopandas, digitalhub)
    ├── readers.py         low-level file readers
    ├── datasets.py        registry: datasets, value columns, references, phenomena
    ├── phenomena.py       processed -> phenomena computation
    ├── disaggregation.py  space / time disaggregation
    ├── steps/             download_data, standardize_raw_data, process_std_data, compute_phenomena (base build)
    │                      standardize_update_raw_data, process_update_std_data (update; compute_phenomena is shared)
    ├── adapters/          year-specific layouts -> aligned layout (registry)
    └── update/            sources (readers), spec (config, parts)
```

## Base build: `gen_base_phenomenon_dataframes.py`

Runs all the steps, from the download to the final files:

| Step | Module | Input | Output |
|------|--------|-------|--------|
| 0 Download | `utils/steps/download_data.py` (`download_raw_base_data`) | server (S3) | `Output/data/raw_data/` |
| 1 Standardization | `utils/steps/standardize_raw_data.py` | raw_data | `Output/data/normalized/` |
| 2 Processing | `utils/steps/process_std_data.py` | normalized (+ mappings in `Output/mapping`) | `Output/data/data_processed/` |
| 3 Phenomena | `utils/steps/compute_phenomena.py` | data_processed | `Output/data/final_data/` (+ platform with `--upload`) |

* **Download** saves data as they arrive: no renaming, no normalization. The mappings go to `Output/mapping/`, not to raw_data.
* **Standardization** uniforms column names, `DATA`/`LOCATION` schema, dates and comune names (no filtering/aggregation).
  Output: `popolazione_std`, `strutture_std`, `vodafone_std`. The ISPAT arrivals / presences (alb, extralb) are **not normalized**.
* **Processing**: `ID_COMUNE` resolution/padding, filtering, column selection, spatial/temporal disaggregation
  (comune x day). Output: `*_pr`. The presences are processed **in this order**:
  1. `vodafone`: areas mapping to more than one comune are split linearly to the beds (`tot_postiletto` of
     `strutture_pr`, same year or nearest); single-comune areas are unchanged.
  2. `presenze_alb` / 3. `presenze_extralb`: read as downloaded from `raw_data`
     (`Presenze/<arrivi|presenze>_<alb|exalb>_<year>.csv`; base build: 2022, 2023, updates: later years).
     alb: only the `<APT> - Totale` columns are used; extralb: only the first and the last column (provincial
     total); the `Anno` row and the empty row are dropped. Monthly area presences are distributed over the days
     with the **average stay** of the month (presences / arrivals): the arrivals of a month are uniform over its
     days and each arrival adds presences on the following days, also across the end of the month. Daily values
     are rescaled and rounded so that each area-month sums exactly to the official presences. Then area x day
     is split over comuni proportionally to the beds of the normalized strutture (`alberghieri posti_letto` for
     alb, `extra alb. Posti_letto` for extralb; same year or nearest). Arrivals are not in the output.
     The sums are checked (ValueError otherwise). Details: `utils/stay_distribution.py`.
  Every vodafone / ISPAT step checks that summing back gives the original totals.
* **Phenomena**: `phen_popolazione`, `phen_strutture`, `phen_presenze` (alb + xalb + vodafone unified).

```bash
python -m gen_base_phenomenon_dataframes                   # all steps, parquet
python -m gen_base_phenomenon_dataframes --skip-download   # reuse Output/data/raw_data
python -m gen_base_phenomenon_dataframes --upload          # also log final data to the platform
```
Each step can also be run alone, e.g. `python -m utils.steps.process_std_data`.

## Yearly update: `update_phenomenon_dataframes.py`

Same steps of the base build, with update-specific versions of standardize and process:

| Step | Module | Input | Output |
|------|--------|-------|--------|
| 0 Download | `utils/steps/download_data.py` (`download_update_raw_data`) | server (S3) or `update.local_source_dir` | `Output/data/raw_data/` + `Output/mapping/` |
| 1 Standardization | `utils/steps/standardize_update_raw_data.py` | raw_data | `Output/data/normalized/<dataset>_update_std` |
| 2 Processing | `utils/steps/process_update_std_data.py` | normalized (+ mappings) | `Output/data/data_processed/<dataset>_update_pr` |
| 3 Phenomena | `utils/steps/compute_phenomena.py` (`datasets=[...]`) | `<dataset>_update_pr` + existing `final_data` | `Output/data/final_data/` (appended) |

* **Download**: `download_raw_base_data` and `download_update_raw_data` live in the same module and share
  `download_mappings`: the mapping json files and the geojson go to `Output/mapping/` in both cases.
  The update downloads the files listed in the update config.
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
  (`phen_presenze` needs `vodafone`, `presenze_alb` and `presenze_extralb`); the others are skipped with a warning.
  The final data of the base build must already exist.

```bash
python -m update_phenomenon_dataframes --config data_preparation/config/updates/update_2026.yaml
python -m update_phenomenon_dataframes --config ... --skip-download   # reuse raw_data and mappings
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

For now data have been retrived on request and we cannot make assumptions about the structures files will 
have in future versions for yearly updates.

For this reason update_phenonmenon_datafrems requires for year 2025 some temporary files generated by the previous step.

### Outputs

Update files are kept next to the base ones: raw sources in `raw_data`, `<dataset>_update_std` in `normalized`,
`<dataset>_update_pr` in `data_processed` (the base `<dataset>_pr` are **not** modified), and the final
phenomenon files (`phen_popolazione`, `phen_strutture`, `phen_presenze`) in `final_data`, with the update rows appended.

### Strutture and popolazione

* **strutture**: the default `strutture_annuario` adapter expects the 2025 XLSX layout (two-row header and `Comune`).
  The known 2024 ODS variant uses `strutture_annuario_2024` (`Comuni`). If a file does not match its selected
  handler, validation stops and asks for a dedicated adapter rather than guessing its layout. The adapters rename
  columns (`Alloggi turistici` → `all. privati`, `Alloggi a disposizione` → `all. disposizione`,
  `Totale` → `tot convenzionali`) and converts `-` to 0. In processed data (base and update) the raw
  `tot convenzionali strutture / posti_letto` are **discarded**: conv is recomputed as alberghieri + extralberghieri,
  total = conv + non conv (`all. privati`).
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



