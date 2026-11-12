import pandas as pd
import pytest

from utils.config import BASE_WINDOW, UPDATE_WINDOW, load_settings
from utils.steps.create_phenomena_df import compute_phenomena
from utils.steps.process_std_data import process_energy
from utils.update.spec import ConfigError, load_config
from utils.window import Window, clip


def test_settings_period():
    assert str(BASE_WINDOW) == "2022-01-01..2024-12-31"
    assert str(UPDATE_WINDOW) == "2025-01-01..2025-12-31"
    assert "period" in load_settings()


def test_clip_yearly_and_daily():
    w = Window(pd.Timestamp("2022-01-01"), pd.Timestamp("2024-12-31"))
    yearly = pd.DataFrame({"DATA": [2020, 2021, 2022, 2024, 2025], "x": range(5)})
    assert clip(yearly, w)["DATA"].tolist() == [2022, 2024]
    as_str = yearly.assign(DATA=yearly["DATA"].astype(str))
    assert clip(as_str, w)["DATA"].tolist() == ["2022", "2024"]
    daily = pd.DataFrame(
        {"DATA": ["2021-12-31", "2022-01-01", "2024-12-31", "2025-01-01", None]}
    )
    assert clip(daily, w)["DATA"].tolist() == ["2022-01-01", "2024-12-31"]


def _energy(years):
    rows = []
    for y in years:
        row = {"DATA": y, "LOCATION": "TRENTO", "codice_utilizzo": 553}
        row.update({m: 31.0 for m in (
            "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
        )})
        rows.append(row)
    return pd.DataFrame(rows)


def test_process_energy_respects_window():
    mapping = {"TRENTO": 22205}
    out = process_energy(_energy([2021, 2022, 2024, 2025]), mapping, "ee_services", "ee", BASE_WINDOW)
    assert out["DATA"].min() == "2022-01-01"
    assert out["DATA"].max() == "2024-12-31"
    upd = process_energy(_energy([2024, 2025]), mapping, "ee_services", "ee", UPDATE_WINDOW)
    assert upd["DATA"].min() == "2025-01-01" and upd["DATA"].max() == "2025-12-31"


def test_update_period_override_never_before_start():
    cfg = {
        "period": {"start": "2020-01-01", "end": "2026-12-31"},
        "datasets": {"popolazione": {"sources": [{"file": "a.csv", "reader": "csv",
                     "adapter": "popolazione_ispat_1jan", "adapter_kwargs": {"year": 2025}}]}},
    }
    w = load_config(cfg).window
    assert str(w) == "2022-01-01..2026-12-31"
    cfg["period"] = {"start": "2026-01-01", "end": "2025-01-01"}
    with pytest.raises(ConfigError):
        load_config(cfg)


def test_compute_phenomena_update_appends_2025_and_drops_before_2022(tmp_path):
    proc, final = tmp_path / "proc", tmp_path / "final"
    proc.mkdir(), final.mkdir()
    pd.DataFrame({"DATA": [2025, 2025], "ID_COMUNE": ["022001", "022002"], "popolazione": [5, 6]}).to_parquet(
        proc / "popolazione_update_pr.parquet"
    )
    pd.DataFrame({"DATA": [2020, 2021, 2022, 2024], "ID_COMUNE": ["022001"] * 4, "popolazione": [1, 2, 3, 4]}).to_parquet(
        final / "phen_popolazione.parquet"
    )
    out = compute_phenomena(proc, final, "parquet", datasets=["popolazione"], window=UPDATE_WINDOW)
    assert sorted(out["phen_popolazione"]["DATA"].unique()) == [2022, 2024, 2025]
