"""Scenari what-if per il modello di overtourism di Fazzon (Lago dei Caprioli, Val di Sole).

Ogni :class:`WhatIfScenario` porta un'etichetta di visualizzazione, una descrizione
(tabella Markdown mostrata sotto la figura del campo) e una ``overrides_fn`` che mappa
da un'istanza live di :class:`FazzonModel` a un dict di override compatibile con Scenario.

Utilizzo::

    from overtourism.model.fazzon.fazzon_scenarios import SCENARIO_BY_KEY
    scenario_def = SCENARIO_BY_KEY["a1_no_cap"]
    overrides = scenario_def.overrides_fn(model)
    scenario = Scenario(model, overrides=overrides)

Per aggiungere un nuovo scenario: definire una costante :class:`WhatIfScenario` e aggiungerla
a :data:`ALL_SCENARIOS`.  La dashboard recepisce la modifica automaticamente.
"""

# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from scipy import stats

if TYPE_CHECKING:
    from overtourism.model.fazzon.fazzon_model import FazzonModel

# ---------------------------------------------------------------------------
# Data type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WhatIfScenario:
    """Scenario what-if con overrides dei parametri per il modello di Fazzon."""

    key: str
    label: str
    category: str
    description: str
    overrides_fn: Callable[[FazzonModel], dict] = field(
        default=lambda m: {}, compare=False, hash=False
    )


# ---------------------------------------------------------------------------
# Distribution helpers (return frozen scipy distributions)
# ---------------------------------------------------------------------------


def _triang(loc: float, scale: float, c: float):
    return stats.triang(c=c, loc=loc, scale=scale)


def _uniform(loc: float, scale: float):
    return stats.uniform(loc=loc, scale=scale)


# ---------------------------------------------------------------------------
# Riferimento — As-Is (2025 stagione regolata)
# ---------------------------------------------------------------------------

AS_IS = WhatIfScenario(
    key="as_is",
    label="As-is (2025 regolato)",
    category="Riferimento",
    description=(
        "Nessun intervento.  I parametri riflettono la stagione 2025 regolata: "
        "parcheggio contingentato, navetta non ancora operativa a regime, "
        "quota modale auto calibrata dal dato EETRA 2022 (69 %)."
    ),
)

# ---------------------------------------------------------------------------
# Categoria A — Capacità di parcheggio
#
# La variabile di indice i_c_parking rappresenta il numero massimo di auto
# in parcheggio simultaneo (non giornaliero).  I valori di riferimento
# riflettono il contingentamento 2025 (≈200 auto simultanee).
# ---------------------------------------------------------------------------

A1_NO_CAP = WhatIfScenario(
    key="a1_no_cap",
    label="A1 – Senza cap (baseline storico 2022)",
    category="A — Capacità",
    description=(
        "Scenario pre-intervento 2022: il contingentamento non è ancora in vigore. "
        "La capacità di parcheggio simultaneo sale a 400 auto (stima del massimo "
        "storico prima della regolamentazione).\n\n"
        "| Parametro | Riferimento (2025) | Scenario |\n"
        "| --- | --- | --- |\n"
        "| cap parcheggio simultaneo | triang, moda 200, range [150, 250] auto"
        " | **triang, moda 400, range [350, 450] auto** |"
    ),
    overrides_fn=lambda m: {
        m.i_c_parking: _triang(loc=350.0, scale=100.0, c=0.5),
    },
)

A2_REDUCED_CAP = WhatIfScenario(
    key="a2_reduced_cap",
    label="A2 – Cap ridotto (100 auto simultanee)",
    category="A — Capacità",
    description=(
        "Inasprimento del contingentamento: il numero massimo di auto in parcheggio "
        "simultaneo scende a 100.  Questo scenario testa la resilienza del sistema "
        "a una riduzione ulteriore dell'accesso motorizzato.\n\n"
        "| Parametro | Riferimento (2025) | Scenario |\n"
        "| --- | --- | --- |\n"
        "| cap parcheggio simultaneo | triang, moda 200, range [150, 250] auto"
        " | **triang, moda 100, range [80, 120] auto** |"
    ),
    overrides_fn=lambda m: {
        m.i_c_parking: _triang(loc=80.0, scale=40.0, c=0.5),
    },
)

# ---------------------------------------------------------------------------
# Categoria B — Navetta
#
# La variabile i_shuttle_daily_trips rappresenta il numero di viaggi
# navetta giornalieri (andata + ritorno).  Il riferimento AS_IS è 0
# (nessuna navetta strutturata nella stagione 2025).
# La variabile i_car_mode_share è la quota modale auto sul totale dei
# visitatori giornalieri; valore di riferimento 0.69 (= 1 − 0.31, EETRA 2022).
# ---------------------------------------------------------------------------

