# Territorial indexes (gen / update of the phenomena): decisions and assumptions

Register of the decisions (`D*`) and assumptions (`A*`) of the pipeline that builds the phenomenon dataframes:
`gen_phenomenon_dataframes.py` (base build, "gen") and `update_phenomenon_dataframes.py` (yearly update).
The steps are described in [METHODOLOGY.md](METHODOLOGY.md); **how each phenomenon is computed** is in the section
[How each phenomenon is computed](#how-each-phenomenon-is-computed). Where a value is configurable the file is named.

Status: **in use** · **to verify** (written without being able to check it against the real files / data lake: confirm
it before trusting the 2025 numbers) · **retired**.

## Time window

| ID | Decision | Reason / effect | Where | Status |
|----|----------|-----------------|-------|--------|
| D1 | **Nothing before 01/01/2022 is kept**, in the base build and in the update. | Earlier years are discarded (the older strutture were also not comparable, municipal mergers). Applied in step 2 (processing) and again on the final phenomena, so an old `final_data` file cannot bring older rows back. | `config/settings.yaml` `period.start`; `utils/window.py`; `process_std_data.py`; `create_phenomena_df.py` | in use |
| D2 | **gen (base build) uses data up to 31/12/2024** (included). | Whatever the raw files contain after that date (2025 days of the Vodafone files, 2025 energy, ...) is ignored by the base build and is left to the update. This also removes the warning `[beds_weights] no strutture for 2025: using 2024`: the base build no longer processes 2025 days that have no 2025 strutture. | `period.base_end` | in use |
| D3 | **update covers 2025 only**: popolazione, strutture, presenze (Vodafone + ISPAT alb + ISPAT extralb), flussi OD and, when its four datasets (`ee_prelievi`, `gas_prelievi`, `ee_totale`, `gas_totale`) are enabled in the update yaml, consumption. In `update_2025.yaml` the energy datasets are `enabled: false` for now (U1). | The processed update files and the rows appended to the base phenomena only contain 2025. Rows of other periods in the update files (e.g. Vodafone 2023–2024, in the same csv) are ignored. An update that finds no data in its window stops with an error (instead of silently appending nothing). | `period.update_start/update_end`; optional `period: {start, end}` in the update yaml (never before `period.start`) | in use |
| D4 | Yearly data (DATA = `YYYY`: popolazione, strutture, flussi OD) are kept if their **year** is inside the window; daily data by exact date, both ends included. | Window boundaries are whole years in the current settings; with a boundary inside a year a yearly row of that year is kept. | `utils/window.py` | in use |
| D5 | The update **replaces** rows with the same DATA + ID_COMUNE and **appends** the new ones to the existing phenomena; the earlier rows (2022–2024) are untouched. | Reruns of the update are idempotent. | `create_phenomena_df.append_to_existing` | in use |
| D6 | **Downloads are never repeated**: step 0 (base build and update, raw files and mappings) skips every object that is already in `raw_data/` / `mapping/` as a non-empty file with the same name. `--force-download` (or `force=True`) overrides it; `--skip-download` skips the whole step. | Avoids downloading again the big files (Vodafone, co-visits) that the base build and the update share (e.g. `vodafone_attendences_new.csv`). A partially written or outdated file is not detected: delete it or use `--force-download`. | `download_data.already_downloaded` | in use |
| D7 | **gen can also run the 2025 update**: `--with-update` (base build, then the update with `config/updates/update_2025.yaml`) and `--update-only` (only the update, the base build must exist). | One entry point for the full 2022–2025 refresh. The update is the same code and yaml of `update_phenomenon_dataframes.py`, with the same download check (D6). | `gen_phenomenon_dataframes.py` | in use |

## Base build (gen)

| ID | Assumption | Evidence / reason | Where | Status |
|----|------------|-------------------|-------|--------|
| A1 | Vodafone presences of 2024-04-01 .. 2024-12-31 come from `vodafone_attendences_new.csv` (2023-01-01 .. 2025-12-31). The base build reads it together with `vodafone_attendences` (2022-01-01 .. 2024-03-31); on the dates present in both files **the newer file wins**. | `vodafone_attendences` stops at 2024-03-31, so without it the base would end in March 2024 (the final presences are an inner join of Vodafone and ISPAT) . The two files are identical on 2023 (Molveno ASSUMPTIONS D8). The file is added to the base download list. | `standardize_raw_data.read_base_vodafone`; `download_data.S3_DATA` | to verify |
| A2 | ISPAT arrivals / presences (alb and extralb) are read for **every year of the window** (2022, 2023, 2024): `Presenze/<arrivi\|presenze>_<alb\|exalb>_<year>.csv`. | `PRESENZE_BASE_YEARS` is derived from the window. The 2024 files were in the former update (`update_2025.yaml`); they are now downloaded by the base build. | `datasets.PRESENZE_BASE_YEARS` | to verify |
| A3 | The 2022 stays that cross the 2021/2022 boundary are approximated (no 2021 files, warning). | Spill-over of the stays uses the previous year's files when present. | `process_presenze_stay` | in use |
| A4 | Popolazione of year Y is the resident population at 1 January of Y. | `popolazione_ispat_1jan` | `adapters/popolazione.py` | in use |
| A5 | Strutture: CONV = alberghieri + extralberghieri; the totals are recomputed from the components, not read from the raw totals: `tot_strutture` / `tot_postiletto` = alberghieri + extralberghieri + alloggi privati (`all. privati`, the "alloggi turistici"). The `all. disposizione` are kept in their own columns (`strutture_alloggi_disp`, `letti_alloggi_disp`) and are **not** in the totals. | Consistency between years / layouts. | `process_strutture` | in use |
| A6 | Vodafone presences: `TOURIST`, `VISITOR` and `INHABITANT`, `locType = TN_MKT_AL_3` rows; `VIGO DI FASSA` and `POZZA DI FASSA` are unified in `SAN GIOVANNI DI FASSA` (22250). | The comune of Fassa is a merger; the three profiles are kept in separate columns. | `standardize_vodafone_columns`, `process_vodafone` | in use |
| A7 | An area that covers several comuni is split **proportionally to the beds** (`tot_postiletto`) of the year for all three Vodafone profiles; ISPAT alb / extralb are split by `alberghieri` / `extra alb.` beds. Without beds of the year, the nearest year is used (earlier on a tie, warning); without beds at all, uniform split. | Beds are a supply proxy appropriate to tourists and visitors; using them for `INHABITANT` is the current implementation and should be validated against a population-weighted split. Largest-remainder rounding preserves each profile's area total. | `disaggregation.beds_weights` | review for INHABITANT |
| A8 | ISPAT presences: the monthly arrivals are spread uniformly over the days of the month; a guest who arrives on day d stays `s = presences / arrivals` nights (also across the end of the month); each month is then rescaled to the official monthly presences. | A uniform spread of the presences would ignore the length of stay. | `stay_distribution.py`, `PRESENZE_SPILL_OVER` | in use |
| A9 | Energy (`ee_services`, `gas_services`, `ee_total`, `gas_total`): all the rows of a comune-month (usage categories `codice_utilizzo`) are summed, then divided **evenly over the calendar days** of the month (leap days included). Comuni without an ID are dropped (warning). Same function for the four measures. | Only monthly data are available. | `process_energy` | in use |
| A10 | Flussi OD: only area-level rows (`TN_MKT_AL_3`), profiles TOURIST and VISITOR, total over the countries (`userCountry` empty). Indicators are yearly per comune; `_combined` columns merge the profiles with **fixed weights, TOURIST 1 and VISITOR 0.5**. An area covering several comuni gives its value to each of them. | Simple and transparent; same weights in base build and update, so years are comparable. 0.5 is a chosen coefficient, not estimated. | `datasets.COVISITS_PROFILE_WEIGHTS`, `flows.build_area_comune`, `process_covisits` | in use |

| A11 | **Energy totals**: `Energia/ee_prelievi/totale_ee.csv` and `Energia/gas_prelievi/totale_gas.csv` (data-lake objects in the folders of the category files, copied to `raw_data/ee_prelievi/` and `raw_data/gas_prelievi/`; the category folders are read **excluding** these two files, otherwise they would be summed into `*_services`) feed the columns `ee_total` and `gas_total`. They are assumed to have the layout of the category files (semicolon csv, `anno`, `comune`, one column per month); the `codice_utilizzo` column is optional (if missing it is filled with `TOTALE`) and **one row per comune and year is assumed**: if a file also contained the single categories next to a grand total, summing the rows (A9) would double count. Units are not converted (as for the services files). A comune/year absent from a file gives an empty value in its column (outer join). | The two files were delivered without a specification and were not available while implementing: the reader accepts both layouts, the content must be checked on the real files. | `standardize_raw_data.read_energy_category`, `standardize_energy_total`, `datasets.ENERGY_TOTAL_FILES` | **to verify** |

| A12 | **Provenienza** (`phen_provenienza`): per Vodafone area and year, `hhi = (H − 1/N)/(1 − 1/N)` with `H = Σ s_c²`, `s_c` = share of country c in the yearly TOURIST user-days (sum of the daily presences), `N` = countries with presences > 0 (`N = 1` → 1). Only `userProfile = TOURIST`, `locType = TN_MKT_AL_3`; rows without `userCountry` are ignored; Italy (`ITA`) is one market. Empty where the area has < 100 user-days in the year (`PROVENIENZA_MIN_PRESENZE`). An area is **not split** among its comuni (the HHI is not additive): it passes its value to all of them, a comune with several areas gets the mean weighted by the areas' user-days. `giorni_coperti` = days with data in the year; < 360 → partial year (warning). | Vodafone hides counts below a privacy threshold (smallest non-zero value in the sample: 15), so the shares cover only the visible part of the presences and small areas are biased upwards: hence the threshold, and the index must be read as the concentration of the *observed* markets. 100 is a chosen value, not estimated. | `utils/provenienza.py`, `process_std_data.process_provenienza`, `datasets.PROVENIENZA_*` | **to verify** |

## Update (2025)

| ID | Assumption | Evidence / reason | Where | Status |
|----|------------|-------------------|-------|--------|
| U1 | **Energy 2025**: the files of the update have the same layout as the base ones (semicolon csv, year × comune × usage category, one column per month) and are the objects `Energia/<ee_prelievi\|gas_prelievi>/{49_3,55_1,56_1,93_1,96}.csv` plus `totale_ee.csv` / `totale_gas.csv` (A11); the 2025 rows are read from them (same names as the base files). The four datasets are **disabled** in `update_2025.yaml` (`enabled: false`), and `phen_consumption` needs all four: enable them together once the 2025 rows are confirmed. | The format of the energy update was undefined (placeholder adapter). If the 2025 data arrive in other files, edit the `sources` of `ee_prelievi` / `gas_prelievi` in `config/updates/update_2025.yaml`. | `adapters/energia.py` (`energia_categorie`), `sources.read_energy_csv` | **to verify** |
| U2 | **Flussi OD 2025**: the 2025 co-visits are in the object `vodafone_covisits.csv` (the same of the base build), read in chunks and filtered to the update period. | The update yaml had no co-visits source. If a separate file is delivered, change `file` in `update_2025.yaml`. | `sources.read_covisits_csv` | **to verify** |
| U3 | The yearly flow indicators of 2025 are computed on all the 2025 days (base std data of earlier years are not touched); the same fixed profile weights (A10) are used. A partial year (< 360 days) is flagged by `giorni_coperti` and a warning. | Comparability across years. | `process_update_std_data._process_covisits` | in use |
| U4 | **Presenze 2025**: only the 2025 ISPAT files are in the update yaml; the 2024 files (downloaded by the base build in the same `raw_data` folder) give the stays that cross the new year. If they are missing the stays crossing 31/12/2024 are approximated (warning). | The 2024 sources moved to the base build (A2). | `_process_presenze` | in use |
| U5 | **Vodafone 2025** is in `vodafone_attendences_new.csv`; areas are split with the 2025 beds (the 2025 strutture are processed first in the same update). | If `strutture` is not part of the update, the 2025 beds are missing and the 2024 beds are used (this is the origin of the old warning). Keep `strutture` enabled. | `process_update_std_data` | in use |
| U6 | Popolazione and strutture of 2025 keep their files and adapters (`popolazione_2026_ISPAT.csv`, `numero_strutture_ISPAT_2025.xlsx`). | unchanged | `update_2025.yaml` | in use |
| U8 | **Provenienza 2025**: `vodafone_provenienza` reads `vodafone_attendences_new.csv` (same file of `vodafone`, downloaded once, D6) and must contain **all the days of the year**: the yearly index is computed on the update data only (the base days of the same year are not stacked as for the co-visits). With a partial file the year is flagged by `giorni_coperti` and a warning. | Unlike the OD co-visits, the base `vodafone_std` also holds the 2025 days of the newer file, so stacking would double count. | `process_update_std_data`, `update_2025.yaml` | in use |
| U7 | The base build must have been run (in the same `Output/` folder, same `type_format`) before the update. | The update appends to `final_data`, reads the base normalized strutture / co-visits and the 2024 ISPAT files. | `update_phenomenon_dataframes.py` | in use |

## How each phenomenon is computed

Every final file (`Output/data/final_data/phen_*`) has `DATA` and `ID_COMUNE` (6 digits, zero-padded ISTAT code) plus the
value columns below. The window of D1–D4 is applied everywhere. "Where" is the function in `utils/steps/process_std_data.py`
(`create_phenomena_df.py` for the joins).

### `phen_popolazione` (comune × year)
* **Source**: ISPAT resident population, file `popolazione_2020_2024.parquet` (base) / `popolazione_2026_ISPAT.csv` (update 2025).
* **Computation**: `popolazione` = resident population **at 1 January of the year** (A4). The comune name is resolved to its
  ISTAT id with `mapping_comuni`; rows of the provincia are removed. Nothing is aggregated or disaggregated.
* **Window**: kept if the year is inside the window (D4). Where: `process_popolazione`.

### `phen_strutture` (comune × year)
* **Source**: ISPAT accommodation statistics: `Annuario-TavXIII-per-comune-csv.csv` + `strutture_annuario_2024.ods` (base),
  `numero_strutture_ISPAT_2025.xlsx` (update).
* **Computation**: for each comune and year, number of structures (`strutture_*`) and beds (`letti_*`) of four types:
  alberghieri (`alb`), extralberghieri (`exalb`), alloggi privati / turistici, alloggi a disposizione (`disp`).
  `tot_strutture` = alb + exalb + alloggi turistici and `tot_postiletto` = letti_alb + letti_exalb + letti_alloggi_turistici (A5);
  the `disp` types are not summed in. The totals of the raw files are discarded and recomputed. `-` is read as 0.
* **Use**: its beds are the weights of the spatial splits of the presences (A7). Where: `process_strutture`.

### `phen_presenze` (comune × day)
The final file has three Vodafone profile columns plus `presenze_alb` and `presenze_xalb`, joined with an **inner join** on DATA + ID_COMUNE (dropped keys are counted in warnings, so only dates and comuni present in all three input datasets are retained).
* **`vodafone_tourists_presences`**, **`vodafone_visitors_presences`** and **`vodafone_inhabitant_presences`** — Vodafone daily presences by profile, level `TN_MKT_AL_3` (A6), per Vodafone area
  (base: `vodafone_attendences` + `vodafone_attendences_new`, the newer wins on common dates, A1). Vigo di Fassa and
  Pozza di Fassa are unified in San Giovanni di Fassa. An area that is one comune is unchanged; an area with several comuni is
  **split proportionally to the `tot_postiletto` of the year** of the day (or the nearest year, A7), with the largest-remainder
  rounding so that the integer sum of each profile's area-day is preserved; sums are checked and a mismatch stops the run.
  Where: `process_vodafone`, `disaggregation.disaggregate`.
* **`presenze_alb`** and **`presenze_xalb`** — ISPAT monthly arrivals and presences of the hotels (alb, per APT, columns
  `<APT> - Totale`) and of the extra-hotels (exalb, province total), files `Presenze/<arrivi|presenze>_<alb|exalb>_<year>.csv`.
  1) average stay of the month `s = presences / arrivals`; 2) the arrivals of the month are spread uniformly over its days;
  3) each arrival adds one presence per day for `s` days (the fractional part on the last day), also across the end of the month and of the year
  (the files of the previous year give the stays that cross 31/12; if absent they are approximated, A3);
  4) the daily values of each month are rescaled and rounded (largest remainder) so that they add up exactly to the official monthly
  presences; 5) the area × day presences are split among the comuni of the area proportionally to the beds of the type
  (`alberghieri posti_letto` for alb, `extra alb. Posti_letto` for exalb; same year or nearest, A7). The arrivals are not in the output (A8).
  Where: `process_presenze_stay`, `utils/stay_distribution.py`.

