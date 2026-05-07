# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Language = Literal["it", "en"]


@dataclass(frozen=True)
class LocalizedText:
    it: str
    en: str

    def resolve(self, language: Language) -> str:
        return self.en if language == "en" else self.it


@dataclass(frozen=True)
class MapDefinition:
    geojson: str
    key: str
    locations_col: str

    def to_public_dict(self) -> dict[str, str]:
        return {
            "geojson": self.geojson,
            "key": self.key,
            "locations_col": self.locations_col,
        }


@dataclass(frozen=True)
class IndexDefinition:
    dataset: str
    title: LocalizedText
    key: str
    other: tuple[str, ...]
    alias: dict[str, LocalizedText]
    help: LocalizedText
    map: MapDefinition
    ticks: tuple[tuple[Any, ...], tuple[Any, ...]] | None = None

    def to_public_dict(self, language: Language) -> dict[str, Any]:
        payload = {
            "dataset": self.dataset,
            "title": self.title.resolve(language),
            "key": self.key,
            "other": list(self.other),
            "alias": {
                key: value.resolve(language) for key, value in self.alias.items()
            },
            "help": self.help.resolve(language),
            "map": self.map.to_public_dict(),
        }
        if self.ticks is not None:
            payload["ticks"] = self.ticks
        return payload


@dataclass(frozen=True)
class CategoryDefinition:
    name: LocalizedText
    indexes: dict[str, IndexDefinition]

    def to_public_dict(self, language: Language) -> dict[str, dict[str, Any]]:
        return {
            key: definition.to_public_dict(language)
            for key, definition in self.indexes.items()
        }


@dataclass(frozen=True)
class IndexCatalog:
    categories: dict[str, CategoryDefinition]

    def get_categories(self, language: Language) -> dict[str, str]:
        return {
            key: category.name.resolve(language)
            for key, category in self.categories.items()
        }

    def get_indexes(
        self,
        language: Language,
        category: str = "",
    ) -> dict[str, dict[str, Any]]:
        if category:
            return self.categories[category].to_public_dict(language)

        payload: dict[str, dict[str, Any]] = {}
        for definition in self.categories.values():
            payload.update(definition.to_public_dict(language))
        return payload


def _text(it: str, en: str) -> LocalizedText:
    return LocalizedText(it=it, en=en)


def _labels(values: dict[str, tuple[str, str]]) -> dict[str, LocalizedText]:
    return {
        key: _text(it=localized[0], en=localized[1])
        for key, localized in values.items()
    }


def _map(geojson: str, key: str, locations_col: str) -> MapDefinition:
    return MapDefinition(
        geojson=geojson,
        key=key,
        locations_col=locations_col,
    )


_MUNICIPALITY_ALIASES = _labels(
    {
        "anno": ("Anno", "Year"),
        "comune": ("Comune", "Municipality"),
    }
)

_AREA_ALIASES = _labels(
    {
        "anno": ("Anno", "Year"),
        "comune": ("Ambito", "Area"),
    }
)

_FLOW_DAY_LABELS = {
    "feriali": _text("giorni feriali", "weekdays"),
    "prefestivi": _text("giorni prefestivi", "pre-holiday days"),
    "festivi": _text("giorni festivi", "holidays"),
    "sempre": _text("tutti i giorni", "all days"),
}

_FLOW_DIRECTION_LABELS = {
    "in": _text("in ingresso", "inbound"),
    "out": _text("in uscita", "outbound"),
}

_FLOW_HELP = _text(
    (
        "L'indice dei flussi descrive diverse misure dei movimenti giornalieri "
        "di persone nelle varie aree. Attraverso la selezione dei parametri si "
        "possono ottenere i flussi giornalieri in entrata o in uscita; "
        "selezionare i flussi totali, solo quelli legati agli escursionisti o il "
        "rapporto fra flussi di escursionisti e flussi totali; e distinguere tra "
        "giorni feriali, prefestivi, festivi e tutti i giorni. L'indice "
        "definisce, per ogni territorio, un livello di densità dei flussi, dove "
        "LIV_10 rappresenta i flussi più intensi. L'indice è calcolato a partire "
        "dai dati Vodafone relativi ai flussi dell'anno 2024."
    ),
    (
        "The flow index describes several measures of daily population movements "
        "across the different areas. By selecting the parameters, you can "
        "retrieve daily inbound or outbound flows; choose total flows, only "
        "excursionist flows, or the ratio of excursionist flows to total flows; "
        "and distinguish between weekdays, pre-holiday days, holidays, and all "
        "days. The index defines a flow density level for each area, where "
        "LIV_10 represents the most intense flows. The index is computed from "
        "Vodafone flow data for 2024."
    ),
)

_REDISTRIBUTION_HELP = _text(
    (
        "L'indice di ridistribuzione misura lo sbilanciamento nei flussi di "
        "persone, che dovrebbe essere riallocato per ridurre il rischio di "
        "sovraffollamento in determinate aree. L'indice è positivo per le aree "
        "che dovrebbero attrarre più persone, negativo per le aree che dovrebbero "
        "ridurre i flussi. Il valore assoluto dell'indice indica l'intensità "
        "percentuale della riallocazione dei flussi: più alto il valore assoluto, "
        "maggiore la variazione percentuale dello sbilanciamento e della variazione "
        "dei flussi prospettata. Questo indice suggerisce una quantità di "
        "investimento, ad esempio in pubblicità, che le varie aree dovrebbero "
        "attuare per incentivare i cittadini alla mobilità nelle zone meno a "
        "rischio di sovraffollamento. L'indice è calcolato partendo dai dati "
        "Vodafone relativi alle presenze dell'anno 2024."
    ),
    (
        "The redistribution index measures the imbalance in people flows that "
        "should be reallocated to reduce the risk of overcrowding in specific "
        "areas. The index is positive for areas that should attract more people "
        "and negative for areas that should reduce flows. The absolute value of "
        "the index indicates the percentage intensity of the flow reallocation: "
        "the higher the absolute value, the larger the expected percentage change "
        "in the imbalance and in the resulting flow variation. This index suggests "
        "an amount of investment, for example in advertising, that each area "
        "should activate to encourage mobility toward zones with a lower risk of "
        "overcrowding. The index is computed from Vodafone presence data for 2024."
    ),
)


