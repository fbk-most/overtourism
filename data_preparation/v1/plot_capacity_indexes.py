### Library import

from pathlib import Path
import json

import streamlit as st
import plotly.express as px

from utils import get_dataframe

### Manage execution of streamlit

if __name__ == "__main__":
    if "__streamlitmagic__" not in locals():
        import streamlit.web.bootstrap

        streamlit.web.bootstrap.run(__file__, False, [], {})
        exit(0)

### Reading and fixing geojson files

def merge_polygons(p1, p2):
    assert len(p1) == 1 and len(p2) == 1  # Single polygons
    assert len(p1[0]) == 1 and len(p2[0]) == 1  # No holes
    ring1 = p1[0][0]
    ring2 = p2[0][0]
    shared1 = [i for i, e in enumerate(ring1[:-1]) if e in ring2]
    shared2 = [i for i, e in enumerate(ring2[:-1]) if e in ring1]
    assert len(shared1) == len(shared2)
    assert len(shared1) > 0
    assert all(shared1[i+1] == shared1[i]+1 for i in range(len(shared1)-1))
    assert all(shared2[i+1] == shared2[i]+1 for i in range(len(shared2)-1))
    assert all(ring1[shared1[i]] == ring2[shared2[-1-i]] for i in range(len(shared1)))
    return [[ring1[:shared1[0]] + ring2[shared2[-1]:] + ring2[:shared2[0]] + ring1[shared1[-1]:]]]


PATH_TO_TESTDATA = Path(__file__).resolve().parent.parent / "testdata" / "overtourism-data"
assert PATH_TO_TESTDATA.exists()

### Indices registry

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
    variazione_percentuale = dict(
        dataset="df_tasso_variazione_pecentuale",
        title="Tasso di variazione percentuale degli arrivi di turisti",
        key="tasso_variazione_perc",
        other=["tasso_variazione_perc", "anno_2022", "anno_2023", "anno_2024"],
        alias={
            "anno":"Anno",
            "comune":"Ambito",
            "tasso_variazione_perc":"Tasso di variazione percentaule",
            "anno_2022":"Arrivi anno 2022",
            "anno_2023":"Arrivi anno 2023",
            "anno_2024":"Arrivi anno 2024"},
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
             "L'indice complessivo identifica comuni e aree in cui uno o più di questi indici assumono livelli elevanti nel panorama trentino (indicati con un numero crescente di '*\').",
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
    "flows": _diffusion_indexes,
    "overtourism": _overtourism_indexes,
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

### Index plot front-end

st.set_page_config(page_title="Indicatori", layout="wide", initial_sidebar_state="expanded")

index_classes = { _category_names[k]: _category_map[k] for k in _category_map }

tabs = st.tabs(index_classes.keys())

for tab, class_name in zip(tabs, index_classes.keys()):

    with tab:

        indexes = index_classes[class_name]

        if class_name == "Flussi":
            who = st.radio("Indicatore", ["tutti", "escursionisti", "rapporto"], horizontal=True)
            where = st.radio("Direzione", ["in", "out"], horizontal=True)
            when = st.radio("Giorni", ["feriali", "prefestivi", "festivi", "sempre"], horizontal=True)
            index_key = f'flusso_{where}_{who}_{when}'
        else:
            index_key = st.selectbox("Indice", indexes.keys(),
                                     format_func=lambda x: indexes[x]['title'],
                                     key=f"index_{class_name}",)

        index = indexes[index_key]

        dataset = index['dataset']
        title = index['title']
        key = index['key']
        other = index['other']
        alias = index['alias'] if 'alias' in index else {}
        help_text = index['help'] if 'help' in index else None
        map_geojson = index['map']['geojson']
        map_key = index['map']['key']
        map_locations_col = index['map']['locations_col']
        ticks = index['ticks'] if 'ticks' in index else None

        df = get_dataframe(dataset, local=True)

        lista_comuni = df.index.levels[0]
        lista_anni = df.index.levels[1]

        # Help
        if help_text is not None:
            with st.expander("Descrizione"):
                st.write(help_text)

        viz = st.segmented_control("Visualizzazione", ["Grafico", "Mappa"], default="Grafico",
                                   label_visibility="collapsed", key=f"viz_{class_name}")

        if viz == "Grafico":
            # Graph
            default = {"MOLVENO", "ANDALO", "Altopiano della Paganella, Piana della Rotaliana e San Lorenzo Dorsino"} & \
                set(df.index.levels[0])
            comuni = st.multiselect("Comuni", df.index.levels[0], default=default, key=f"comuni_{class_name}")

            df_toplot = df.loc[comuni].copy().reset_index()

            if df.index.levels[1].size > 1:
                mode = st.radio("Visualizzazione", ["Linea", "Barra"], horizontal=True, key=f"mode_{class_name}")
            else:
                mode = "Barra"

            if mode == "Linea":
                fig = px.line(df_toplot, x="anno", y=key, color="comune", title=title, markers=True,
                              hover_name="comune", hover_data={"anno": True, key: False, **{o:True for o in other}},
                              labels=alias)
            else:
                fig = px.bar(df_toplot, x="anno", y=key, color='comune', barmode='group',
                             hover_name="comune", hover_data={"anno": True, key: False, **{o:True for o in other}},
                             labels=alias).update_traces(marker_line_width = 1)

            fig.update_layout(
                xaxis=dict(
                    showgrid=True,
                    showticklabels=True,
                    tickmode='array',
                    tickvals=lista_anni,
                ),
                yaxis=dict(
                    showgrid=True,
                ),
            )
            if ticks is not None:
                fig.update_layout(
                    yaxis=dict(tickvals=ticks[0], ticktext=ticks[1])
                )

            st.plotly_chart(fig, key=f"graph_{class_name}")

        else:
            # Map
            if df.index.levels[1].size > 1:
                anno = st.radio("Anno", df.index.levels[1], horizontal=True, key=f"anno_{class_name}")
            else:
                anno = df.index.levels[1][0]

            df_toplot = df.xs(anno, level=1, drop_level=False).reset_index()

            geojson = json.load(open((PATH_TO_TESTDATA / map_geojson).with_suffix(".geojson")))

            fig = px.choropleth_map(
                df_toplot,
                locations=map_locations_col,
                color=key,
                geojson=geojson, featureidkey=map_key,
                hover_data={"anno": True, "comune": True, key: False, **{o:True for o in other}},
                opacity = 1,
                center = dict(lat = 46.1, lon = 11.00),
                zoom = 7.3,
                labels=alias)

            if ticks is not None:
                fig.update_layout(
                    coloraxis_colorbar=dict(
                        tickmode="array",
                        tickvals=ticks[0],
                        labelalias=dict(zip(*ticks)),
                    ),
                )

            st.plotly_chart(fig, key=f"map_{class_name}")