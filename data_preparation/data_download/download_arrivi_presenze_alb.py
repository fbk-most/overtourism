import io, time
from pathlib import Path
import pandas as pd
import requests

BASE = "https://statweb.provincia.tn.it/movturistico/data.asp"
YEARS = range(2022, 2026)  # 2022-2025
SAVE_DIR = Path("Download")
SAVE_DIR.mkdir(parents=True, exist_ok=True)


def fetch_tables(year, var=0):
    r = requests.get(
        BASE,
        params={
            "db": "annuarioturismo",
            "sp": "spArrPresEsAlbXAmbProvMes",
            "var": var,
            "a": year,
        },
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    r.raise_for_status()
    tables = pd.read_html(io.StringIO(r.text))
    return [
        t for t in tables if t.shape[1] == 40 and str(t.iloc[0, 0]).strip() == "Mese"
    ]


def to_wide(t):
    ambiti = t.iloc[0, 1:].astype(str).str.strip().tolist()
    prov = t.iloc[1, 1:].astype(str).str.strip().tolist()
    body = t.iloc[2:].reset_index(drop=True)

    out = pd.DataFrame({"mese": body.iloc[:, 0].astype(str).str.strip()})
    for j in range(1, 40):
        col = f"{ambiti[j-1]} - {prov[j-1]}"
        out[col] = pd.to_numeric(
            body.iloc[:, j].astype(str).str.replace(".", "", regex=False),
            errors="coerce",
        ).astype("Int64")
    return out


for year in YEARS:
    try:
        tabs = fetch_tables(year)
        if len(tabs) != 2:
            print(year, f"expected 2 tables, found {len(tabs)}")
            continue
        for misura, t in zip(["arrivi_alb", "presenze_alb"], tabs):
            to_wide(t).to_csv(SAVE_DIR / f"{misura}_{year}.csv", index=False)
        print(year, "ok")
    except Exception as e:
        print(year, "skipped:", e)
    time.sleep(1)