### `phen_consumption` (comune × day)
Columns `DATA, ID_COMUNE, ee_services, ee_total, gas_services, gas_total`. Four measures, all computed in the same way
(A9) from monthly values per comune; electricity (`ee_*`) in kWh, gas (`gas_*`) in Smc, as in the source files (no conversion).
* **`ee_services`, `gas_services`** — withdrawals of the *services* usage categories, files `Energia/ee_prelievi/*.csv` and
  `Energia/gas_prelievi/*.csv` (one file per category: 49_3, 55_1, 56_1, 93_1, 96, i.e. the ATECO codes 49.3, 55.1, 56.1, 93.1, 96).
  The rows of all the categories of a comune-month are **summed**.
* **`ee_total`, `gas_total`** — withdrawals of all the usages, files `totale_ee.csv` / `totale_gas.csv` (A11): the monthly value of the
  comune (the rows of a comune-month are summed, one is expected).
* **Monthly → daily**: the monthly value of a comune is **divided evenly over the calendar days** of the month
  (`value / days in the month`, leap days included), so the sum of the days gives back the month. There is no daily profile: within a month
  every day has the same value.
* **Join**: the four daily frames are joined with an **outer join** on DATA + ID_COMUNE (a key missing in a measure has an empty value).
  Locations without an ISTAT id are excluded with a warning. Where: `_energy_monthly`, `process_energy`, `compute_consumption`.

