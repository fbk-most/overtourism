# Data transformation into phenomena process 
This folder contains the data preparation pipeline that processes raw data in order to calculate overtourism and tourist capacity indices for Trentino.

The data are processed and transformed with the following steps: they are standardized into a unified schema, then they are stored (locally or on remote) and used to calculate the base quantities ("phenomena"), required to compute the final indices, by performing operations such as spatial/temporal disaggregation depending on the granularity of the initial data.

---

## Two-Step Pipeline

### 1. Standardization (`standardize_raw_data.py`)
Takes raw data and brings them all into the same common schema:
- **`DATA`**: Temporal dimension (`YYYY` for annual data, `YYYY-MM-DD` for daily/monthly data).
- **`LOCATION`**: Name of the municipality or area (*comune* / *ambito*).
- **`ID_COMUNE`**: ISTAT municipal code, always stored as a 6-digit zero-padded string (`"022001"`). Some phenomena (e.g., Vodafone attendences) can contain a list of IDs instead of a single string (because areas correspond to multiple municipalities)
- Phenomenon-specific columns (e.g., `presenze_alb`, `tot_postiletto`, etc.).

Each data source has its own dedicated function:
- `standardize_popolazione`: Annual population per municipality.
- `standardize_strutture`: Annual accommodation structures 
- `standardize_vodafone`: Daily tourist presences detected by Vodafone.
- `standardize_presenze_ISPAT_alb`: Monthly ISPAT hotel presences at  APT level.
- `standardize_presenze_ISPAT_extralb`: Monthly ISPAT non-hotel presences at the provincial level.

Output files are cached locally in `data_std/` (Parquet or CSV).
Some helper functions (for handling standardisation, such as `_pad_id_comune` and `_remove_provincia`, or for interacting with the platform...) are used, from the `utils.py`.

---

### 2. Phenomenon Calculation (`gen_base_phenomenon_dataframes.py`)
Loads the standardized DataFrames and combines/disaggregates them to generate the final phenomena to use for the index computation:
- `phen_popolazione`
- `phen_strutture`
- `phen_presenze` (combination of ISPAT hotel + non-hotel + Vodafone presences)

**Spatio-Temporal Disaggregation:** ISPAT data are at a higher granularity level (spatial and temporal), but the pipeline requires daily municipal-level data. The disaggregation method supports two possibilities:
- `"uniform"`: Evenly distributes values across municipalities and days
- `"distributional"`: Allocates values using a weighting distribution (e.g., daily Vodafone presences).

Finally, output dataframes are either saved locally or logged to DigitalHub based on the `local` flag.


## How to Run

### Run the complete pipeline from scratch:
```python
from data_preparation.v2.gen_base_phenomenon_dataframes import compute_phenomenon_dataframes

compute_phenomenon_dataframes(local=True, use_cached_standardized=False)
```
This will save the phenomena locally, starting from the raw data and performing the standardization process from scratch. If `use_cached_standardized` is set to True and no local data are stored, the process is executed anyway.  

