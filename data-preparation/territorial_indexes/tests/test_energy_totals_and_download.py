import io

import pandas as pd

from utils.config import BASE_WINDOW
from utils.steps import download_data
from utils.steps.create_phenomena_df import compute_consumption
from utils.steps.process_std_data import process_energy
from utils.steps.standardize_raw_data import read_energy_category

MONTHS = "gennaio;febbraio;marzo;aprile;maggio;giugno;luglio;agosto;settembre;ottobre;novembre;dicembre"


def _csv(with_code: bool) -> io.BytesIO:
    head = "anno;comune" + (";codice_utilizzo" if with_code else "") + ";" + MONTHS
    row = "2023;Trento" + (";553" if with_code else "") + ";" + ";".join(["31"] * 12)
    return io.BytesIO(f"{head}\n{row}\n".encode())


def test_total_file_without_usage_code_is_read():
    df = read_energy_category(_csv(with_code=False))
    assert df["codice_utilizzo"].tolist() == ["TOTALE"]
    assert df["DATA"].tolist() == [2023]


def test_category_file_with_usage_code_is_unchanged():
    assert read_energy_category(_csv(with_code=True))["codice_utilizzo"].tolist() == [553]


def test_category_file_with_missing_header_field_is_repaired():  # the 96.csv layout
    buf = io.BytesIO(
        ("anno;comune;" + MONTHS + "\n2023;Trento;553;" + ";".join(["31"] * 12) + "\n").encode()
    )
    assert read_energy_category(buf)["codice_utilizzo"].tolist() == [553]


def _daily(col):
    std = read_energy_category(_csv(with_code=False))
    return process_energy(std, {"TRENTO": 22205}, col, col, BASE_WINDOW)


def test_consumption_has_the_four_columns_in_order():
    out = compute_consumption(
        _daily("ee_services"), _daily("gas_services"), _daily("ee_total"), _daily("gas_total")
    )
    assert list(out.columns) == ["DATA", "ID_COMUNE", "ee_services", "ee_total", "gas_services", "gas_total"]
    assert len(out) == 365 and out["ee_total"].iloc[0] == 1.0


def test_download_skips_files_already_in_raw(tmp_path, monkeypatch):
    (tmp_path / "vodafone_attendences_new.csv").write_text("x")
    (tmp_path / "empty.csv").write_text("")
    assert download_data.already_downloaded("vodafone_attendences_new.csv", tmp_path)
    assert not download_data.already_downloaded("vodafone_attendences_new.csv", tmp_path, force=True)
    assert not download_data.already_downloaded("empty.csv", tmp_path)  # an empty file is downloaded again
    assert not download_data.already_downloaded("missing.csv", tmp_path)

    calls = []
    monkeypatch.setattr(download_data, "fetch_bytes", lambda key, **kw: calls.append(key))
    monkeypatch.setattr(download_data, "S3_DATA", ["vodafone_attendences_new.csv", "Energia/ee_prelievi/totale_ee.csv"])
    monkeypatch.setattr(download_data, "download_mappings", lambda *a, **k: None)
    download_data.download_raw_base_data(out_dir=tmp_path)
    assert calls == ["Energia/ee_prelievi/totale_ee.csv"]
    calls.clear()
    download_data.download_raw_base_data(out_dir=tmp_path, force=True)
    assert calls == ["vodafone_attendences_new.csv", "Energia/ee_prelievi/totale_ee.csv"]