def _build_capacity_indices() -> dict[str, IndexDefinition]:
    return {
        "ricettivita": IndexDefinition(
            dataset="df_tasso_ricettivita",
            title=_text("Indice di ricettività", "Accommodation capacity index"),
            key="ricettivita",
            other=("ricettivita", "popolazione", "posti_letto"),
            alias=(
                _MUNICIPALITY_ALIASES
                | _labels(
                    {
                        "ricettivita": ("Ricettività", "Accommodation capacity"),
                        "popolazione": ("Popolazione", "Population"),
                        "posti_letto": ("Posti letto", "Beds"),
                    }
                )
            ),
            help=_text(
                (
                    "L'indice di ricettività definisce il rapporto fra i letti "
                    "presenti negli esercizi ricettivi e gli abitanti di una stessa "
                    "area. L'indice è una misura della capacità turistica rispetto "
                    "alla dimensione, in termini di popolazione, di un'area. "
                    "L'indice è calcolato partendo dai dati ISPAT relativi alla "
                    "popolazione residente e alla consistenza degli esercizi "
                    "alberghieri e extra-alberghieri."
                ),
                (
                    "The accommodation capacity index measures the ratio between "
                    "beds available in accommodation establishments and the "
                    "inhabitants of the same area. The index measures tourism "
                    "capacity relative to the size of the area in terms of resident "
                    "population. The index is computed from ISPAT data on resident "
                    "population and the stock of hotel and extra-hotel "
                    "accommodation establishments."
                ),
            ),
            map=_map("map_comuni", "properties.com_code", "ID"),
        ),
        "turisticita": IndexDefinition(
            dataset="df_tasso_turisticita",
            title=_text("Indice di turisticità", "Tourism intensity index"),
            key="turisticita",
            other=("turisticita", "popolazione"),
            alias=(
                _MUNICIPALITY_ALIASES
                | _labels(
                    {
                        "turisticita": ("Turisticità", "Tourism intensity"),
                        "popolazione": ("Popolazione", "Population"),
                    }
                )
            ),
            help=_text(
                (
                    "L'indice di turisticità definisce il rapporto fra il numero "
                    "medio giornaliero di turisti negli esercizi ricettivi e gli "
                    "abitanti di una stessa area. L'indice è una misura "
                    "dell'effettivo peso del turismo rispetto alla dimensione, in "
                    "termini di popolazione, di un'area. L'indice è calcolato "
                    "partendo dai dati Vodafone per quanto riguarda le presenze "
                    "turistiche e dai dati ISPAT relativi alla popolazione residente."
                ),
                (
                    "The tourism intensity index measures the ratio between the "
                    "average daily number of tourists in accommodation establishments "
                    "and the inhabitants of the same area. The index measures the "
                    "actual weight of tourism relative to the size of the area in "
                    "terms of population. The index is computed from Vodafone data "
                    "for tourist presences and ISPAT data on resident population."
                ),
            ),
            map=_map("map_vodafone", "properties.name", "comune"),
        ),
        "turisticita_estiva": IndexDefinition(
            dataset="df_tasso_turisticita_estate",
            title=_text(
                "Indice di turisticità estiva",
                "Summer tourism intensity index",
            ),
            key="turisticita",
            other=("turisticita", "popolazione"),
            alias=(
                _MUNICIPALITY_ALIASES
                | _labels(
                    {
                        "turisticita": ("Turisticità", "Tourism intensity"),
                        "popolazione": ("Popolazione", "Population"),
                    }
                )
            ),
            help=_text(
                (
                    "L'indice di turisticità definisce il rapporto fra il numero "
                    "medio giornaliero di turisti negli esercizi ricettivi durante "
                    "il periodo estivo, da giugno a settembre, e gli abitanti di "
                    "una stessa area. L'indice è una misura dell'effettivo peso del "
                    "turismo rispetto alla dimensione, in termini di popolazione, di "
                    "un'area. L'indice è calcolato partendo dai dati Vodafone per "
                    "quanto riguarda le presenze turistiche e dai dati ISPAT relativi "
                    "alla popolazione residente."
                ),
                (
                    "The summer tourism intensity index measures the ratio between "
                    "the average daily number of tourists in accommodation "
                    "establishments during the summer period, from June to September, "
                    "and the inhabitants of the same area. The index measures the "
                    "actual weight of tourism relative to the size of the area in "
                    "terms of population. The index is computed from Vodafone data "
                    "for tourist presences and ISPAT data on resident population."
                ),
            ),
            map=_map("map_vodafone", "properties.name", "comune"),
        ),
        "stagionalita": IndexDefinition(
            dataset="df_stagionalita_presenze",
            title=_text(
                "Indice di stagionalità delle presenze",
                "Presence seasonality index",
            ),
            key="stagionalita",
            other=(
                "stagionalita",
                "nturisti_alta_stagione",
                "nturisti_bassa_stagione",
            ),
            alias=(
                _MUNICIPALITY_ALIASES
                | _labels(
                    {
                        "stagionalita": ("Stagionalità", "Seasonality"),
                        "nturisti_alta_stagione": (
                            "Presenze turisti alta stagione",
                            "Tourist presences in high season",
                        ),
                        "nturisti_bassa_stagione": (
                            "Presenze turisti bassa stagione",
                            "Tourist presences in low season",
                        ),
                    }
                )
            ),
            help=_text(
                (
                    "L'indice di stagionalità definisce il rapporto fra le presenze "
                    "di turisti ed escursionisti durante l'alta stagione estiva, a "
                    "luglio e agosto, e le presenze durante un periodo di "
                    "riferimento di bassa stagione, a ottobre e novembre. L'indice è "
                    "calcolato partendo dai dati Vodafone relativi alle presenze di "
                    "turisti ed escursionisti."
                ),
                (
                    "The seasonality index measures the ratio between tourist and "
                    "excursionist presences during the summer high season, in July "
                    "and August, and presences during a reference low-season period, "
                    "in October and November. The index is computed from Vodafone "
                    "data on tourist and excursionist presences."
                ),
            ),
            map=_map("map_vodafone", "properties.name", "comune"),
        ),
        "variazione_percentuale": IndexDefinition(
            dataset="df_tasso_variazione_pecentuale",
            title=_text(
                "Tasso di variazione percentuale degli arrivi di turisti",
                "Percentage change in tourist arrivals",
            ),
            key="tasso_variazione_perc",
            other=(
                "tasso_variazione_perc",
                "anno_2022",
                "anno_2023",
                "anno_2024",
            ),
            alias=(
                _AREA_ALIASES
                | _labels(
                    {
                        "tasso_variazione_perc": (
                            "Tasso di variazione percentuale",
                            "Percentage change",
                        ),
                        "anno_2022": ("Arrivi anno 2022", "Arrivals in 2022"),
                        "anno_2023": ("Arrivi anno 2023", "Arrivals in 2023"),
                        "anno_2024": ("Arrivi anno 2024", "Arrivals in 2024"),
                    }
                )
            ),
            help=_text(
                (
                    "L'indice di variazione percentuale degli arrivi di turisti "
                    "misura il tasso di variazione, in percentuale, degli arrivi di "
                    "turisti nei diversi ambiti turistici trentini nel triennio "
                    "2022-2024. L'indice è calcolato partendo dai dati ISPAT "
                    "relativi ai movimenti turistici."
                ),
                (
                    "The percentage change index for tourist arrivals measures the "
                    "percentage variation in tourist arrivals across the different "
                    "tourism areas of Trentino over the 2022-2024 period. The index "
                    "is computed from ISPAT tourism movement data."
                ),
            ),
            map=_map("map_apt", "properties.name", "comune"),
        ),
        "strutture_non_convenzionali": IndexDefinition(
            dataset="df_incidenza_strutture_non_conv",
            title=_text(
                "Indice di incidenza ospitalità non convenzionale (strutture)",
                "Share of non-conventional accommodation facilities",
            ),
            key="incidenza_strutture_non_conv",
            other=(
                "incidenza_strutture_non_conv",
                "tot_strutture_non_conv",
                "tot_strutture",
            ),
            alias=(
                _MUNICIPALITY_ALIASES
                | _labels(
                    {
                        "incidenza_strutture_non_conv": (
                            "Incidenza strutture non conv.",
                            "Share of non-conventional facilities",
                        ),
                        "tot_strutture_non_conv": (
                            "Numero strutture non conv.",
                            "Non-conventional facilities",
                        ),
                        "tot_strutture": ("Totale strutture", "Total facilities"),
                    }
                )
            ),
            help=_text(
                (
                    "Questo indice di incidenza dell'ospitalità non convenzionale "
                    "misura il rapporto fra le strutture ricettive non convenzionali "
                    "e il totale delle strutture presenti in un'area. L'indice è "
                    "calcolato partendo dai dati ISPAT relativi alla consistenza "
                    "degli esercizi alberghieri e extra-alberghieri."
                ),
                (
                    "This non-conventional hospitality share index measures the "
                    "ratio between non-conventional accommodation facilities and the "
                    "total number of facilities in an area. The index is computed "
                    "from ISPAT data on the stock of hotel and extra-hotel "
                    "accommodation establishments."
                ),
            ),
            map=_map("map_comuni", "properties.com_code", "ID"),
        ),
        "postiletto_non_convenzionali": IndexDefinition(
            dataset="df_incidenza_postiletto_non_conv",
            title=_text(
                "Indice di incidenza ospitalità non convenzionale (posti letto)",
                "Share of non-conventional accommodation beds",
            ),
            key="incidenza_postiletto_non_conv",
            other=(
                "incidenza_postiletto_non_conv",
                "tot_postiletto_non_conv",
                "tot_postiletto",
            ),
            alias=(
                _MUNICIPALITY_ALIASES
                | _labels(
                    {
                        "incidenza_postiletto_non_conv": (
                            "Incidenza posti letto non conv.",
                            "Share of non-conventional beds",
                        ),
                        "tot_postiletto_non_conv": (
                            "Numero posti letto non conv.",
                            "Non-conventional beds",
                        ),
                        "tot_postiletto": ("Totale posti letto", "Total beds"),
                    }
                )
            ),
            help=_text(
                (
                    "Questo indice di incidenza dell'ospitalità non convenzionale "
                    "misura il rapporto fra il numero di posti letto in strutture "
                    "ricettive non convenzionali e il numero totale di posti letto "
                    "in tutte le strutture di un'area. L'indice è calcolato partendo "
                    "dai dati ISPAT relativi alla consistenza degli esercizi "
                    "alberghieri e extra-alberghieri."
                ),
                (
                    "This non-conventional hospitality share index measures the "
                    "ratio between the number of beds in non-conventional "
                    "accommodation facilities and the total number of beds in all "
                    "facilities in an area. The index is computed from ISPAT data on "
                    "the stock of hotel and extra-hotel accommodation establishments."
                ),
            ),
            map=_map("map_comuni", "properties.com_code", "ID"),
        ),
    }


