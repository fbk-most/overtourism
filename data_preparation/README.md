# Data preparation pipeline

```
server -> Output/raw_data -> Output/normalized -> Output/data_processed -> Output/final_data
      (0)                 (1)                  (2)                      (3)             
```

Each step reads the output of the previous one to perform its computations and saves the results in `Output/` directory, in `type_format` format (`csv` default, or `parquet`, must be the same in all the steps).

| Step | Script | Input | Output |
|------|--------|-------|--------|
| 0 - Download | `download_raw_data.py` | server (S3) | `Output/raw_data/` |
| 1 - Standardization | `standardize_raw_data.py` | `Output/raw_data/` | `Output/normalized/` |
| 2 - Processing | `process_data.py` | `Output/normalized/` (+ mappings in `Output/raw_data/`) | `Output/data_processed/` |
| 3 - Final dataframes | `gen_phenomenon.py` | `Output/data_processed/` | `Output/final_data/` (or upload) |

## Step 0 - Download raw data
File: `download_raw_data.py`
Saves the data exactly as they arrive from the server: no renaming, no normalization.
Geojson, json mapping, and data: copied as they are

## Step 1 - Standardization
File: `standardize_raw_data.py`

Uniforms the raw data (column names, `DATA`/`LOCATION` schema, date format, comune names).
No filtering and no aggregation.

Output: `popolazione_std`, `strutture_std`, `vodafone_std`, `presenze_alb_std`, `presenze_extralb_std`.

## Step 2 - Processing
File: `process_data.py`

Transformations: `ID_COMUNE` resolution and padding, data filtering (type of user for vodafone, years
for strutture), selection of the useful columns and finally spatial / temporal disaggregation (day x comune).

Output: `popolazione_pr`, `strutture_pr`, `vodafone_pr`, `presenze_alb_pr`, `presenze_extralb_pr`.

## Step 3 - Final dataframes
File: `gen_base_phenomenon_dataframes.py`

Creation of the phenomenon dataframes, unyfing presenze in a single one.

Output: `phen_popolazione`, `phen_strutture`, `phen_presenze`.
Finally, output dataframes are either saved locally or logged to DigitalHub based on the `local` flag.


## How to Run

### Run the complete pipeline from scratch:
The file `pipeline_phenomena.py` runs the entire pipeline, starting from the raw data and performing the standardization process from scratch. 
## Parameters

In every file, the following parameters can be set: 
- `dir_in`: input directory (output directory of the previous step)
- `dir_in`: output storing directory (input directory of the following step)
- `type_format` controls the format of both the stored file ('csv', 'parquet') 
- for `gen_base_phenomena`: `local`: to decide if store locally or upload
- for `process_data`: `mapping_dir`: directory which contains the mapping files (by default, stored in Output/raw_data)

## Step 4 (optional) - Update

File: `update_pipeline.py` (function `update_pipeline_phen_computation`)

Updates data already processed in `Output/data_processed/` with new sources (e.g. a new year), without rerunning the whole pipeline from scratch. The update can be done on a subset of the datasets: `popolazione`, `strutture`, `vodafone`, `presenze_alb`, `presenze_extralb` (`datasets` parameter, default: all). Datasets not selected are left untouched.

Internal pipeline:
1. download, standardize and process only the sources of the selected datasets
2. read the current processed data from `processed_dir`
3. merge row by row on `DATA` + `ID_COMUNE`: on overlap, the new data are kept
4. recompute the final phenomena affected by the update and save them separately.

Output:
- `Output/data_update/data_processed/`: processed-only datasets from the update (e.g. `popolazione_update_pr`)
- `Output/data_update/merged_processed/`: updated datasets merged with the existing data in `Output/data` (e.g. `popolazione_pr`, `strutture_pr`)
- `Output/data_update/final_phenomena/`: the final phenomena affected by the update

Note on `phen_presenze`: it depends on `vodafone`, `presenze_alb` and `presenze_extralb` together. If you only select some of them, the individual processed datasets are still updated and saved, but `phen_presenze` is not recomputed/saved until all three have been updated (a warning is logged when the selection is partial).

### Parameters

- `datasets`: set of strings among `{"popolazione", "strutture", "vodafone", "presenze_alb", "presenze_extralb"}`; `None` updates everything
- `processed_dir`: directory of the current processed data to update (default `Output/data_processed/`)
- `update_dir`, `merged_dir`, `final_dir`: output directories for the three sub-steps above (default under `Output/data_update/`)
- `type_format`: same as in the other steps, must be consistent with `processed_dir`

### Example

```python
from data_preparation.update_pipeline import update_pipeline_phen_computation

# update popolazione only
update_pipeline_phen_computation(datasets={"popolazione"}, type_format="csv")

# update all presenze (needed to recompute phen_presenze)
update_pipeline_phen_computation(datasets={"vodafone", "presenze_alb", "presenze_extralb"})

# update everything
update_pipeline_phen_computation()
```