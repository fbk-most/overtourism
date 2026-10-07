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
    ├── steps/             download_raw_data, standardize_raw_data, process_std_data, compute_phenomena
    ├── adapters/          year-specific layouts -> aligned layout (registry)
    └── update/            sources (S3/local + readers), spec (config), transform, merge
```

## Base build: `gen_base_phenomenon_dataframes.py`

Runs all the steps, from the download to the final files:

| Step | Module | Input | Output |
|------|--------|-------|--------|
| 0 Download | `utils/steps/download_raw_data.py` | server (S3) | `Output/data/raw_data/` |
| 1 Standardization | `utils/steps/standardize_raw_data.py` | raw_data | `Output/data/normalized/` |
| 2 Processing | `utils/steps/process_std_data.py` | normalized (+ mappings in `Output/mapping`) | `Output/data/data_processed/` |
| 3 Phenomena | `utils/steps/compute_phenomena.py` | data_processed | `Output/data/final_data/` (+ platform with `--upload`) |

* **Download** saves data as they arrive: no renaming, no normalization. The mappings go to `Output/mapping/`, not to raw_data.
* **Standardization** uniforms column names, `DATA`/`LOCATION` schema, dates and comune names (no filtering/aggregation).
  Output: `popolazione_std`, `strutture_std`, `vodafone_std`, `presenze_alb_std`, `presenze_extralb_std`.
* **Processing**: `ID_COMUNE` resolution/padding, filtering, column selection, spatial/temporal disaggregation
  (comune x day). Output: `*_pr`.
* **Phenomena**: `phen_popolazione`, `phen_strutture`, `phen_presenze` (alb + xalb + vodafone unified).

```bash
python -m data_preparation.gen_base_phenomenon_dataframes                   # all steps, parquet
python -m data_preparation.gen_base_phenomenon_dataframes --skip-download   # reuse Output/data/raw_data
python -m data_preparation.gen_base_phenomenon_dataframes --upload          # also log final data to the platform
```
Each step can also be run alone, e.g. `python -m data_preparation.utils.steps.process_std_data`.

## Yearly update: `update_phenomenon_dataframes.py`

Brings new data into the already processed ones (`paths.processed` in `settings.yaml`, produced by the base build):

The update writes its artifacts into the same folders as the base build. New raw sources are archived in `Output/data/raw_data/`, standardized update parts go to `Output/data/normalized/`, merged processed datasets replace the touched files in `Output/data/data_processed/`, and phenomena are recomputed into `Output/data/final_data/`.

1. for each dataset in the update config: fetch (raw copy to `paths.raw`) → **reader** → **adapter** (provider layout → aligned layout, checked against its schema) → **standardize** (saved in `paths.normalized`) → **process**
2. read the current processed data (`paths.processed`) and merge on `DATA` + `ID_COMUNE`; new rows replace matching old rows, and touched merged datasets are written back to `paths.processed`
3. recompute all phenomena from the resulting processed datasets and save them to `paths.final`

The standardize and process functions are the same ones of the base build. Shared mapping and GeoJSON references are configured once in `settings.yaml`; mappings are read from `Output/mapping` (if one is missing it is fetched and saved there).

```bash
python -m data_preparation.update_phenomenon_dataframes --config data_preparation/config/updates/update_2026.yaml
```
The update reuses the shared mappings in `Output/mapping/`; required GeoJSON and configured update source files are also archived in `Output/data/raw_data/`. To read source files from a local folder instead of S3 set `update.local_source_dir` in `settings.yaml`.
Only `--config` and `--no-strict` (adapter schema mismatch → warning instead of error) are supported:
directories, reference files and format come from `settings.yaml`, datasets from the update yaml.
From Python: `update_pipeline(config)`.

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
        # label: "2026"                        # optional: keeps this source separate until the merge
```
      Sources without a label share the `<dataset>_update` part. A labeled source is kept separate during processing
      (e.g. two strutture years) and parts of the same dataset are stacked before the merge (later sources win on overlap).
To update a subset, list only those datasets or set `enabled: false` on the others; their processed datasets remain unchanged. Each run recomputes the final phenomena using all datasets in `paths.processed`.

### Outputs

Update outputs follow the base-build layout. Merged processed datasets (for example `popolazione_pr.parquet`) are written to `Output/data/data_processed/`, replacing the touched dataset files; final phenomenon files (`phen_popolazione`, `phen_strutture`, `phen_presenze`) are refreshed in `Output/data/final_data/`. Raw source files and standardized parts are kept in their matching `raw_data` and `normalized` subfolders.

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
   stops the run with a clear error. Config errors (unknown dataset/adapter/reader, wrong adapter parameters)
   are also reported before anything is downloaded.
4. Run the update and inspect the merged frames in `Output/data/data_processed/` and refreshed phenomena in `Output/data/final_data/`.

## Requirements

`pandas`, `numpy`, `unidecode`, `pyyaml`, `pyarrow`, `openpyxl`, `odfpy`; `boto3`, `geopandas`, `digitalhub`
are needed only to talk to S3 / the platform (imported lazily).
The credentials of S3 are read from `~/.dhcore.ini` (section: `platform.dhcore_env` in `settings.yaml`).
