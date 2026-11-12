import pandas as pd

from utils.disaggregation import beds_weights
from utils.steps.process_std_data import process_strutture


def test_process_strutture_computes_totals_used_by_vodafone_weights():
    raw = pd.DataFrame(
        {
            "DATA": [2024, 2024],
            "LOCATION": ["COMUNE UNO", "COMUNE DUE"],
            "alberghieri posti_letto": [10, 20],
            "extra alb. Posti_letto": [2, 3],
            "all. privati posti_letto": [4, 5],
            "all. disposizione posti_letto": [100, 100],
            "alberghieri strutture": [1, 2],
            "extra alb. Strutture": [3, 4],
            "all. privati numero": [5, 6],
            "all.disposizione numero": [100, 100],
        }
    )

    processed = process_strutture(
        raw,
        {"COMUNE UNO": 22001, "COMUNE DUE": 22002},
    )

    assert processed["tot_strutture"].tolist() == [9, 12]
    assert processed["tot_postiletto"].tolist() == [16, 28]

    weights = beds_weights(processed, [2024])
    assert weights["tot_postiletto"].tolist() == [16, 28]
