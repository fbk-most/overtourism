import yaml

from utils.config import load_settings
from utils.datasets import DATASETS, PHENOMENA, VODAFONE_VALUE_COLS


def test_dataset_and_phenomenon_names_are_in_yaml():
    settings = load_settings()

    assert "datasets" in settings
    assert "phenomena" in settings
    assert settings["datasets"]["popolazione"]["processed"] == "popolazione_pr"
    assert settings["phenomena"]["phen_presenze"] == [
        "vodafone",
        "presenze_alb",
        "presenze_extralb",
    ]

    assert DATASETS["popolazione"].processed_name == "popolazione_pr"
    assert PHENOMENA["phen_presenze"] == frozenset(
        {
            "vodafone",
            "presenze_alb",
            "presenze_extralb",
        }
    )
    assert VODAFONE_VALUE_COLS == [
        "presenze",
        "presenze_escursionisti_vodafone",
    ]
    assert settings["flows"]["min_comune_coverage"] == 0.5
    assert settings["flows"]["active"] is True


def test_flow_coverage_setting_must_be_between_zero_and_one(tmp_path):
    settings = load_settings()
    settings["flows"]["min_comune_coverage"] = 1.1
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump(settings), encoding="utf-8")

    try:
        load_settings(path)
    except ValueError as exc:
        assert "flows.min_comune_coverage" in str(exc)
    else:
        raise AssertionError("invalid flow coverage threshold was accepted")


def test_flow_coverage_active_setting_must_be_boolean(tmp_path):
    settings = load_settings()
    settings["flows"]["active"] = "yes"
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump(settings), encoding="utf-8")

    try:
        load_settings(path)
    except ValueError as exc:
        assert "flows.active" in str(exc)
    else:
        raise AssertionError("non-boolean coverage setting was accepted")