def _build_overtourism_indexes() -> dict[str, IndexDefinition]:
    return {
        "livello_overturismo": IndexDefinition(
            dataset="df_overturismo",
            title=_text(
                "Livello complessivo di affollamento turistico estivo",
                "Overall summer tourist crowding level",
            ),
            key="level",
            other=("level", "ricettivita", "turisticita", "stagionalita", "flusso"),
            alias=(
                _MUNICIPALITY_ALIASES
                | _labels(
                    {
                        "level": (
                            "Livello complessivo di affollamento",
                            "Overall crowding level",
                        ),
                        "ricettivita": (
                            "Livello di ricettività",
                            "Accommodation capacity level",
                        ),
                        "turisticita": (
                            "Livello di turisticità estiva",
                            "Summer tourism intensity level",
                        ),
                        "stagionalita": (
                            "Livello di stagionalità",
                            "Seasonality level",
                        ),
                        "flusso": (
                            "Livello del flusso di escursionisti",
                            "Excursionist flow level",
                        ),
                    }
                )
            ),
            help=_text(
                (
                    "L'indice complessivo di affollamento turistico estivo integra "
                    "e aggrega diversi indici legati all'affollamento turistico, "
                    "come ricettività, turisticità, stagionalità e flussi di "
                    "escursionisti. L'indice complessivo identifica comuni e aree in "
                    "cui uno o più di questi indici assumono livelli elevati nel "
                    "panorama trentino, indicati con un numero crescente di '*'."
                ),
                (
                    "The overall summer tourist crowding index integrates and "
                    "aggregates several indicators related to tourist crowding, such "
                    "as accommodation capacity, tourism intensity, seasonality, and "
                    "excursionist flows. The overall index identifies municipalities "
                    "and areas where one or more of these indicators reach high "
                    "levels within Trentino, shown with an increasing number of '*'."
                ),
            ),
            map=_map("map_vodafone_2024", "properties.comune", "comune"),
        )
    }


