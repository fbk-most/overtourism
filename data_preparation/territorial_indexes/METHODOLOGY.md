# Methodology: how the phenomena are generated (gen) and updated (update)

```
server -> raw_data -> normalized -> data_processed -> final_data
 (0)         (1)          (2)             (3)
```

Same four steps for the base build (`gen_phenomenon_dataframes.py`) and for the yearly update
(`update_phenomenon_dataframes.py`). Directories, file format and the **time window** are in
`config/settings.yaml`; the decisions behind each step are in [ASSUMPTIONS.md](ASSUMPTIONS.md) (IDs in brackets).

## Time window

| | from | to | content |
|---|---|---|---|
| gen | 2022-01-01 | 2024-12-31 | creates the phenomena |
| update 2025 | 2025-01-01 | 2025-12-31 | appends the 2025 rows to the existing phenomena |

Nothing before 2022-01-01 survives anywhere (D1). The window is applied in step 2 on every dataset (before the heavy
computations, so that e.g. 2025 days do not enter the base build), and a last
time in step 3 on the final phenomena. Yearly data are kept by year, daily data by date.

## Step 0 – Download

Raw files are copied exactly as they are from the data lake (or from `update.local_source_dir`) to `raw_data/`;
the json mappings and the geojson of the areas go to `mapping/`. **A file already present (non-empty) in `raw_data/`
or `mapping/` is never downloaded again** (checked file by file in the base build and in the update, D6);
`--force-download` downloads everything again. The base build downloads: popolazione 2020–2024,
strutture (Annuario csv + 2024 ods), Vodafone presences (`vodafone_attendences` + `_new`, A1), Vodafone OD co-visits,
the ISPAT arrivals / presences 2022–2024 (A2), the energy category files and the two energy total files
`Energia/ee_prelievi/totale_ee.csv` / `Energia/gas_prelievi/totale_gas.csv` (A11; they are in the folders of the category files, also in `raw_data/`). The update downloads the files listed in its
yaml (`config/updates/update_2025.yaml`). Energy files keep their folder (`ee_prelievi/`, `gas_prelievi/`) because the
two carriers have identically named files.

## Step 1 – Standardization (`<dataset>_std`)

Uniform names and format, **no filtering and no aggregation**: columns `DATA` / `LOCATION`, comune names cleaned,
Vodafone area ids converted to names (Vigo + Pozza di Fassa → San Giovanni di Fassa), energy categories stacked
(`ee_prelievi`, `gas_prelievi`; the total files `ee_totale`, `gas_totale` are read one by one),
OD co-visits reduced to what the indicators use (area level, TOURIST / VISITOR, total over the countries; read in chunks).
In the update every source first goes through its **adapter**, which checks the layout (a mismatch stops the run)
and renames the columns to the standard ones; then the same standardization functions of the base build are applied.
The ISPAT arrivals / presences are not normalized (only their layout is checked).

## Step 2 – Processing (`<dataset>_pr`, `<dataset>_update_pr`)

The update calls the **same functions** as the base build, so a `_update_pr` has exactly the format of its `_pr`.
Every output has `DATA` and `ID_COMUNE` (6 digits, one comune per row) plus the value columns.

| dataset | granularity out | how |
|---|---|---|
| popolazione | comune × year | resident population at 1 January |
| strutture | comune × year | beds and structures, conventional (alb + extralb) and not; totals recomputed (A5) |
| vodafone | comune × day | TOURIST and VISITOR presences kept separately per area × day; areas with several comuni split by beds of the year (A7); sums checked after the split |
| presenze_alb / presenze_extralb | comune × day | ISPAT monthly arrivals and presences per APT / province → daily presences through the average length of stay (A8), then split among comuni by `alberghieri` / `extra alb.` beds; each month adds up exactly to the official figure |
| ee_prelievi / gas_prelievi | comune × day | categories summed per comune-month, spread evenly over the days (A9); column `ee_services` / `gas_services` |
| ee_totale / gas_totale | comune × day | total files: same treatment (A9, A11); column `ee_total` / `gas_total` |
| vodafone_provenienza | comune × year | normalized HHI of the TOURIST presences by country of origin, per area × year, then areas → comuni (A12); derived from the standardized Vodafone presences |
| vodafone_covisits | comune × year | flow indicators: share of incoming and outgoing users, share of intra-ambito flow, PageRank, for TOURIST, VISITOR and a weighted `_combined`; `giorni_coperti` = days with data (A10) |

Presences and beds: for a day, the beds of its year are used; if the year is missing the nearest one (with a warning).
With the window of D2 the base build never needs 2025 beds; the update processes the 2025 strutture first and uses them
for the 2025 Vodafone presences (U5).

**Profile weights (flussi OD).** The `_combined` indicators merge TOURIST and VISITOR with fixed weights
(`COVISITS_PROFILE_WEIGHTS` in `utils/datasets.py`: TOURIST 1, VISITOR 0.5). No energy / gas based estimation.
An area that covers several comuni passes its indicators to all of them.

**Update specifics.** The update only processes the rows of its window: `process_update_std_data` receives the window
and passes it to every processor. The co-visit indicators of a year need all its days, so the base standardized
data of the same year (none for 2025) and the update parts are stacked (the later file wins on a duplicated date) and cut
to the year of the update.

## Step 3 – Phenomena (`final_data/phen_*`)

| phenomenon | built from | rule |
|---|---|---|
| `phen_popolazione` | popolazione | as is |
| `phen_strutture` | strutture | as is |
| `phen_presenze` | vodafone, presenze_alb, presenze_extralb | **inner join** on DATA + ID_COMUNE; the dropped records (e.g. days not covered by Vodafone) are counted in warnings |
| `phen_consumption` | ee_prelievi, gas_prelievi, ee_totale, gas_totale | outer join on DATA + ID_COMUNE; columns `DATA, ID_COMUNE, ee_services, ee_total, gas_services, gas_total` |
| `phen_flussi_od` | vodafone_covisits | as is |
| `phen_provenienza` | vodafone_provenienza | as is: `DATA` (year), `ID_COMUNE`, `hhi_provenienza`, `giorni_coperti` |

* **gen**: the phenomena are created from the `_pr` files and cut to 2022-01-01 .. 2024-12-31.
* **update**: a phenomenon is recomputed only if **all** its input datasets are in the update (the datasets enabled in
  the 2025 yaml; the four energy ones are currently disabled, so `phen_consumption` is not appended, see U1); the new rows are appended to the existing file (the update wins on a duplicated key, D5), and the
  result is cut to `period.start` .. end of the update window. `--upload` also logs the phenomena to the platform.

How each value is obtained, phenomenon by phenomenon, is in [ASSUMPTIONS.md](ASSUMPTIONS.md#how-each-phenomenon-is-computed).

## Running

```
python -m gen_phenomenon_dataframes [--with-update | --update-only] [--skip-download] [--force-download] [--upload]
python -m update_phenomenon_dataframes --config config/updates/update_2025.yaml [--skip-download] [--force-download] [--upload]
```

`--with-update` runs the base build and then the 2025 update; `--update-only` runs only the 2025 update.
Run from `territorial_indexes/`. Run gen first (same `Output/`, same `type_format`), then the update. To move the window edit `period` in
`config/settings.yaml` (or add `period: {start, end}` to the update yaml); to update a new year write a new yaml.
Tests: `python -m pytest tests` (from `territorial_indexes/`).