### `phen_flussi_od` (comune × year)
* **Source**: Vodafone OD co-visits `vodafone_covisits.csv` (day × source area × target area, `covisitType` ND = users present / UD = users who
  visit both areas). Kept: area level `TN_MKT_AL_3`, profiles TOURIST and VISITOR, `userCountry` empty (total over the countries) (A10).
* **Computation, per year and profile**, on user-days summed over the year, with `T(j)` = users present in area j (ND, source `*`):
  `quota_ingresso` = UD(*→j) / T(j); `quota_uscita` = UD(j→*) / T(j); `quota_intra_ambito` = flow between areas of the same ambito
  / total flow between areas, on the in + out pairs of the area; `pagerank` = PageRank (damping 0.85) of the directed network of the UD flows between
  areas. The two mobility shares are empty where `T < 100` raw user-days (`COVISITS_MIN_T`); they can exceed 1 (a user counted in several areas).
* **Combined profile**: `_combined` columns are computed with the user-days multiplied by the profile weight **before** the indicators
  (TOURIST 1, VISITOR 0.5): share = Σ w·UD / Σ w·T and PageRank on the weighted network (A10).
* **Areas → comuni**: an area that covers several comuni gives its value to **all** of them; a comune with several areas gets the weighted mean
  (weights: T for the two shares, intra-ambito flow for the intra share, in + out flow for the PageRank).