def _flow_title_total(where: str, when: str) -> LocalizedText:
    direction = _FLOW_DIRECTION_LABELS[where]
    day = _FLOW_DAY_LABELS[when]
    return _text(
        f"Flussi totali {direction.it} ({day.it})",
        f"Total {direction.en} flows ({day.en})",
    )


def _flow_title_excursionists(where: str, when: str) -> LocalizedText:
    direction = _FLOW_DIRECTION_LABELS[where]
    day = _FLOW_DAY_LABELS[when]
    return _text(
        f"Flussi di escursionisti {direction.it} ({day.it})",
        f"Excursionist {direction.en} flows ({day.en})",
    )


def _flow_title_ratio(where: str, when: str) -> LocalizedText:
    direction = _FLOW_DIRECTION_LABELS[where]
    day = _FLOW_DAY_LABELS[when]
    return _text(
        f"Rapporto flussi di escursionisti / flussi totali {direction.it} ({day.it})",
        f"Ratio of excursionist flows / total flows {direction.en} ({day.en})",
    )


def _build_flow_indices() -> dict[str, IndexDefinition]:
    indexes: dict[str, IndexDefinition] = {}
    for where in ("in", "out"):
        for when in ("feriali", "prefestivi", "festivi", "sempre"):
            total_key = f"flusso_{where}_tutti_{when}"
            excursionist_key = f"flusso_{where}_escursionisti_{when}"
            ratio_key = f"flusso_{where}_rapporto_{when}"

            indexes[total_key] = IndexDefinition(
                dataset="df_flussi_estate",
                title=_flow_title_total(where, when),
                key=f"level_{where}_tutti_{when}",
                other=(
                    f"level_{where}_tutti_{when}_label",
                    f"flows_{where}_tutti_{when}",
                ),
                alias=(
                    _MUNICIPALITY_ALIASES
                    | _labels(
                        {
                            f"level_{where}_tutti_{when}": (
                                "Livello di densità dei flussi",
                                "Flow density level",
                            ),
                            f"level_{where}_tutti_{when}_label": (
                                "Livello di densità flussi",
                                "Flow density label",
                            ),
                            f"flows_{where}_tutti_{when}": (
                                "Valore flussi",
                                "Flow value",
                            ),
                        }
                    )
                ),
                help=_FLOW_HELP,
                map=_map("map_vodafone_2024", "properties.comune", "comune"),
                ticks=(
                    (1, 2, 3, 4, 5, 6, 7),
                    ("N/A", "LIV_5", "LIV_6", "LIV_7", "LIV_8", "LIV_9", "LIV_10"),
                ),
            )

            indexes[excursionist_key] = IndexDefinition(
                dataset="df_flussi_estate",
                title=_flow_title_excursionists(where, when),
                key=f"level_{where}_escursionisti_{when}",
                other=(
                    f"level_{where}_escursionisti_{when}_label",
                    f"flows_{where}_escursionisti_{when}",
                ),
                alias=(
                    _MUNICIPALITY_ALIASES
                    | _labels(
                        {
                            f"level_{where}_escursionisti_{when}": (
                                "Livello di densità dei flussi",
                                "Flow density level",
                            ),
                            f"level_{where}_escursionisti_{when}_label": (
                                "Livello di densità flussi",
                                "Flow density label",
                            ),
                            f"flows_{where}_escursionisti_{when}": (
                                "Valore flussi",
                                "Flow value",
                            ),
                        }
                    )
                ),
                help=_FLOW_HELP,
                map=_map("map_vodafone_2024", "properties.comune", "comune"),
                ticks=(
                    (1, 2, 3, 4, 5, 6, 7),
                    ("N/A", "LIV_5", "LIV_6", "LIV_7", "LIV_8", "LIV_9", "LIV_10"),
                ),
            )

            indexes[ratio_key] = IndexDefinition(
                dataset="df_flussi_estate",
                title=_flow_title_ratio(where, when),
                key=f"flows_{where}_ratio_{when}",
                other=(
                    f"flows_{where}_ratio_{when}",
                    f"flows_{where}_tutti_{when}",
                    f"flows_{where}_escursionisti_{when}",
                ),
                alias=(
                    _MUNICIPALITY_ALIASES
                    | _labels(
                        {
                            f"flows_{where}_ratio_{when}": (
                                "Rapporto flussi escursionisti / flussi totali",
                                "Excursionist / total flow ratio",
                            ),
                            f"flows_{where}_tutti_{when}": (
                                "Valore flussi totali",
                                "Total flow value",
                            ),
                            f"flows_{where}_escursionisti_{when}": (
                                "Valore flussi escursionisti",
                                "Excursionist flow value",
                            ),
                        }
                    )
                ),
                help=_FLOW_HELP,
                map=_map("map_vodafone_2024", "properties.comune", "comune"),
            )
    return indexes


