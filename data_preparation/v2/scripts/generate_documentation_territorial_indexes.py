#!/usr/bin/env python3
"""
generate_context.py
--------------------
Legge un file Python che definisce classi `Indicator` e `Phenomenon`
(nello stile del modulo `overtourism`) e genera un documento Markdown
in italiano che descrive, per ogni indicatore:

  - nome e descrizione (se presenti nel codice)
  - la formula di calcolo (in linguaggio naturale quando possibile,
    altrimenti come frammento di codice)
  - i "fenomeni" (le grandezze) coinvolti, con la colonna sorgente,
    il tipo di aggregazione e la risoluzione spazio-temporale

Il file NON viene importato: viene analizzato staticamente con il
modulo `ast`, quindi funziona anche senza le dipendenze del progetto
originale (pandas, numpy, i moduli custom `Indicator`/`Phenomenon`, ecc.)
e senza i dati veri e propri.

Uso:
    python generate_context.py path/al/file.py -o output.md
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Etichette leggibili in italiano per i nomi "tecnici" dei fenomeni/campi
# usati più di frequente. Se un nome non è in questo dizionario, viene
# comunque reso leggibile ("extra_beds" -> "extra beds").
# ---------------------------------------------------------------------------
ITALIAN_LABELS = {
    "beds": "posti letto totali",
    "extra_beds": "posti letto non convenzionali",
    "population": "popolazione residente",
    "presences": "presenze turistiche",
    "presenze_vodafone": "presenze rilevate da rete mobile (Vodafone)",
    "presenze_alb": "presenze ufficiali alberghiere",
    "presenze_xalb": "presenze ufficiali extra-alberghiere",
    "Facilities_total": "numero totale di strutture ricettive",
    "extra_Facilities": "numero di strutture non convenzionali",
}

AGG_LABELS = {
    "sum": "somma",
    "mean": "media",
    "max": "massimo",
    "min": "minimo",
}

TEMPORAL_LABELS = {
    "daily": "giornaliera",
    "yearly": "annuale",
}

SPATIAL_LABELS = {
    "comune": "comunale",
}

STRATEGY_LABELS = {
    "identity": "valore rilevato direttamente, senza trasformazioni",
    "constant": "valore costante propagato su tutto il periodo",
}


def humanize(name: str) -> str:
    """Fallback per rendere leggibile un nome tecnico non mappato."""
    if name in ITALIAN_LABELS:
        return ITALIAN_LABELS[name]
    return name.replace("_", " ").strip()


# ---------------------------------------------------------------------------
# Strutture dati intermedie
# ---------------------------------------------------------------------------


@dataclass
class PhenomenonDef:
    class_name: str
    default_name: str | None = None
    docstring: str | None = None
    temporal_resolution: str | None = None
    temporal_strategy: str | None = None
    spatial_resolution: str | None = None
    spatial_strategy: str | None = None
    default_col: str | None = None
    agg: str | None = None


@dataclass
class PhenomenonUsage:
    class_name: str
    effective_name: str
    col: str | None = None


@dataclass
class IndicatorDef:
    class_name: str
    name: str | None = None
    description: str | None = None
    docstring: str | None = None
    phenomena: list[PhenomenonUsage] = field(default_factory=list)
    combinator_kind: str = "unknown"  # "divide" | "custom" | "unknown"
    combinator_args: tuple[str, str] | None = None
    combinator_method_name: str | None = None
    combinator_source: str | None = None  # snippet of the custom formula


# ---------------------------------------------------------------------------
# Helper AST
# ---------------------------------------------------------------------------


def _literal_or_none(node: ast.AST | None):
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _get_class_str_attr(class_node: ast.ClassDef, attr: str) -> str | None:
    for stmt in class_node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == attr:
                    val = _literal_or_none(stmt.value)
                    if isinstance(val, str):
                        return val
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name) and stmt.target.id == attr:
                val = _literal_or_none(stmt.value)
                if isinstance(val, str):
                    return val
    return None


def _get_docstring(class_node: ast.ClassDef) -> str | None:
    return ast.get_docstring(class_node)


def _find_init(class_node: ast.ClassDef) -> ast.FunctionDef | None:
    for stmt in class_node.body:
        if isinstance(stmt, ast.FunctionDef) and stmt.name == "__init__":
            return stmt
    return None


def _default_for_param(init_node: ast.FunctionDef, param_name: str):
    """Return the literal default value for a given __init__ parameter, if any."""
    args = init_node.args
    all_args = args.args
    defaults = args.defaults
    # map positional args (excluding self) to defaults, right-aligned
    positional = all_args[1:]  # drop self
    n_defaults = len(defaults)
    n_positional = len(positional)
    default_map = {}
    for i, arg in enumerate(positional[n_positional - n_defaults :]):
        default_map[arg.arg] = defaults[i]
    if param_name in default_map:
        return _literal_or_none(default_map[param_name])
    # keyword-only args
    for kwarg, kwdefault in zip(args.kwonlyargs, args.kw_defaults):
        if kwarg.arg == param_name and kwdefault is not None:
            return _literal_or_none(kwdefault)
    return None


def _find_super_init_call(init_node: ast.FunctionDef) -> ast.Call | None:
    for node in ast.walk(init_node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "__init__" and isinstance(node.func.value, ast.Call):
                if (
                    isinstance(node.func.value.func, ast.Name)
                    and node.func.value.func.id == "super"
                ):
                    return node
    return None


def _kwarg_value(call: ast.Call, key: str):
    for kw in call.keywords:
        if kw.arg == key:
            return _literal_or_none(kw.value)
    return None


# ---------------------------------------------------------------------------
# Parsing dei Phenomenon
# ---------------------------------------------------------------------------


def parse_phenomenon_class(class_node: ast.ClassDef) -> PhenomenonDef:
    pdef = PhenomenonDef(class_name=class_node.name)
    pdef.docstring = _get_docstring(class_node)
    pdef.default_name = _get_class_str_attr(class_node, "name")
    pdef.temporal_resolution = _get_class_str_attr(class_node, "temporal_resolution")
    pdef.temporal_strategy = _get_class_str_attr(class_node, "temporal_strategy")
    pdef.spatial_resolution = _get_class_str_attr(class_node, "spatial_resolution")
    pdef.spatial_strategy = _get_class_str_attr(class_node, "spatial_strategy")

    init_node = _find_init(class_node)
    if init_node:
        default_col = _default_for_param(init_node, "col")
        if isinstance(default_col, str):
            pdef.default_col = default_col
        # find super().__init__(source, col, agg="...") call to read agg default
        super_call = _find_super_init_call(init_node)
        if super_call:
            agg_val = _kwarg_value(super_call, "agg")
            if isinstance(agg_val, str):
                pdef.agg = agg_val
    return pdef


# ---------------------------------------------------------------------------
# Parsing degli Indicator
# ---------------------------------------------------------------------------


def _resolve_phenomenon_call(
    call: ast.Call, phenomenon_defs: dict[str, PhenomenonDef]
) -> PhenomenonUsage | None:
    if not isinstance(call.func, ast.Name):
        return None
    class_name = call.func.id
    pdef = phenomenon_defs.get(class_name)

    # effective name: explicit name= kwarg wins, else class default
    name_kw = _kwarg_value(call, "name")
    effective_name = (
        name_kw if isinstance(name_kw, str) else (pdef.default_name if pdef else None)
    )
    if effective_name is None:
        effective_name = class_name

    # effective col: explicit col= kwarg, else positional 2nd arg, else class default
    col_kw = _kwarg_value(call, "col")
    col = col_kw
    if col is None and len(call.args) >= 2:
        col = _literal_or_none(call.args[1])
    if col is None and pdef:
        col = pdef.default_col

    return PhenomenonUsage(
        class_name=class_name, effective_name=effective_name, col=col
    )


def _find_phenomena_list(init_node: ast.FunctionDef) -> ast.List | None:
    for node in ast.walk(init_node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            # super().__init__(phenomena=[...], combinator=...)
            for kw in node.keywords:
                if kw.arg == "phenomena" and isinstance(kw.value, ast.List):
                    return kw.value
    return None


def _find_combinator(init_node: ast.FunctionDef):
    for node in ast.walk(init_node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            for kw in node.keywords:
                if kw.arg == "combinator":
                    return kw.value
    return None


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "<espressione non interpretabile>"


def parse_indicator_class(
    class_node: ast.ClassDef, phenomenon_defs: dict[str, PhenomenonDef]
) -> IndicatorDef:
    idef = IndicatorDef(class_name=class_node.name)
    idef.docstring = _get_docstring(class_node)
    idef.name = _get_class_str_attr(class_node, "name")
    idef.description = _get_class_str_attr(class_node, "description")

    init_node = _find_init(class_node)
    if init_node is None:
        return idef

    phen_list = _find_phenomena_list(init_node)
    if phen_list is not None:
        for elt in phen_list.elts:
            if isinstance(elt, ast.Call):
                usage = _resolve_phenomenon_call(elt, phenomenon_defs)
                if usage:
                    idef.phenomena.append(usage)
            elif (
                isinstance(elt, ast.Attribute)
                and isinstance(elt.value, ast.Name)
                and elt.value.id == "self"
            ):
                # e.g. self._phenom built earlier in __init__ - try to resolve it
                # by scanning the init body for an assignment to that attribute
                target_attr = elt.attr
                for stmt in ast.walk(init_node):
                    if isinstance(stmt, ast.Assign):
                        for t in stmt.targets:
                            if (
                                isinstance(t, ast.Attribute)
                                and t.attr == target_attr
                                and isinstance(stmt.value, ast.Call)
                            ):
                                usage = _resolve_phenomenon_call(
                                    stmt.value, phenomenon_defs
                                )
                                if usage:
                                    idef.phenomena.append(usage)

    combinator_node = _find_combinator(init_node)
    if combinator_node is not None:
        if isinstance(combinator_node, ast.Call) and isinstance(
            combinator_node.func, ast.Attribute
        ):
            # self.divide("a", "b")
            if combinator_node.func.attr == "divide" and len(combinator_node.args) == 2:
                a = _literal_or_none(combinator_node.args[0])
                b = _literal_or_none(combinator_node.args[1])
                if isinstance(a, str) and isinstance(b, str):
                    idef.combinator_kind = "divide"
                    idef.combinator_args = (a, b)
            else:
                idef.combinator_kind = "custom"
                idef.combinator_method_name = combinator_node.func.attr
        elif isinstance(combinator_node, ast.Attribute) and isinstance(
            combinator_node.value, ast.Name
        ):
            # combinator=self.compute_hidden_factor  (method reference, not called here)
            idef.combinator_kind = "custom"
            idef.combinator_method_name = combinator_node.attr

    # if custom, try to locate the referenced method in the class and grab
    # its `return` expression as a formula snippet
    if idef.combinator_kind == "custom" and idef.combinator_method_name:
        for stmt in class_node.body:
            if (
                isinstance(stmt, ast.FunctionDef)
                and stmt.name == idef.combinator_method_name
            ):
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.Return) and sub.value is not None:
                        idef.combinator_source = _unparse(sub.value)
                        break

    return idef


# ---------------------------------------------------------------------------
# Rendering Markdown (italiano)
# ---------------------------------------------------------------------------


def render_phenomenon_line(
    usage: PhenomenonUsage, phenomenon_defs: dict[str, PhenomenonDef]
) -> str:
    pdef = phenomenon_defs.get(usage.class_name)
    label = humanize(usage.effective_name)
    parts = [f"**{label}** (`{usage.effective_name}`)"]

    details = []
    if usage.col:
        details.append(f"colonna sorgente `{usage.col}`")
    if pdef and pdef.agg:
        details.append(f"aggregazione: {AGG_LABELS.get(pdef.agg, pdef.agg)}")
    if pdef and pdef.temporal_resolution:
        res = TEMPORAL_LABELS.get(pdef.temporal_resolution, pdef.temporal_resolution)
        strat = STRATEGY_LABELS.get(
            pdef.temporal_strategy, pdef.temporal_strategy or ""
        )
        details.append(f"risoluzione temporale {res} ({strat})")
    if pdef and pdef.spatial_resolution:
        res = SPATIAL_LABELS.get(pdef.spatial_resolution, pdef.spatial_resolution)
        details.append(f"risoluzione spaziale {res}")

    line = "- " + parts[0]
    if details:
        line += " — " + "; ".join(details)
    return line


def render_formula(idef: IndicatorDef) -> str:
    if idef.combinator_kind == "divide" and idef.combinator_args:
        a, b = idef.combinator_args
        return f"**Formula:** rapporto tra *{humanize(a)}* e *{humanize(b)}*  \n`{a} / {b}`"
    if idef.combinator_kind == "custom":
        method = idef.combinator_method_name or "metodo personalizzato"
        text = f"**Formula:** calcolata con una logica personalizzata (`{method}`)."
        if idef.combinator_source:
            text += f"\n\n```python\n{idef.combinator_source}\n```"
        return text
    return "**Formula:** non determinabile automaticamente dal codice sorgente."


def render_report(
    indicators: list[IndicatorDef],
    phenomenon_defs: dict[str, PhenomenonDef],
    source_file: str,
) -> str:
    lines: list[str] = []

    # Title
    lines.append("# Documentazione indici territoriali")
    lines.append("")
    lines.append("")

    # Introduction
    lines.append(
        "L'idea del framework è poter inserire dati sorgente arbitrari in un'unica forma canonica standardizzata."
    )
    lines.append(
        "I dati possono in seguito essere interpretati per rispondere a diverse esigenze di visualizzazione: un valore su una mappa, una serie temporale in un grafico."
    )
    lines.append("Due classi svolgono tutto il lavoro:")
    lines.append(
        "**Fenomeno**: incapsula una singola fonte dati (es. 'posti letto per comune per anno', 'presenze da rete mobile per comune per giorno'). Un **Indice** territoriale può a sua volta essere usato come *fenomeno* di un altro Indice, per costruire macro-indicatori a partire da più sotto-indicatori."
    )
    lines.append(
        "**Indice** (territoriale): possiede una lista di **Fenomeni** più una funzione combinatore che trasforma i loro valori allineati in un unico INDICE (es. posti letto ÷ popolazione). Gestisce inoltre tutta la logica a tempo di interrogazione (es: filtraggio per data, aggregazione, ecc.)"
    )
    lines.append("")
    lines.append("")

    lines.append(
        "Tutto ciò che è territoriale (quali comuni sono visibili, raggruppamento per comune o per macro-area) è gestito da esternamente: un Indice non conosce mai permessi o granularità spaziale."
    )

    lines.append("")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## Glossario")
    lines.append("")
    lines.append("")
    lines.append("| Termine | Significato |")
    lines.append("|---|---|")
    lines.append(
        "| **Fenomeno** | classe che incapsula una singola fonte di dati grezzi|"
    )
    lines.append(
        "| **Indice** | classe che combina più fenomeni (o altri indicatori) tramite una funzione *combinatore*, restituendo l'`INDICE` finale |"
    )
    lines.append(
        "| **combinatore** | la funzione che trasforma le colonne dei fenomeni nell'`INDICE` |"
    )
    lines.append(
        "| **macro area** | un gruppo di comuni con un nome (provincia / APT / ambito turistico) |"
    )

    lines.append("")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Indice
    lines.append(f"Numero di indicatori attualmente disponibili: **{len(indicators)}**")
    lines.append("")
    for idef in indicators:
        title = idef.name or idef.class_name
        anchor = title.lower()
        anchor = anchor.replace("'", "").replace("(", "").replace(")", "")
        anchor = anchor.replace(" ", "-")
        lines.append(f"- [{title}](#{anchor})")
    lines.append("")
    lines.append("---")
    lines.append("")

    for idef in indicators:
        title = idef.name or idef.class_name
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"*Classe Python: `{idef.class_name}`*")
        lines.append("")
        if idef.description:
            lines.append(idef.description)
            lines.append("")
        elif idef.docstring:
            lines.append(idef.docstring)
            lines.append("")

        lines.append(render_formula(idef))
        lines.append("")

        if idef.phenomena:
            lines.append("**Dati utilizzati:**")
            lines.append("")
            for usage in idef.phenomena:
                lines.append(render_phenomenon_line(usage, phenomenon_defs))
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def analyze_file(path: Path) -> tuple[list[IndicatorDef], dict[str, PhenomenonDef]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))

    phenomenon_defs: dict[str, PhenomenonDef] = {}
    indicator_class_nodes: list[ast.ClassDef] = []

    # first pass: classify classes as Phenomenon or Indicator based on base class name
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            base_names = [b.id for b in node.bases if isinstance(b, ast.Name)]
            if "Phenomenon" in base_names:
                phenomenon_defs[node.name] = parse_phenomenon_class(node)
            elif "Indicator" in base_names:
                indicator_class_nodes.append(node)

    indicators = [
        parse_indicator_class(n, phenomenon_defs) for n in indicator_class_nodes
    ]
    return indicators, phenomenon_defs


def main():
    base_dir = Path(__file__).resolve().parent

    input_file = (
        base_dir
        / "../../../overtourism/overtourism/backend_extension/models/trentino_indicators.py"
    ).resolve()

    print(input_file)

    indicators, phenomenon_defs = analyze_file(input_file)
    report = render_report(indicators, phenomenon_defs, "indici_territoriali")

    output = Path("indici territoriali.md")
    output.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
