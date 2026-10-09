from utils.config import load_settings
from utils.datasets import DATASETS, PHENOMENA


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