def _build_redistribution_indices() -> dict[str, IndexDefinition]:
    return {
        "diffusione_feriale": IndexDefinition(
            dataset="df_distribuzione_feriale",
            title=_text(
                "Costo di distribuzione dei turisti (giorni feriali)",
                "Tourist redistribution cost (weekdays)",
            ),
            key="value",
            other=("value",),
            alias=(
                _MUNICIPALITY_ALIASES
                | _labels({"value": ("Costo di distribuzione", "Redistribution cost")})
            ),
            help=_REDISTRIBUTION_HELP,
            map=_map("map_vodafone_2024", "properties.comune", "comune"),
        ),
        "diffusione_prefestivo": IndexDefinition(
            dataset="df_distribuzione_prefestivo",
            title=_text(
                "Costo di distribuzione dei turisti (giorni prefestivi)",
                "Tourist redistribution cost (pre-holiday days)",
            ),
            key="value",
            other=("value",),
            alias=(
                _MUNICIPALITY_ALIASES
                | _labels({"value": ("Costo di distribuzione", "Redistribution cost")})
            ),
            help=_REDISTRIBUTION_HELP,
            map=_map("map_vodafone_2024", "properties.comune", "comune"),
        ),
        "diffusione_festivo": IndexDefinition(
            dataset="df_distribuzione_festivo",
            title=_text(
                "Costo di distribuzione dei turisti (giorni festivi)",
                "Tourist redistribution cost (holidays)",
            ),
            key="value",
            other=("value",),
            alias=(
                _MUNICIPALITY_ALIASES
                | _labels({"value": ("Costo di distribuzione", "Redistribution cost")})
            ),
            help=_REDISTRIBUTION_HELP,
            map=_map("map_vodafone_2024", "properties.comune", "comune"),
        ),
    }


def _build_hidden_tourism_indices() -> dict[str, IndexDefinition]:
    return {
        "livello_turismo_sommerso": IndexDefinition(
            dataset="df_turismo_sommerso",
            title=_text(
                "Rapporto presenze misurate / presenze ufficiali di turisti",
                "Ratio of measured tourist presences / official tourist presences",
            ),
            key="ratio",
            other=("ratio", "presenze", "presenze_vodafone"),
            alias=(
                _AREA_ALIASES
                | _labels(
                    {
                        "ratio": (
                            "Rapporto presenze misurate / ufficiali",
                            "Measured / official presences ratio",
                        ),
                        "presenze": ("Presenze ufficiali", "Official presences"),
                        "presenze_vodafone": (
                            "Presenze misurate",
                            "Measured presences",
                        ),
                    }
                )
            ),
            help=_text(
                (
                    "L'indice misura il rapporto fra le presenze di turisti "
                    "raccolte attraverso l'analisi di dati da rete di telefonia "
                    "mobile e le presenze ufficiali di turisti in strutture "
                    "alberghiere e extra-alberghiere. L'analisi è a livello di "
                    "ambito turistico e riguarda gli anni 2022 e 2023. L'indice è "
                    "stato calcolato partendo dai dati ISPAT sul movimento turistico "
                    "e dai dati Vodafone relativi alle presenze misurate."
                ),
                (
                    "The index measures the ratio between tourist presences captured "
                    "through the analysis of mobile network data and the official "
                    "tourist presences recorded in hotel and extra-hotel "
                    "accommodation establishments. The analysis is carried out at the "
                    "tourism-area level and refers to 2022 and 2023. The index is "
                    "computed from ISPAT tourism movement data and Vodafone measured "
                    "presence data."
                ),
            ),
            map=_map("map_apt", "properties.name", "comune"),
        ),
        "livello_turismo_sommerso_estate": IndexDefinition(
            dataset="df_turismo_sommerso",
            title=_text(
                "Rapporto presenze misurate / presenze ufficiali di turisti (estate)",
                "Ratio of measured tourist presences / official tourist presences (summer)",
            ),
            key="ratio_estate",
            other=("ratio_estate", "presenze_estate", "presenze_vodafone_estate"),
            alias=(
                _AREA_ALIASES
                | _labels(
                    {
                        "ratio_estate": (
                            "Rapporto presenze misurate / ufficiali",
                            "Measured / official presences ratio",
                        ),
                        "presenze_estate": (
                            "Presenze ufficiali",
                            "Official presences",
                        ),
                        "presenze_vodafone_estate": (
                            "Presenze misurate",
                            "Measured presences",
                        ),
                    }
                )
            ),
            help=_text(
                (
                    "L'indice misura il rapporto, limitato ai mesi estivi, da giugno "
                    "a settembre, fra le presenze di turisti raccolte attraverso "
                    "l'analisi di dati da rete di telefonia mobile e le presenze "
                    "ufficiali di turisti in strutture alberghiere e "
                    "extra-alberghiere. L'analisi è a livello di ambito turistico e "
                    "riguarda gli anni 2022 e 2023. L'indice è stato calcolato "
                    "partendo dai dati ISPAT sul movimento turistico e dai dati "
                    "Vodafone relativi alle presenze misurate."
                ),
                (
                    "The index measures the ratio, limited to the summer months from "
                    "June to September, between tourist presences captured through the "
                    "analysis of mobile network data and the official tourist "
                    "presences recorded in hotel and extra-hotel accommodation "
                    "establishments. The analysis is carried out at the tourism-area "
                    "level and refers to 2022 and 2023. The index is computed from "
                    "ISPAT tourism movement data and Vodafone measured presence data."
                ),
            ),
            map=_map("map_apt", "properties.name", "comune"),
        ),
    }


