import pandas as pd
import pytest

from utils.steps.create_phenomena_df import compute_presenze_trentino
from utils.steps.process_std_data import process_vodafone


@pytest.fixture
def vodafone_inputs():
    vodafone = pd.DataFrame(
        {
            "DATA": ["2024-07-01"] * 4,
            "LOCATION": ["AREA CONDIVISA"] * 4,
            "locType": ["TN_MKT_AL_3", "TN_MKT_AL_3", "TN_MKT_AL_3", "AL_2"],
            "userProfile": ["TOURIST", "VISITOR", "COMMUTER", "TOURIST"],
            "presenze": [100, 80, 900, 500],
        }
    )
    strutture = pd.DataFrame(
        {
            "DATA": [2024, 2024],
            "ID_COMUNE": ["022001", "022002"],
            "tot_postiletto": [3, 1],
        }
    )
    popolazione = pd.DataFrame(
        {
            "DATA": [2024, 2024],
            "ID_COMUNE": ["022001", "022002"],
            "popolazione": [1, 3],
        }
    )
    return vodafone, strutture, popolazione


def test_process_vodafone_uses_beds_for_tourists_and_population_for_visitors(
    vodafone_inputs,
):
    vodafone, strutture, popolazione = vodafone_inputs

    out = process_vodafone(
        vodafone,
        {"AREA CONDIVISA": [22001, 22002]},
        strutture,
        popolazione=popolazione,
    ).sort_values("ID_COMUNE")

    assert out["ID_COMUNE"].tolist() == ["022001", "022002"]
    assert out["presenze"].tolist() == [75, 25]
    assert out["presenze_escursionisti_vodafone"].tolist() == [20, 60]


def test_process_vodafone_rejects_missing_shared_area_population(vodafone_inputs):
    vodafone, strutture, popolazione = vodafone_inputs
    popolazione = popolazione.iloc[:1]

    with pytest.raises(ValueError, match="missing positive population"):
        process_vodafone(
            vodafone,
            {"AREA CONDIVISA": [22001, 22002]},
            strutture,
            popolazione=popolazione,
        )


def test_presenze_phenomenon_includes_vodafone_excursionists():
    alb = pd.DataFrame(
        {"DATA": ["2024-07-01"], "ID_COMUNE": ["022001"], "presenze_alb": [10]}
    )
    extralb = pd.DataFrame(
        {"DATA": ["2024-07-01"], "ID_COMUNE": ["022001"], "presenze_xalb": [4]}
    )
    vodafone = pd.DataFrame(
        {
            "DATA": ["2024-07-01"],
            "ID_COMUNE": ["022001"],
            "presenze": [20],
            "presenze_escursionisti_vodafone": [8],
        }
    )

    out = compute_presenze_trentino(alb, extralb, vodafone)

    assert out.loc[0, "presenze_vodafone"] == 20
    assert out.loc[0, "presenze_escursionisti_vodafone"] == 8


def test_process_vodafone_keeps_visitors_of_single_comune_areas():
    """Regression: `presenze_escursionisti_vodafone` was always 0 (derived from `presenze` after it had
    been restricted to TOURIST rows)."""
    vodafone = pd.DataFrame(
        {
            "DATA": ["2024-07-01"] * 3,
            "LOCATION": ["AREA SINGOLA"] * 3,
            "locType": ["TN_MKT_AL_3"] * 3,
            "userProfile": ["TOURIST", "VISITOR", "COMMUTER"],
            "presenze": [100, 80, 900],
        }
    )
    popolazione = pd.DataFrame(
        {"DATA": [2024], "ID_COMUNE": ["022001"], "popolazione": [10]}
    )

    out = process_vodafone(
        vodafone, {"AREA SINGOLA": [22001]}, None, popolazione=popolazione
    )

    assert out["presenze"].tolist() == [100]
    assert out["presenze_escursionisti_vodafone"].tolist() == [80]