* `giorni_coperti` = days with data in the year; below 360 the year is partial (kept, warning) (U3). Where: `utils/flows.py`, `process_covisits`.

### `phen_provenienza` (comune × year)
* **Source**: Vodafone presences (`vodafone_attendences` + `vodafone_attendences_new.csv`, A1), TOURIST, area level, per day × area × `userCountry`.
* **Computation** (A12): yearly user-days per area and country → shares `s_c` → `H = Σ s_c²` → normalized `hhi_provenienza = (H − 1/N)/(1 − 1/N)`
  (0 = presences evenly spread over the markets, 1 = a single market); empty below 100 user-days. Areas → comuni without splitting: same value
  for every comune of the area, weighted mean over the areas of a comune. Columns `DATA` (year), `ID_COMUNE`, `hhi_provenienza`, `giorni_coperti`.
* **Reading it**: Italy is usually the largest market, so the values are high where the visible presences are few; the counts below the privacy threshold of
  Vodafone are not in the data. Where: `utils/provenienza.py`, `process_provenienza`.

## Not changed / out of scope

* The two model pipelines (`../model/molveno`, `../model/fazzon`) have their own registers and are not covered here.
* The raw files and the data lake were not available while making these changes: the window logic, the energy totals reader / column
  order and the download check are covered by unit tests on synthetic data (`tests/test_period_window.py`,
  `tests/test_energy_totals_and_download.py`, `tests/test_provenienza.py`); the full pipeline has **not** been run on the real data, and `totale_ee.csv` / `totale_gas.csv`
  were not seen (A11).
* After this change `phen_consumption` has two more columns: rerun the base build before any update, otherwise the append stops on the
  column mismatch.