# ---------------------------------------------------------------------------
# Simulation index catalog (Molveno overtourism model parameters)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimIndexEntry:
    """Simulation model parameter definition with bilingual metadata."""

    index_id: str
    index_type: str
    index_name: LocalizedText
    group: LocalizedText
    description: LocalizedText
    min: float
    max: float
    step: float
    editable: bool = True
    index_category: str | None = None
    # constant
    v: float | None = None
    # uniform / lognorm / triang
    loc: float | None = None
    scale: float | None = None
    # lognorm
    s: float | None = None
    # triang
    c: float | None = None

    def to_config_dict(self, language: Language = "it") -> dict:
        """Return a dict compatible with the YAML-based viewer config format."""
        entry: dict = {
            "index_id": self.index_id,
            "index_type": self.index_type,
            "index_name": self.index_name.resolve(language),
            # group ID is always the Italian string for backward compatibility
            "group": self.group.it,
            "description": self.description.resolve(language),
            "min": self.min,
            "max": self.max,
            "step": self.step,
            "editable": self.editable,
        }
        if self.index_category is not None:
            entry["index_category"] = self.index_category
        if self.v is not None:
            entry["v"] = self.v
        if self.loc is not None:
            entry["loc"] = self.loc
        if self.scale is not None:
            entry["scale"] = self.scale
        if self.s is not None:
            entry["s"] = self.s
        if self.c is not None:
            entry["c"] = self.c
        return entry


@dataclass(frozen=True)
class SimIndexCatalog:
    """Ordered collection of simulation parameter definitions."""

    entries: tuple[SimIndexEntry, ...]

    def to_config(self, language: Language = "it") -> dict:
        """Build a viewer-compatible config dict for the given language."""
        return {"indexes": [e.to_config_dict(language) for e in self.entries]}


def _se(
    index_id: str,
    index_type: str,
    index_name: tuple[str, str],
    group: tuple[str, str],
    description: tuple[str, str],
    min: float,
    max: float,
    step: float,
    editable: bool = True,
    index_category: str | None = None,
    **kwargs: float,
) -> SimIndexEntry:
    return SimIndexEntry(
        index_id=index_id,
        index_type=index_type,
        index_name=_text(*index_name),
        group=_text(*group),
        description=_text(*description),
        min=min,
        max=max,
        step=step,
        editable=editable,
        index_category=index_category,
        **kwargs,
    )


_PARKING = ("Parcheggi", "Parking")
_BEACH = ("Spiaggia", "Beach")
_HOTELS = ("Alberghi", "Hotels")
_RESTAURANTS = ("Ristoranti", "Restaurants")
_FLOWS = ("Flussi", "Flows")

