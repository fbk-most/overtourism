# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import orjson
import numpy as np
import pandas as pd


class OvertourismIndexesLoader:
    _capacity_indices = dict(
        ricettivita=dict(
            dataset="df_tasso_ricettivita",
            title="Indice di ricettività",
            key="ricettivita",
            other=["ricettivita", "popolazione", "posti_letto"],
            alias={
                "anno": "Anno",
                "comune": "Comune",
                "ricettivita": "Ricettività",
                "popolazione": "Popolazione",
                "posti_letto": "Posti letto",
            },
            help="L'indice di ricettività definisce il rapporto fra i letti presenti negli esercizi ricettivi e gli abitanti di una stessa area. L’indice è una misura della capacità turistica rispetto alla dimensione (in termini di popolazione) di un’area. "
            "L'indice è calcolato partendo dai dati ISPAT relativi alla popolazione residente e alla consistenza degli esercizi alberghieri e extra-alberghieri.",
            map=dict(
                geojson="map_comuni", key="properties.com_code", locations_col="ID"
            ),
        ),
        turisticita=dict(
            dataset="df_tasso_turisticita",
            title="Indice di turisticità",
            key="turisticita",
            other=["turisticita", "popolazione"],
            alias={
                "anno": "Anno",
                "comune": "Comune",
                "turisticita": "Turisticità",
                "popolazione": "Popolazione",
            },
            help="L'indice di turisticità definisce il rapporto fra il numero medio giornaliero di turisti negli esercizi ricettivi e gli abitanti di una stessa area. L’indice è una misura dell’effettivo peso del turismo rispetto alla dimensione (in termini di popolazione) di un’area. "
            "L'indice è calcolato partendo dai dati Vodafone per quanto riguarda le presenze turistiche e i dati ISPAT relativi alla popolazione residente.",
            map=dict(
                geojson="map_vodafone", key="properties.name", locations_col="comune"
            ),
        ),
        turisticita_estiva=dict(
            dataset="df_tasso_turisticita_estate",
            title="Indice di turisticità estiva",
            key="turisticita",
            other=["turisticita", "popolazione"],
            alias={
                "anno": "Anno",
                "comune": "Comune",
                "turisticita": "Turisticità",
                "popolazione": "Popolazione",
            },
            help="L'indice di turisticità definisce il rapporto fra il numero medio giornaliero di turisti negli esercizi ricettivi durante il periodo estivo (giugno-settembre) e gli abitanti di una stessa area. L’indice è una misura dell’effettivo peso del turismo rispetto alla dimensione (in termini di popolazione) di un’area. "
            "L'indice è calcolato partendo dai dati Vodafone per quanto riguarda le presenze turistiche e i dati ISPAT relativi alla popolazione residente.",
            map=dict(
                geojson="map_vodafone", key="properties.name", locations_col="comune"
            ),
        ),
        stagionalita=dict(
            dataset="df_stagionalita_presenze",
            title="Indice di stagionalità delle presenze",
            key="stagionalita",
            other=["stagionalita", "nturisti_alta_stagione", "nturisti_bassa_stagione"],
            alias={
                "anno": "Anno",
                "comune": "Comune",
                "stagionalita": "Stagionalità",
                "nturisti_alta_stagione": "Presenze turisti alta stagione",
                "nturisti_bassa_stagione": "Presenze turisti bassa stagione",
            },
            help="L'indice di stagionalità definisce il rapporto fra le presenze di turisti ed escursionisti durante l’alta stagione estiva (luglio-agosto) e le presenze durante un periodo \”di riferimento\” di bassa stagione (ottobre-novembre). "
            "L'indice è calcolato partendo dai dati Vodafone relativi alle presenze di turisti e escursionisti.",
            map=dict(
                geojson="map_vodafone", key="properties.name", locations_col="comune"
            ),
        ),
        variazione_percentuale=dict(
            dataset="df_tasso_variazione_pecentuale",
            title="Tasso di variazione percentuale degli arrivi di turisti",
            key="tasso_variazione_perc",
            other=["tasso_variazione_perc", "anno_2022", "anno_2023", "anno_2024"],
            alias={
                "anno": "Anno",
                "comune": "Ambito",
                "tasso_variazione_perc": "Tasso di variazione percentaule",
                "anno_2022": "Arrivi anno 2022",
                "anno_2023": "Arrivi anno 2023",
                "anno_2024": "Arrivi anno 2024",
            },
            help="L’indice di variazione percentuale degli arrivi di turisti misura il tasso di variazione (in percentuale), nel triennio 2022-2024 di arrivi di turisti nei diversi ambiti turistici trentini. "
            "L’indice è calcolato partendo dai dati ISPAT relativi ai movimenti turistici.",
            map=dict(
                geojson="map_apt",
                key="properties.name",
                locations_col="comune",
            ),
        ),
        strutture_non_convenzionali=dict(
            dataset="df_incidenza_strutture_non_conv",
            title="Indice di incidenza ospitalità non convenzionale (strutture)",
            key="incidenza_strutture_non_conv",
            other=[
                "incidenza_strutture_non_conv",
                "tot_strutture_non_conv",
                "tot_strutture",
            ],
            alias={
                "anno": "Anno",
                "comune": "Comune",
                "incidenza_strutture_non_conv": "Incidenza strutture non conv.",
                "tot_strutture_non_conv": "Numero strutture non conv.",
                "tot_strutture": "Totale strutture",
            },
            help="Questo indice di incidenza ospitalità non convenzionale misura il rapporto fra le strutture ricettive non convenzionali e il totale delle strutture presenti in un’area. "
            "L'indice è calcolato partendo dai dati ISPAT relativi alla consistenza degli esercizi alberghieri e extra-alberghieri.",
            map=dict(
                geojson="map_comuni", key="properties.com_code", locations_col="ID"
            ),
        ),
        postiletto_non_convenzionali=dict(
            dataset="df_incidenza_postiletto_non_conv",
            title="Indice di incidenza ospitalità non convenzionale (posti letto)",
            key="incidenza_postiletto_non_conv",
            other=[
                "incidenza_postiletto_non_conv",
                "tot_postiletto_non_conv",
                "tot_postiletto",
            ],
            alias={
                "anno": "Anno",
                "comune": "Comune",
                "incidenza_postiletto_non_conv": "Incidenza posti letto non conv.",
                "tot_postiletto_non_conv": "Numero posti letto non conv.",
                "tot_postiletto": "Totale posti letto",
            },
            help="Questo indice di incidenza ospitalità non convenzionale misura il rapporto fra il numero di posti letto in strutture ricettive non convenzionali e il numero totale di posti letto in tutte le strutture di un’area. "
            "L'indice è calcolato partendo dai dati ISPAT relativi alla consistenza degli esercizi alberghieri e extra-alberghieri.",
            map=dict(
                geojson="map_comuni", key="properties.com_code", locations_col="ID"
            ),
        ),
    )

    _overtourism_indexes = dict(
        livello_overturismo=dict(
            dataset="df_overturismo",
            title="Livello complessivo di affollamento turistico estivo",
            key="level",
            other=["level", "ricettivita", "turisticita", "stagionalita", "flusso"],
            alias={
                "anno": "Anno",
                "comune": "Comune",
                "level": "Livello complessivo di affollamento",
                "ricettivita": "Livello di ricettività",
                "turisticita": "Livello di turisticità estiva",
                "stagionalita": "Livello di stagionalità",
                "flusso": "Livello del flusso di escursionisti",
            },
            help="L'indice complessivo di affollamento turistico estivo integra e aggrega diversi indici legati all'affollamento turistico (ricettività, turisticità, stagionalità e flusssi di escursionisti). "
            "L'indice complessivo identifica comuni e aree in cui uno o più di questi indici assumono livelli elevanti nel panorama trentino (indicati con un numero crescente di '*').",
            map=dict(
                geojson="map_vodafone_2024",
                key="properties.comune",
                locations_col="comune",
            ),
        ),
    )

    _diffusion_indexes = {}
    for where in ["in", "out"]:
        for when in ["feriali", "prefestivi", "festivi", "sempre"]:
            _diffusion_indexes[f"flusso_{where}_tutti_{when}"] = dict(
                dataset="df_flussi_estate",
                title=f"Flussi totali in {'ingresso' if where == 'in' else 'uscita'} ({'giorni ' + when if when != 'tutti' else 'tutti i giorni'})",
                key=f"level_{where}_tutti_{when}",
                other=[
                    f"level_{where}_tutti_{when}_label",
                    f"flows_{where}_tutti_{when}",
                ],
                alias={
                    "anno": "Anno",
                    "comune": "Comune",
                    f"level_{where}_tutti_{when}": "Livello di densità dei flussi",
                    f"level_{where}_tutti_{when}_label": "Livello di densità flussi",
                    f"flows_{where}_tutti_{when}": "Valore flussi",
                },
                help="L'indice dei flussi descrive diverse misure dei movimenti giornalieri di persone relative alle varie aree. Attraverso la selezione dei parametri: si possono ottenere i flussi giornalieri in entrata o in uscita; si possono selezionare i flussi totali o solo quelli legati agli escursionisti, o il rapporto fra i flussi di escursionisti e i flussi totali; si può infine differenziare fra giorni feriali, prefestivi e festivi. "
                "L’indice definisce, per ogni territorio, un livello di densità dei flussi, dove il LIV_10 rappresenta flussi più intensi. "
                "L'indice è calcolato partendo dai dati Vodafone relativi ai flussi dell’anno 2024.",
                map=dict(
                    geojson="map_vodafone_2024",
                    key="properties.comune",
                    locations_col="comune",
                ),
                ticks=(
                    (1, 2, 3, 4, 5, 6, 7),
                    ("N/A", "LIV_5", "LIV_6", "LIV_7", "LIV_8", "LIV_9", "LIV_10"),
                ),
            )
            _diffusion_indexes[f"flusso_{where}_escursionisti_{when}"] = dict(
                dataset="df_flussi_estate",
                title=f"Flussi di escursionisti in {'ingresso' if where == 'in' else 'uscita'} ({'giorni ' + when if when != 'tutti' else 'tutti i giorni'})",
                key=f"level_{where}_escursionisti_{when}",
                other=[
                    f"level_{where}_escursionisti_{when}_label",
                    f"flows_{where}_escursionisti_{when}",
                ],
                alias={
                    "anno": "Anno",
                    "comune": "Comune",
                    f"level_{where}_escursionisti_{when}": "Livello di densità dei flussi",
                    f"level_{where}_escursionisti_{when}_label": "Livello di densità flussi",
                    f"flows_{where}_escursionisti_{when}": "Valore flussi",
                },
                help="L'indice dei flussi descrive diverse misure dei movimenti giornalieri di persone relative alle varie aree. Attraverso la selezione dei parametri: si possono ottenere i flussi giornalieri in entrata o in uscita; si possono selezionare i flussi totali o solo quelli legati agli escursionisti, o il rapporto fra i flussi di escursionisti e i flussi totali; si può infine differenziare fra giorni feriali, prefestivi e festivi. "
                "L’indice definisce, per ogni territorio, un livello di densità dei flussi, dove il LIV_10 rappresenta flussi più intensi. "
                "L'indice è calcolato partendo dai dati Vodafone relativi ai flussi dell’anno 2024.",
                map=dict(
                    geojson="map_vodafone_2024",
                    key="properties.comune",
                    locations_col="comune",
                ),
                ticks=(
                    (1, 2, 3, 4, 5, 6, 7),
                    ("N/A", "LIV_5", "LIV_6", "LIV_7", "LIV_8", "LIV_9", "LIV_10"),
                ),
            )
            _diffusion_indexes[f"flusso_{where}_rapporto_{when}"] = dict(
                dataset="df_flussi_estate",
                title=f"Rapporto flussi di escursionisti / flussi totali in {'ingresso' if where == 'in' else 'uscita'} ({'giorni ' + when if when != 'tutti' else 'tutti i giorni'})",
                key=f"flows_{where}_ratio_{when}",
                other=[
                    f"flows_{where}_ratio_{when}",
                    f"flows_{where}_tutti_{when}",
                    f"flows_{where}_escursionisti_{when}",
                ],
                alias={
                    "anno": "Anno",
                    "comune": "Comune",
                    f"flows_{where}_ratio_{when}": "Rapporto flussi escursionisti / flussi totali",
                    f"flows_{where}_tutti_{when}": "Valore flussi totali",
                    f"flows_{where}_escursionisti_{when}": "Valore flussi escursionisti",
                },
                help="L'indice dei flussi descrive diverse misure dei movimenti giornalieri di persone relative alle varie aree. Attraverso la selezione dei parametri: si possono ottenere i flussi giornalieri in entrata o in uscita; si possono selezionare i flussi totali o solo quelli legati agli escursionisti, o il rapporto fra i flussi di escursionisti e i flussi totali; si può infine differenziare fra giorni feriali, prefestivi e festivi. "
                "L'indice è calcolato partendo dai dati Vodafone relativi ai flussi dell’anno 2024.",
                map=dict(
                    geojson="map_vodafone_2024",
                    key="properties.comune",
                    locations_col="comune",
                ),
            )

    _redistribution_indexes = dict(
        diffusione_feriale=dict(
            dataset="df_distribuzione_feriale",
            title="Costo di distribuzione dei turisti (giorni feriali)",
            key="value",
            other=["value"],
            alias={
                "anno": "Anno",
                "comune": "Comune",
                "value": "Costo di distribuzione",
            },
            help="L’indice di ridistribuzione misura lo sbilanciamento nei flussi di persone, sbilanciamento che dovrebbe essere riallocato per ridurre il rischio di sovraffollamento in determinate aree. L’indice è positivo per le aree che dovrebbero attrarre più persone, negativo per le aree che dovrebbero ridurre i flussi. Il valore assoluto dell’indice indica l’intensità percentuale della riallocazione dei flussi: più alto il valore assoluto, maggiore la variazione percentuale dello sbilanciamento e della variazione dei flussi prospettata. "
            "Questo indice suggerisce una quantità di investimento (es. in pubblicità) che le varie aree dovrebbero attuare per incentivare i cittadini alla mobilità nelle zone meno a rischio sovraffollamento. "
            "L'indice è calcolato partendo dai dati Vodafone relativi alle presenze dell’anno 2024.",
            map=dict(
                geojson="map_vodafone_2024",
                key="properties.comune",
                locations_col="comune",
            ),
        ),
        diffusione_prefestivo=dict(
            dataset="df_distribuzione_prefestivo",
            title="Costo di distribuzione dei turisti (giorni prefestivi)",
            key="value",
            other=["value"],
            alias={
                "anno": "Anno",
                "comune": "Comune",
                "value": "Costo di distribuzione",
            },
            help="L’indice di ridistribuzione misura lo sbilanciamento nei flussi di persone, sbilanciamento che dovrebbe essere riallocato per ridurre il rischio di sovraffollamento in determinate aree. L’indice è positivo per le aree che dovrebbero attrarre più persone, negativo per le aree che dovrebbero ridurre i flussi. Il valore assoluto dell’indice indica l’intensità percentuale della riallocazione dei flussi: più alto il valore assoluto, maggiore la variazione percentuale dello sbilanciamento e della variazione dei flussi prospettata. "
            "Questo indice suggerisce una quantità di investimento (es. in pubblicità) che le varie aree dovrebbero attuare per incentivare i cittadini alla mobilità nelle zone meno a rischio sovraffollamento. "
            "L'indice è calcolato partendo dai dati Vodafone relativi alle presenze dell’anno 2024.",
            map=dict(
                geojson="map_vodafone_2024",
                key="properties.comune",
                locations_col="comune",
            ),
        ),
        diffusione_festivo=dict(
            dataset="df_distribuzione_festivo",
            title="Costo di distribuzione dei turisti (giorni festivi)",
            key="value",
            other=["value"],
            alias={
                "anno": "Anno",
                "comune": "Comune",
                "value": "Costo di distribuzione",
            },
            help="L'indice dei costi di distribuzione dei turisti (giorni festivi) [...]. L'indice è stato calcolato partendo dai dati [...].",
            map=dict(
                geojson="map_vodafone_2024",
                key="properties.comune",
                locations_col="comune",
            ),
        ),
    )

    _hidden_tourism_indexes = dict(
        livello_turismo_sommerso=dict(
            dataset="df_turismo_sommerso",
            title="Rapporto presenze misurate / presenze ufficiali di turisti",
            key="ratio",
            other=["ratio", "presenze", "presenze_vodafone"],
            alias={
                "anno": "Anno",
                "comune": "Ambito",
                "ratio": "Rapporto presenze misurate / ufficiali",
                "presenze": "Presenze ufficiali",
                "presenze_vodafone": "Presenze misurate",
            },
            help="L'indice misura il rapporto fra le presenze di turisti raccolte attraverso l’analisi di dati da rete di telefonia mobile e le presenze ufficiali di turisti in strutture alberghiere e extra-alberghiere. "
            "L’analisi è a livello di ambito turistico e riguarda gli anni 2022 e 2023. "
            "L'indice è stato calcolato partendo dai dati ISPAT sul movimento turistico e dai dati Vodafone relativi alle presenze misurate.",
            map=dict(
                geojson="map_apt",
                key="properties.name",
                locations_col="comune",
            ),
        ),
        livello_turismo_sommerso_estate=dict(
            dataset="df_turismo_sommerso",
            title="Rapporto presenze misurate / presenze ufficiali di turisti (estate)",
            key="ratio_estate",
            other=["ratio_estate", "presenze_estate", "presenze_vodafone_estate"],
            alias={
                "anno": "Anno",
                "comune": "Ambito",
                "ratio_estate": "Rapporto presenze misurate / ufficiali",
                "presenze_estate": "Presenze ufficiali",
                "presenze_vodafone_estate": "Presenze misurate",
            },
            help="L'indice misura il rapporto, limitato ai mesi estivi (giugno-settembre) fra le presenze di turisti raccolte attraverso l’analisi di dati da rete di telefonia mobile e le presenze ufficiali di turisti in strutture alberghiere e extra-alberghiere. "
            "L’analisi è a livello di ambito turistico e riguarda gli anni 2022 e 2023. "
            "L'indice è stato calcolato partendo dai dati ISPAT sul movimento turistico e dai dati Vodafone relativi alle presenze misurate.",
            map=dict(
                geojson="map_apt",
                key="properties.name",
                locations_col="comune",
            ),
        ),
    )

    _category_map = {
        "capacity": _capacity_indices,
        "overtourism": _overtourism_indexes,
        "flows": _diffusion_indexes,
        "redistribution": _redistribution_indexes,
        "hidden": _hidden_tourism_indexes,
    }

    _category_names = {
        "capacity": "Indici di Capacità",
        "flows": "Flussi",
        "overtourism": "Livello di Affollamento",
        "redistribution": "Ridistribuzione dei Turisti",
        "hidden": "Turismo Sommerso",
    }

    def __init__(self, data_path: str) -> None:
        self.data_path = data_path
        self._map = {}
        self._df = {}

    def get_categories(self) -> dict:
        return self._category_names

    def get_list(self, category: str = "") -> dict:
        if category != "":
            return self._category_map[category]
        indexes = {}
        for k in self._category_map:
            indexes.update(self._category_map[k])
        return indexes

    def _load_map(self, map_: str, refresh: bool = False) -> None:
        if map_ not in self._map or refresh:
            path = f"{self.data_path}/{map_}.geojson"
            with open(path, "r") as f:
                self._map[map_] = orjson.loads(f.read())

    def _load_data(self, df: str, refresh: bool = False) -> None:
        if df not in self._df or refresh:
            path = f"{self.data_path}/{df}.parquet"
            self._df[df] = pd.read_parquet(path).reset_index()

    def _jsonify_value(self, value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, dict):
            return {key: self._jsonify_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._jsonify_value(item) for item in value]
        if isinstance(value, tuple):
            return [self._jsonify_value(item) for item in value]
        return value

    def get_map(self, map_: str) -> dict:
        self._load_map(map_)
        return self._map[map_]

    def get_dataframe(self, df: str) -> dict:
        self._load_data(df)
        dict_ = self._jsonify_value(self._df[df].to_dict(orient="records"))
        return {"data": dict_}

    def refresh(self) -> None:
        for i in self._indexes.values():
            self._load_map(i["map"], refresh=True)
            self._load_data(i["dataset"], refresh=True)
