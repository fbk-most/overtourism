<!-- SPDX-License-Identifier: Apache-2.0 -->

# Overtourism Backend Architecture

This document describes the layered architecture of the `overtourism` package's
digital-twin backend — how the computation layer for the Fazzon and Molveno
overtourism models is organized, why it is split the way it is, and what is
still missing before a production frontend (FastAPI + a real UI) can be built
on top of it.

**Status**: Layers 1–3 and the Streamlit dev/test tooling (Layer 5, partial)
are implemented for Fazzon and Molveno. Layer 4 (application backend) and a
production Layer 5 (FastAPI, a real UI) do not exist yet *for these models* —
see [Next steps](#next-steps). Both layers already exist for the older,
Trentino-wide model this repository previously served (`overtourism.OLD/`: a
FastAPI backend and a persistence/scenario-catalogue layer, plus a separate
Angular frontend); adapting that prior work is one option worth evaluating
before building either layer from scratch — see the notes in each subsection
below.

---

## Layer architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│  LAYER 5 — Frontend                                                      │
│  Streamlit (today, dev/test only) | FastAPI + UI (next — adapt/reuse?)   │
│  Entry point lives here. Presentation only.                              │
├──────────────────────────────────────────────────────────────────────────┤
│  LAYER 4 — Application / tool backend  (next, for these models —         │
│  adapt/reuse? see overtourism.OLD)                                       │
│  Scenario catalogue · persistence · user storage · i18n                  │
├──────────────────────────────────────────────────────────────────────────┤
│  LAYER 3 — Computation backend  (model-specific, plain classes)          │
│  FazzonBackend · MolvenoBackend — no shared base class                   │
├───────────────────────────────────┬──────────────────────────────────────┤
│  LAYER 2a — overtourism.cdt_ext   │  LAYER 2b — overtourism.model.common │
│  (staged civic_digital_twins      │  (overtourism-model-family code,     │
│   extensions)                     │   not domain-agnostic)               │
│  ParameterMeta · build_scenario() │  OvertourismParameterMeta ·          │
│  · EnsembleEvaluationConfig       │  SustainabilityFieldOutput ·         │
│                                   │  OvertourismEvaluationConfig ·       │
│                                   │  shared sustainability-field math    │
├───────────────────────────────────┴──────────────────────────────────────┤
│  LAYER 1 — civic_digital_twins library  (external, read-only)            │
│  Model/@define/@inputs/@outputs · ModelOutput · EvaluationConfig ·       │
│  Scenario · CrossProductEnsemble · Evaluation                            │
└──────────────────────────────────────────────────────────────────────────┘
```

| Layer | Responsibility |
|---|---|
| 1 — `civic_digital_twins` | The external digital-twin modeling library. Read-only from this repo's point of view. |
| 2a — `overtourism.cdt_ext` | Utilities that are useful to *any* `civic_digital_twins` model, staged here only because they are not part of the published library yet. |
| 2b — `overtourism.model.common` | Code shared by the overtourism models specifically (currently Fazzon and Molveno) — array math and types that only make sense for this "2D presence-vs-presence sustainability field" model family. |
| 3 — Computation backend | One class per model (`FazzonBackend`, `MolvenoBackend`): builds the model, exposes its parameter schema, and evaluates scenarios. Frontend-agnostic — no Streamlit, FastAPI, or other UI/transport code. |
| 4 — Application backend | Not implemented for Fazzon/Molveno yet. Would own scenario persistence, saved-result storage, and any cross-session state. `overtourism.OLD` already implements this pattern for the older model — see [Next steps](#next-steps). |
| 5 — Frontend | Presentation only. Today: a Streamlit app used for development and manual testing. Next: a FastAPI service exposing the same backend over HTTP, and a real UI — both may be adaptable from `overtourism.OLD`/the old Angular frontend rather than built new. |

---

## Layer 1 — `civic_digital_twins` (external dependency)

Pinned in `pyproject.toml` as `civic-digital-twins==0.11.0`. Both `fazzon_model.py`
and `molveno_model.py` are written against the library's `@define`/`@inputs`/
`@outputs`/`compute()` model-definition API (`civic_digital_twins.dt_model.Model`
and friends) — every concern sub-model declares its inputs/outputs as typed
dataclasses and implements a single `compute()` method. `SustainabilityFieldOutput`
(§Layer 2b) subclasses the library's `ModelOutput`.

This API surface only exists from `civic-digital-twins>=0.10.0` — earlier
releases (`<0.6.0`) instead exposed an `AbstractModel`-based API that has since
been removed. There is no published version that supports both; if any other
code in this repository needs to target the older API, it cannot share a
dependency pin with `overtourism.model.*`.

---

## Layer 2a — `overtourism.cdt_ext` (staged library extensions)

**Location**: `overtourism/cdt_ext/runner_ext.py`, importable as
`overtourism.cdt_ext.runner_ext`.

Utilities that are genuinely domain-agnostic — useful to any `civic_digital_twins`
model, not just the overtourism ones — but not yet part of the published
library. Kept separate from `overtourism.model.common` (§2b) so the boundary
between "generic, could move upstream" and "overtourism-specific" stays clear;
see [Next steps](#upstreaming-cdt_ext) for the migration plan.

### `ParameterMeta`

A typed schema for describing one model parameter — the minimum needed to
**validate or reconstruct** a submitted override, not to render a widget:

```python
@dataclass
class ParameterMeta:
    name: str                 # matches index.name exactly; the boundary key
    kind: str                 # "scalar" | "categorical" | "distribution"
    distribution_family: str | None = None
    distribution_fixed_params: dict[str, Any] | None = None
    support: list[str] = field(default_factory=list)
    default: float | None = None
    default_category: str | None = None
```

Presentation fields (`label`, `description`, `unit`, UI ranges, ...) deliberately
do **not** belong here — `build_scenario()` never reads them, they only affect
widget rendering. A model-family that needs them extends via plain dataclass
inheritance — see `OvertourismParameterMeta` in `overtourism.model.common`
(§2b), the only subclass today.

`name` is kept on the object (not left to a dict key alone) so that any
`list[ParameterMeta]` view — e.g. a `Backend.parameter_schema()` return value,
or a future FastAPI `/schema` JSON array — is self-describing. Such a list is
always *derived* (`list(schema.values())`), never hand-authored separately.

### `EnsembleEvaluationConfig`

```python
@dataclass
class EnsembleEvaluationConfig(EvaluationConfig):
    ensemble_seed: int | None = None
    n_samples_per_combo: int = 1
```

Makes `CrossProductEnsemble`'s reproducibility knobs (`ensemble_seed`,
`n_samples_per_combo`) explicit, injectable config instead of hardcoded
constants. These two fields are candidates to land directly on the library's
own `EvaluationConfig` — see [Next steps](#upstreaming-cdt_ext).

### `build_scenario()`

```python
def build_scenario(
    model: Any,
    param_overrides: dict[str, Any],
    index_map: dict[str, Any],            # index.name → Index object
    spec_map: dict[str, ParameterMeta],   # index.name → ParameterMeta
    parameter_axes: list[Any] | None = None,
) -> Scenario:
```

Resolves a string-keyed `param_overrides` dict (the shape a frontend submits)
into a `Scenario`, dispatching on `spec_map[name].kind`:

- **scalar** (`float`) — passed directly as the index override
- **distribution** (`(lo, hi)` tuple) — reconstructed as a frozen `scipy.stats`
  distribution via `ParameterMeta.distribution_family`/`.distribution_fixed_params`,
  using the convention `loc = lo`, `scale = hi - lo`. This convention belongs to
  the frontends that produce `(lo, hi)` pairs, not to `DistributionIndex` itself.
- **categorical** (`str`) — passed directly as the index override
- keys absent from `param_overrides`, or not present in `index_map`/`spec_map`,
  are left unoverridden — model defaults apply

`parameter_axes` is optional — a model with no presence-variable grid to sweep
passes `None`.

There is no `ModelBackend`/`ParametricModelBackend` base class: once
`ParameterMeta` and `build_scenario()` exist, evaluating from string overrides
is a one-line call (`evaluator.evaluate(build_scenario(...), config)`), so a
wrapping ABC would add no capability. Layer 3 backends (§Layer 3) are plain
concrete classes.

---

## Layer 2b — `overtourism.model.common` (overtourism-model-family code)

**Location**: `overtourism/model/common/sustainability_field.py`, importable
as `overtourism.model.common.sustainability_field`.

Code shared by the overtourism models — currently Fazzon and Molveno. Explicitly
**not** staged in `cdt_ext`: everything here (field math, output shape, config
fields like `sample_seed`/`target_presence_samples`/`category`/`step`) only
means something for this specific "2D presence-vs-presence sustainability
field" model family, not for `civic_digital_twins` models in general.

### `OvertourismParameterMeta`

`ParameterMeta` (§2a) extended with presentation fields via plain dataclass
inheritance:

```python
@dataclass
class OvertourismParameterMeta(ParameterMeta):
    label: str = ""
    description: str = ""
    unit: str = ""
    category: str = ""
    step: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    default_range: tuple[float, float] | None = None
```

`build_scenario()` only touches the base `ParameterMeta` fields, so it works
unmodified against this (or any other) subclass.

### `OvertourismEvaluationConfig`

```python
@dataclass
class OvertourismEvaluationConfig(EnsembleEvaluationConfig):
    sample_seed: int | None = None
    target_presence_samples: int = 2000
    confidence: float = 0.8
```

Adds the presence-sampling and confidence-interval parameters that configure
`sample_across()`-based scatter-overlay sampling and the sustainability-index
confidence interval — concepts specific to this model family.

### Shared sustainability-field math

Pure array functions (field + axes + presences + confidence in; tuple/dict
out), with no model-specific coupling, used by both `FazzonBackend` and
`MolvenoBackend`:

- `compute_sustainability_field` — builds the raw `field`/`field_elements`
  arrays from an `EvaluationResult` and a model's `constraints` list. Takes
  `constraints: Iterable[Any]` (structurally typed — `.name`/`.usage`/
  `.capacity` — rather than a shared `Constraint` class, since each model
  keeps its own) and the two axis indexes directly.
- `compute_sustainable_area`
- `compute_sustainability_index_with_ci`
- `compute_sustainability_by_constraint`
- `compute_modal_lines` — per-constraint modal line via orthogonal regression
  (first principal component)

### `SustainabilityFieldOutput`

A `ModelOutput` subclass (Layer 1) defining the unified output schema for both
models — no per-model output subclass is needed since, with the math above
shared, neither model has a field to add beyond the common set:

```python
@dataclass(eq=False)
class SustainabilityFieldOutput(ModelOutput):
    field: np.ndarray                      # shape (N_x, N_y), values in [0, 1]
    field_elements: dict[str, np.ndarray]  # per-constraint fields, same shape
    x_values: np.ndarray                   # 1-D, shape (N_x,)
    y_values: np.ndarray                   # 1-D, shape (N_y,)
    x_axis_name: str
    y_axis_name: str
    samples_x: list[float]                 # presence samples, for scatter overlay
    samples_y: list[float]
    confidence: float = 0.8

    # Derived, lazily via functools.cached_property:
    #   sustainable_area, sustainability_index,
    #   sustainability_by_constraint, modal_lines
```

`to_snapshot()` returns a JSON-serialisable dict including the four derived
values — the shape a future FastAPI `/evaluate` response would return
directly (§[Next steps](#layer-5--fastapi-next)).

---

## Layer 3 — Computation backends

**Location**: `overtourism/model/fazzon/` and `overtourism/model/molveno/`.

Each model package contains:

| File | Contents |
|---|---|
| `<model>_model.py` | The model definition itself — `civic_digital_twins` sub-models, the root `Model` class, `default_inputs()`. |
| `<model>_backend.py` | `FazzonBackend`/`MolvenoBackend` — the frontend-agnostic evaluation entry point. |
| `<model>_presence_stats.py` | Calibration data (presence distributions by context) as plain Python. |
| `fazzon_scenarios.py` (Fazzon only) | Catalogue of named what-if scenarios, expressed against live `Index` objects. |

`FazzonBackend` and `MolvenoBackend` are plain, self-contained classes with no
shared base class (see the `ModelBackend` rationale in §Layer 2a) and no
runtime dependency on each other. Each backend's constructor builds its model,
an `index.name → Index` map, and an `OvertourismEvaluationConfig` with fixed
seeds and sample counts — seeds are a compute-quality concern, so they live
here, not in any frontend.

Public contract (identical shape for both):

```python
class <Model>Backend:
    def __init__(self) -> None: ...

    @property
    def model(self) -> <Model>Model:
        """The live model instance — needed by frontends that resolve
        predefined what-if scenarios against live Index objects."""

    def parameter_schema(self) -> list[OvertourismParameterMeta]:
        """Ordered, self-describing parameter schema."""

    def evaluate(self, param_overrides: dict[str, Any]) -> SustainabilityFieldOutput:
        """Evaluate the model under string-keyed parameter overrides."""
```

`evaluate()` builds a `Scenario` via `build_scenario()` (§Layer 2a), runs a
seeded `CrossProductEnsemble`/`Evaluation` over the model's two presence-variable
axes, and returns a `SustainabilityFieldOutput` computed via the shared field
math (§Layer 2b). Grid-resolution parameters (axis max/sample-count) are
backend constructor arguments, not evaluation config — they are structural
choices about the axis grid, not per-evaluation quality knobs.

---

## Layer 5 (today) — Streamlit dev/test tooling

**Location**: `overtourism/dt_studio/`, isolated from the computation backend
— nothing under `overtourism.model.*` imports Streamlit.

- `overtourism/dt_studio/dashboard/` — the generic, model-agnostic Streamlit
  shell: `adapter.py` defines the `OvertourismAdapter` ABC and the `PlotData`/
  `ScenarioDef` data types; `app.py`'s `run_dashboard()` renders the sidebar
  widgets, field plot, KPI panel, and scenario selector for any adapter.
- `overtourism/dt_studio/fazzon_dashboard.py` / `molveno_dashboard.py` — the
  per-model entry points. Each defines a concrete `OvertourismAdapter`
  subclass wrapping the corresponding `Backend`, and is run directly with:

  ```bash
  uv run streamlit run overtourism/dt_studio/fazzon_dashboard.py
  uv run streamlit run overtourism/dt_studio/molveno_dashboard.py
  ```

`OvertourismAdapter.run(param_overrides)` calls `backend.evaluate(param_overrides)`
and maps the resulting `SustainabilityFieldOutput` onto `PlotData` (field names
are aligned except `x_axis_name`/`y_axis_name` → `x_label`/`y_label`).
`predefined_scenarios()` returns UI-facing `ScenarioDef` objects — scenario
descriptions are presentation content and intentionally do not travel through
the computation backend.

This tooling is for development and manual testing only; it is not the
production frontend (see [Next steps](#layer-5--fastapi-next)).

---

## Next steps

### Layer 4 — application backend

Not implemented for Fazzon/Molveno yet. Needed before a production frontend
can be stateful across requests/sessions:

| Concern | Description |
|---|---|
| Scenario catalogue | Load named parameter configurations; validate overrides against `parameter_schema()`. |
| Result persistence | Store `SustainabilityFieldOutput.to_snapshot()` output keyed by scenario + params. |
| User scenario storage | Save/name/retrieve custom parameter sets across sessions. |
| i18n | Translate `OvertourismParameterMeta.label`/`.description` if needed. |

This layer is the single call target for every Layer 5 frontend: a FastAPI
server *is* this layer plus HTTP routing; the current Streamlit dashboards use
`st.session_state` as a temporary, in-process, non-persistent stand-in for it.

**Adapt/reuse candidate**: `overtourism.OLD/backend/managers.py` and
`overtourism.OLD/dt_studio/manager/` (`ProblemManager`, `ScenarioManager`,
local/SQL-backed stores, a metadata manager) already implement exactly this
set of responsibilities — scenario CRUD, saved-result persistence, index-diff
tracking — for the older Trentino-wide model this repository used to serve.
It is tied to that older model's shape (YAML-driven problem/scenario configs,
optional digitalhub-platform data loading) and to the pre-`0.10.0`
`civic_digital_twins` API (§Layer 1), so it cannot be imported unmodified, but
its persistence/store abstractions (`overtourism.OLD/dt_studio/manager/stores/`)
and scenario-manager shape are a reasonable starting point to adapt rather
than designing Layer 4 from a blank page.

### Layer 5 — FastAPI

Not implemented for Fazzon/Molveno yet. A REST layer over the Layer 3
backends, mirroring the shape `SustainabilityFieldOutput` and
`OvertourismParameterMeta` already have:

| Endpoint | Description |
|---|---|
| `GET /schema` | `backend.parameter_schema()` as a JSON array. |
| `GET /scenarios` | Scenario catalogue, from Layer 4. |
| `POST /evaluate` | `{param_overrides: {...}}` → `backend.evaluate(...).to_snapshot()`. |
| `GET /results/{id}` | Persisted result, from Layer 4. |

**Adapt/reuse candidate**: `overtourism.OLD/backend/api/` already implements a
working FastAPI service for the older model (`main.py` — app setup, CORS,
router registration; `scenario.py`/`problem.py`/`widget.py`/`proposal.py`/
`data.py` — the routers themselves). The route shapes above are not a
one-to-one match with the old routers (those are keyed by `problem_id`/
`scenario_id` against Layer 4's `ProblemManager`, these are keyed by model),
but the FastAPI app scaffolding, CORS setup, and router-per-concern structure
are directly reusable patterns.

### Layer 5 — production UI

Not implemented for Fazzon/Molveno yet — the Streamlit dashboards (above) are
dev/test tooling, not this. The previous production UI for the older model was
a separate Angular single-page application
(`https://github.com/tn-aixpa/overtourism-frontend`, not part of this repo),
served against the Layer 5 FastAPI backend. Whether the new models get a
similarly separate Angular/SPA frontend, are folded into that existing
frontend, or take a different approach is an open question — worth deciding
alongside the Layer 5 FastAPI design above, since the two are coupled (the
frontend consumes exactly the endpoints this layer exposes).

### Layer 5 — CLI (future)

Not designed yet, and no prior implementation to draw from. Would invoke
Layer 4 as a plain library call, same as any other frontend.

### Upstreaming `cdt_ext`

`overtourism.cdt_ext.runner_ext` (§Layer 2a) is a staging area, not a
permanent home: `ParameterMeta`, `build_scenario()`, and
`EnsembleEvaluationConfig` are all judged to be useful to any
`civic_digital_twins` model, not just the overtourism ones. When equivalents
land in the `civic_digital_twins` library itself, drop the local copies here
and import from the library instead — `overtourism.model.common` and the
Layer 3 backends should need no other change, since they only depend on
`cdt_ext`'s public names, not its location.