MOLVENO_SIM_INDEXES = SimIndexCatalog(
    entries=(
        _se(
            "available_parking_spaces",
            "uniform",
            (
                "Numero di parcheggi disponibili",
                "Number of available parking spaces",
            ),
            _PARKING,
            (
                "Numero di posti auto disponibili a Molveno",
                "Number of available parking spots in Molveno",
            ),
            min=0.0,
            max=1000.0,
            step=10.0,
            loc=350.0,
            scale=100.0,
        ),
        _se(
            "available_beach_seats",
            "uniform",
            (
                "Numero di posti disponibili in spiaggia",
                "Number of available beach spots",
            ),
            _BEACH,
            (
                "Numero massimo di presenza nella spiaggia di Molveno che "
                "garantiscono un distanziamento adeguato fra le persone",
                "Maximum number of people on Molveno beach that guarantee "
                "adequate distancing between persons",
            ),
            min=0.0,
            max=10000.0,
            step=100.0,
            loc=6000.0,
            scale=1000.0,
        ),
        _se(
            "available_beds",
            "lognorm",
            (
                "Posti letto disponibili",
                "Available beds",
            ),
            _HOTELS,
            (
                "Totale posti letto nelle strutture ricettive alberghiere e "
                "extralberghiere a Molveno",
                "Total beds in hotel and extra-hotel accommodation facilities "
                "in Molveno",
            ),
            min=0.0,
            max=10000.0,
            step=100.0,
            loc=0.0,
            scale=5000.0,
            s=0.125,
        ),
        _se(
            "available_restaurant_seats",
            "triang",
            (
                "Posti a sedere nei ristoranti",
                "Restaurant seats",
            ),
            _RESTAURANTS,
            (
                "Totale posti a sedere nella ristorazione commerciale a Molveno",
                "Total seats in commercial catering establishments in Molveno",
            ),
            min=0.0,
            max=6000.0,
            step=100.0,
            loc=2400.0,
            scale=800.0,
            c=0.5,
        ),
        _se(
            "excursionists_parking_percentage",
            "constant",
            (
                "Percentuale di escursionisti che usano i parcheggi",
                "Percentage of excursionists using parking",
            ),
            _PARKING,
            (
                "Percentuale di escursionisti che usano i parcheggi",
                "Percentage of excursionists who use parking facilities",
            ),
            min=0.0,
            max=100.0,
            step=1.0,
            index_category="%",
            v=80.0,
        ),
        _se(
            "excursionists_beach_percentage",
            "constant",
            (
                "Percentuale di escursionisti che usano la spiaggia",
                "Percentage of excursionists using the beach",
            ),
            _BEACH,
            (
                "Percentuale di escursionisti che usano la spiaggia",
                "Percentage of excursionists who go to the beach",
            ),
            min=0.0,
            max=100.0,
            step=1.0,
            index_category="%",
            v=80.0,
        ),
        _se(
            "tourists_parking_percentage",
            "constant",
            (
                "Percentuale di turisti che usano i parcheggi",
                "Percentage of tourists using parking",
            ),
            _PARKING,
            (
                "Percentuale di turisti che usano i parcheggi",
                "Percentage of tourists who use parking facilities",
            ),
            min=0.0,
            max=100.0,
            step=1.0,
            index_category="%",
            v=2.0,
        ),
        _se(
            "tourists_beach_percentage",
            "constant",
            (
                "Percentuale di turisti che usano la spiaggia",
                "Percentage of tourists using the beach",
            ),
            _BEACH,
            (
                "Percentuale di turisti che usano la spiaggia",
                "Percentage of tourists who go to the beach",
            ),
            min=0.0,
            max=100.0,
            step=1.0,
            index_category="%",
            v=50.0,
        ),
        _se(
            "tourists_accommodation_percentage",
            "constant",
            (
                "Percentuale di turisti che alloggiano in strutture ricettive",
                "Percentage of tourists staying in accommodation",
            ),
            _HOTELS,
            (
                "Percentuale di turisti che alloggiano in strutture ricettive "
                "alberghiere o extralberghiere a Molveno",
                "Percentage of tourists staying in hotel or extra-hotel "
                "accommodation facilities in Molveno",
            ),
            min=0.0,
            max=100.0,
            step=1.0,
            index_category="%",
            v=90.0,
        ),
        _se(
            "tourists_restaurant_percentage",
            "constant",
            (
                "Percentuale di turisti che usano i ristoranti",
                "Percentage of tourists using restaurants",
            ),
            _RESTAURANTS,
            (
                "Percentuale di turisti che usano i ristoranti",
                "Percentage of tourists who visit restaurants",
            ),
            min=0.0,
            max=100.0,
            step=1.0,
            index_category="%",
            v=20.0,
        ),
        _se(
            "tourists_per_vehicle_average",
            "constant",
            (
                "Numero medio di turisti per veicolo",
                "Average number of tourists per vehicle",
            ),
            _PARKING,
            (
                "Occupazione media (numero medio di persone) nei veicoli "
                "utilizzati dai turisti",
                "Average occupancy (mean number of persons) in vehicles "
                "used by tourists",
            ),
            min=0.1,
            max=5.0,
            step=0.1,
            v=2.5,
        ),
        _se(
            "excursionists_per_vehicle_average",
            "constant",
            (
                "Numero medio di escursionisti per veicolo",
                "Average number of excursionists per vehicle",
            ),
            _PARKING,
            (
                "Occupazione media (numero medio di persone) nei veicoli "
                "utilizzati dagli escursionisti",
                "Average occupancy (mean number of persons) in vehicles "
                "used by excursionists",
            ),
            min=0.1,
            max=5.0,
            step=0.1,
            v=2.5,
        ),
        _se(
            "tourists_parking_turnover",
            "constant",
            (
                "Ricambi giornalieri per posto auto (turisti)",
                "Daily turnover per parking space (tourists)",
            ),
            _PARKING,
            (
                "Numero di veicoli di turisti che possono occupare lo stesso "
                "posto auto nell'arco della giornata",
                "Number of tourist vehicles that can occupy the same parking "
                "space during the day",
            ),
            min=1.0,
            max=4.0,
            step=0.05,
            v=1.05,
        ),
        _se(
            "excursionists_parking_turnover",
            "constant",
            (
                "Ricambi giornalieri per posto auto (escursionisti)",
                "Daily turnover per parking space (excursionists)",
            ),
            _PARKING,
            (
                "Numero di veicoli di escursionisti che possono occupare lo "
                "stesso posto auto nell'arco della giornata",
                "Number of excursionist vehicles that can occupy the same "
                "parking space during the day",
            ),
            min=1.0,
            max=4.0,
            step=0.05,
            v=3.50,
        ),
        _se(
            "tourists_reduction_factor",
            "constant",
            (
                "Fattore di variazione di presenze turistiche",
                "Tourist presence variation factor",
            ),
            _FLOWS,
            (
                "Questo fattore serve per aumentare (> 100%) o diminuire "
                "(< 100%) la presenza stimata di turisti rispeto al valore "
                "storico.",
                "This factor is used to increase (> 100%) or decrease "
                "(< 100%) the estimated tourist presence relative to the "
                "historical value.",
            ),
            min=5.0,
            max=400.0,
            step=5.0,
            index_category="%",
            v=100.0,
        ),
        _se(
            "excursionists_reduction_factor",
            "constant",
            (
                "Fattore di variazione di presenze escursionistiche",
                "Excursionist presence variation factor",
            ),
            _FLOWS,
            (
                "Questo fattore serve per aumentare (> 100%) o diminuire "
                "(< 100%) la presenza stimata di escursionisti rispeto al "
                "valore storico.",
                "This factor is used to increase (> 100%) or decrease "
                "(< 100%) the estimated excursionist presence relative to "
                "the historical value.",
            ),
            min=5.0,
            max=400.0,
            step=5.0,
            index_category="%",
            v=100.0,
        ),
        _se(
            "tourists_saturation_level",
            "constant",
            (
                "Soglia di saturazione massima turisti",
                "Maximum tourist saturation threshold",
            ),
            _FLOWS,
            (
                "Questo valore rappresenta il livello massimo che può "
                "raggiungere la presenza di turisti a Molveno durante una "
                "giornata",
                "This value represents the maximum level that tourist "
                "presence in Molveno can reach during a day",
            ),
            min=1000.0,
            max=20000.0,
            step=100.0,
            v=10000.0,
        ),
        _se(
            "excursionists_saturation_level",
            "constant",
            (
                "Soglia di saturazione massima escursionisti",
                "Maximum excursionist saturation threshold",
            ),
            _FLOWS,
            (
                "Questo valore rappresenta il livello massimo che può "
                "raggiungere la presenza di escursionisti a Molveno durante "
                "una giornata",
                "This value represents the maximum level that excursionist "
                "presence in Molveno can reach during a day",
            ),
            min=1000.0,
            max=20000.0,
            step=100.0,
            v=10000.0,
        ),
        _se(
            "visitors_food_allocation_factor",
            "constant",
            (
                "Fattore di allorazione massimo dei posto a sedere nei ristoranti",
                "Maximum restaurant seat allocation factor",
            ),
            _RESTAURANTS,
            (
                "Fattore di allocazione che rappresenta il numero di posti a "
                "sedere occupati nel caso di ristoranti pieni (tenendo conto "
                "ad es. tavoli non completi)",
                "Allocation factor representing the number of occupied seats "
                "when restaurants are full (accounting for e.g. partially "
                "filled tables)",
            ),
            min=50.0,
            max=150.0,
            step=5.0,
            index_category="%",
            v=90.0,
        ),
        _se(
            "visitors_food_turnover",
            "constant",
            (
                "Tasso di rotazione dei tavoli",
                "Table turnover rate",
            ),
            _RESTAURANTS,
            (
                "Numero di volte in cui un tavolo viene occupato nell'arco "
                "di un servizio",
                "Number of times a table is occupied during a service period",
            ),
            min=0.5,
            max=4.0,
            step=0.05,
            v=2.0,
        ),
        _se(
            "tourists_beach_turnover",
            "uniform",
            (
                "Ricambi giornalieri per posto in spiaggia (turisti)",
                "Daily turnover per beach spot (tourists)",
            ),
            _BEACH,
            (
                "Numero di turisti che possono occupare lo stesso posto in "
                "spiaggia della giornata",
                "Number of tourists that can occupy the same beach spot during the day",
            ),
            min=1.0,
            max=4.0,
            step=0.05,
            loc=1.0,
            scale=2.0,
        ),
        _se(
            "excursionists_beach_turnover",
            "constant",
            (
                "Ricambi giornalieri per posto in spiaggia (escursionisti)",
                "Daily turnover per beach spot (excursionists)",
            ),
            _BEACH,
            (
                "Numero di escursionsti che possono occupare lo stesso posto "
                "in spiaggia della giornata",
                "Number of excursionists that can occupy the same beach spot "
                "during the day",
            ),
            min=1.0,
            max=4.0,
            step=0.05,
            v=1.05,
        ),
        _se(
            "tourists_accommodation_allocation_factor",
            "constant",
            (
                "Fattore massimo di allocazione dei posti letto",
                "Maximum bed allocation factor",
            ),
            _HOTELS,
            (
                "Fattore di allocazione che rappresenta il numero di posti "
                "letto occupati nel caso di alberghi pieni (tenendo conto "
                "ad es. di camere doppie uso singolio)",
                "Allocation factor representing the number of occupied beds "
                "when hotels are full (accounting for e.g. double rooms "
                "used as single)",
            ),
            min=50.0,
            max=125.0,
            step=5.0,
            index_category="%",
            v=85.0,
        ),
    )
)


OVERTOURISM_INDEX_CATALOG = IndexCatalog(
    categories={
        "capacity": CategoryDefinition(
            name=_text("Indici di Capacità", "Capacity Indices"),
            indexes=_build_capacity_indices(),
        ),
        "flows": CategoryDefinition(
            name=_text("Flussi", "Flows"),
            indexes=_build_flow_indices(),
        ),
        "overtourism": CategoryDefinition(
            name=_text("Livello di Affollamento", "Crowding Level"),
            indexes=_build_overtourism_indexes(),
        ),
        "redistribution": CategoryDefinition(
            name=_text("Ridistribuzione dei Turisti", "Tourist Redistribution"),
            indexes=_build_redistribution_indices(),
        ),
        "hidden": CategoryDefinition(
            name=_text("Turismo Sommerso", "Hidden Tourism"),
            indexes=_build_hidden_tourism_indices(),
        ),
    }
)