B1_SHUTTLE_FULL = WhatIfScenario(
    key="b1_shuttle_full",
    label="B1 – Navetta stagionale (lug–ago)",
    category="B — Navetta",
    description=(
        "Attivazione della navetta per l'intera stagione alta (luglio–agosto): "
        "2 bus × 8 corse A/R al giorno = 32 viaggi giornalieri.  La navetta "
        "sostituisce parte dei movimenti in auto riducendo la pressione sul parcheggio.\n\n"
        "| Parametro | Riferimento (2025) | Scenario |\n"
        "| --- | --- | --- |\n"
        "| viaggi navetta giornalieri | 0 (nessuna navetta) | **32** (2 bus × 8 A/R) |\n"
        "| quota modale auto | 0.69 (EETRA 2022) | invariata (shift implicito via domanda) |"
    ),
    overrides_fn=lambda m: {
        m.i_shuttle_daily_trips: 32,
    },
)

B2_SHUTTLE_VALLEY = WhatIfScenario(
    key="b2_shuttle_valley",
    label="B2 – Navetta + fondovalle (integrazione valle)",
    category="B — Navetta",
    description=(
        "Navetta potenziata con integrazione fondovalle (Ossana, Mezzana, Vermiglio): "
        "48 viaggi giornalieri totali.  La connessione con il fondovalle riduce "
        "strutturalmente la quota modale auto al 55 %.\n\n"
        "| Parametro | Riferimento (2025) | Scenario |\n"
        "| --- | --- | --- |\n"
        "| viaggi navetta giornalieri | 0 | **48** (navetta + fondovalle) |\n"
        "| quota modale auto | 0.69 | **0.55** (−14 pp, shift modale valle) |"
    ),
    overrides_fn=lambda m: {
        m.i_shuttle_daily_trips: 48,
        m.i_car_mode_share: 0.55,
    },
)

# ---------------------------------------------------------------------------
# Categoria C — Pacchetti di misure (combinazioni di A e B)
# ---------------------------------------------------------------------------

C1_PIANO_2026 = WhatIfScenario(
    key="c1_piano_2026",
    label="C1 – Piano di Mobilità 2026 (tariffa €20 + navetta)",
    category="C — Pacchetti",
    description=(
        "Scenario combinato del Piano di Mobilità 2026: tariffa di parcheggio "
        "€20 (si stima riduca la domanda auto del ~15 % rispetto al 2025) più "
        "navetta stagionale.  L'effetto tariffario è modellato come riduzione "
        "della quota modale auto al 60 %; la navetta opera a 32 viaggi/giorno.\n\n"
        "| Parametro | Riferimento (2025) | Scenario |\n"
        "| --- | --- | --- |\n"
        "| quota modale auto | 0.69 | **0.60** (tariffa €20, −9 pp stimati) |\n"
        "| viaggi navetta giornalieri | 0 | **32** (2 bus × 8 A/R) |\n"
        "| cap parcheggio simultaneo | triang, moda 200, range [150, 250] | invariato |"
    ),
    overrides_fn=lambda m: {
        m.i_car_mode_share: 0.60,
        m.i_shuttle_daily_trips: 32,
    },
)

C2_STRONG = WhatIfScenario(
    key="c2_strong",
    label="C2 – Intervento forte (cap 80 + navetta + fondovalle)",
    category="C — Pacchetti",
    description=(
        "Scenario di massima restrizione: contingentamento a 80 auto simultanee "
        "(A2 inasprito) combinato con navetta integrata al fondovalle (B2).  "
        "La quota modale auto scende al 50 % per effetto combinato.\n\n"
        "| Parametro | Riferimento (2025) | Scenario |\n"
        "| --- | --- | --- |\n"
        "| cap parcheggio simultaneo | triang, moda 200, range [150, 250] auto"
        " | **triang, moda 80, range [60, 100] auto** |\n"
        "| quota modale auto | 0.69 | **0.50** (cap + shift modale valle) |\n"
        "| viaggi navetta giornalieri | 0 | **48** (navetta + fondovalle) |"
    ),
    overrides_fn=lambda m: {
        m.i_c_parking: _triang(loc=60.0, scale=40.0, c=0.5),
        m.i_car_mode_share: 0.50,
        m.i_shuttle_daily_trips: 48,
    },
)

# ---------------------------------------------------------------------------
# Catalogo ordinato — la dashboard itera questa lista per costruire il menu
# ---------------------------------------------------------------------------

ALL_SCENARIOS: list[WhatIfScenario] = [
    AS_IS,
    A1_NO_CAP,
    A2_REDUCED_CAP,
    B1_SHUTTLE_FULL,
    B2_SHUTTLE_VALLEY,
    C1_PIANO_2026,
    C2_STRONG,
]

SCENARIO_BY_KEY: dict[str, WhatIfScenario] = {s.key: s for s in ALL_SCENARIOS}
