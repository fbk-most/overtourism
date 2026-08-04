# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import dataclasses
import functools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from civic_digital_twins.dt_model import (
    CrossProductEnsemble,
    Evaluation,
    EvaluationResult,
    sample_across,
)
from civic_digital_twins.dt_model.model.index import (
    Distribution,
    DistributionIndex,
    Index,
)
from civic_digital_twins.dt_model.simulation.evaluation import _get_default_executor
from civic_digital_twins.dt_model.simulation.runner import (
    EvaluationConfig,
    ModelEvaluator,
    ModelOutput,
    ModelRunHandle,
)
from civic_digital_twins.dt_model.simulation.scenario import Scenario as CDTScenario
from scipy import interpolate, ndimage, stats

from overtourism.overtourism.molveno.molveno_model import MolvenoModel

# Type alias used by Managers
ArrangeDataFn = Callable[[Any, list[str] | None], dict]

# EN → IT constraint name mapping (remove when frontend uses English)
CONSTRAINT_NAME_IT: dict[str, str] = {
    "parking": "parcheggi",
    "beach": "spiaggia",
    "accommodation": "alberghi",
    "food": "ristoranti",
}


def _translate_constraint_names(data: dict[str, Any]) -> dict[str, Any]:
    """Translate English constraint names to Italian in the result dict."""
    tr = CONSTRAINT_NAME_IT

    def _translate_keys(d: dict) -> dict:
        return {tr.get(k, k): v for k, v in d.items()}

    for field in (
        "uncertainty_by_constraint",
        "constraint_curves",
        "usage_by_constraint",
        "usage_uncertainty_by_constraint",
        "capacity_mean_by_constraint",
    ):
        if field in data:
            data[field] = _translate_keys(data[field])

    kpis = data.get("kpis", {})
    new_kpis: dict[str, Any] = {}
    for k, v in kpis.items():
        if k == "critical constraint" and isinstance(v, dict):
            v = {**v, "name": tr.get(v.get("name", ""), v.get("name", ""))}
            new_kpis[k] = v
        elif k.startswith("constraint level "):
            suffix = k.removeprefix("constraint level ")
            new_kpis[f"constraint level {tr.get(suffix, suffix)}"] = v
        else:
            new_kpis[k] = v
    data["kpis"] = new_kpis

    return data


def arrange_data(
    data: MolvenoOutput,
    api_version: Literal["v2"] = "v2",
    as_snapshot: bool = True,
    fields: list[str] | None = None,
) -> dict:
    """Transform a :class:`MolvenoOutput` into the API response format.

    Parameters
    ----------
    data:
        The :class:`MolvenoOutput` object returned by the evaluator.
    api_version:
        ``"v1"`` returns the legacy nested ``points`` structure consumed by the
        v1 frontend.  ``"v2"`` returns the translated snapshot dict directly,
        optionally filtered to *fields*.
    fields:
        For ``api_version="v2"`` only: list of top-level snapshot keys to
        include.  When *None* all keys are returned.
    """
    snapshot = _translate_constraint_names(data.to_snapshot())

    if fields is not None:
        return {k: snapshot[k] for k in fields if k in snapshot}
    if as_snapshot:
        return snapshot

    # Arange for frontend ───────────────────
    d: dict = {}  # type: ignore[unreachable]
    d["points"] = {}
    d["points"]["uncertainty"] = []
    d["points"]["uncertainty_by_constraint"] = {
        k: [] for k in snapshot["uncertainty_by_constraint"]
    }

    for tourists, excursionists, index, usage, usage_unc in zip(
        snapshot["sample_x"],
        snapshot["sample_y"],
        snapshot["uncertainty"],
        snapshot["usage"],
        snapshot["usage_uncertainty"],
    ):
        d["points"]["uncertainty"].append(
            {
                "tourists": tourists,
                "excursionists": excursionists,
                "index": index,
                "usage": usage,
                "usage_uncertainty": usage_unc,
            }
        )

    for k, v in snapshot["uncertainty_by_constraint"].items():
        for tourists, excursionists, index, usage, usage_unc in zip(
            snapshot["sample_x"],
            snapshot["sample_y"],
            v,
            snapshot["usage_by_constraint"][k],
            snapshot["usage_uncertainty_by_constraint"][k],
        ):
            d["points"]["uncertainty_by_constraint"][k].append(
                {
                    "tourists": tourists,
                    "excursionists": excursionists,
                    "index": index,
                    "usage": usage,
                    "usage_uncertainty": usage_unc,
                }
            )

    d["kpis"] = snapshot["kpis"]
    d["x_max"] = snapshot["x_max"]
    d["y_max"] = snapshot["y_max"]
    d["capacity_mean"] = snapshot["capacity_mean"]
    d["capacity_mean_by_constraint"] = snapshot["capacity_mean_by_constraint"]
    d["constraint_curves"] = snapshot["constraint_curves"]
    return d


# ──────────────────────────────────────────────
# Config / dataclass helpers
# ──────────────────────────────────────────────


@dataclass
class MolvenoConfig(EvaluationConfig):
    """Evaluation config carrying an optional situation filter."""

    context_id: str | None = None


@dataclass
class Situation:
    """A named context-variable filter for evaluation."""

    name: str | None
    description: str
    values: dict


@dataclass
class Grid:
    """Evaluation grid configuration."""

    x_max: float
    y_max: float
    n_samples: int


@dataclass
class Sampler:
    """Presence sampling configuration."""

    target_presence_samples: int


# ──────────────────────────────────────────────
# Index-diff helpers
# ──────────────────────────────────────────────


def _get_diff_str(
    idx: Index,
    old_val: Any,
    new_val: Any,
    *,
    percentage_scale: bool = False,
) -> str | None:
    """Return a human-readable diff string, or None when unchanged."""

    def tostr(v: Any) -> str:
        if percentage_scale and isinstance(v, (int, float)):
            v = v * 100.0
        if isinstance(v, (int, float)) and v == int(v):
            return str(int(v))
        return str(v)

    if isinstance(idx, DistributionIndex):
        old_params = idx.params
        if isinstance(new_val, dict):
            new_params = new_val
        elif hasattr(new_val, "kwds"):
            new_params = {**new_val.kwds}
            if new_val.args:
                import inspect

                dist_params = inspect.signature(new_val.dist._parse_args).parameters
                for name_param, val in zip(dist_params, new_val.args):
                    new_params[name_param] = val
        else:
            return None
        if old_params == new_params:
            return None
        if "loc" in old_params and "scale" in old_params:
            old_range = (
                f"{tostr(old_params['loc'])}-"
                f"{tostr(old_params['loc'] + old_params['scale'])}"
            )
            new_loc = new_params.get("loc", old_params["loc"])
            new_scale = new_params.get("scale", old_params["scale"])
            new_range = f"{tostr(new_loc)}-{tostr(new_loc + new_scale)}"
            return f"{old_range} -> {new_range}"
        return f"{old_params} -> {new_params}"

    if old_val == new_val:
        return None
    return f"{tostr(old_val)} -> {tostr(new_val)}"


def _find_index_by_name(
    model: MolvenoModel,
    name: str,
    index_name_map: dict[str, str] | None = None,
) -> Index | None:
    model_name = (index_name_map or {}).get(name, name)
    for idx in model.indexes:
        if isinstance(idx, Index) and idx.name == model_name:
            return idx
    return None


# ──────────────────────────────────────────────
# Compute functions
# ──────────────────────────────────────────────


def compute_sustainable_area(
    field: np.ndarray, tt: np.ndarray, ee: np.ndarray
) -> float:
    """Compute the sustainable area under the sustainability field."""
    return field.sum() * functools.reduce(
        lambda x, y: x * y,
        [axis.max() / (axis.size - 1) + 1 for axis in (tt, ee)],
    )


def compute_sustainability_index_with_ci(
    field: np.ndarray,
    tt: np.ndarray,
    ee: np.ndarray,
    presences: list,
    confidence: float = 0.9,
) -> tuple[float, float]:
    """Return the sustainability index and its confidence half-width."""
    index = interpolate.interpn(
        (tt, ee), field, np.array(presences), bounds_error=False, fill_value=0.0
    )
    m, se = np.mean(index), stats.sem(index)
    h = se * stats.t.ppf((1 + confidence) / 2.0, index.size - 1)
    return float(m), float(h)


def compute_sustainability_by_constraint(
    field_elements: dict,
    tt: np.ndarray,
    ee: np.ndarray,
    presences: list,
    confidence: float = 0.9,
) -> dict[str, tuple[float, float]]:
    """Return (sustainability_index, CI_half_width) per constraint name."""
    result = {}
    for key, fe in field_elements.items():
        index = interpolate.interpn(
            (tt, ee), fe, np.array(presences), bounds_error=False, fill_value=0.0
        )
        m, se = np.mean(index), stats.sem(index)
        h = se * stats.t.ppf((1 + confidence) / 2.0, index.size - 1)
        result[key] = (float(m), float(h))
    return result


def compute_modal_lines(
    field_elements: dict,
    tt: np.ndarray,
    ee: np.ndarray,
) -> dict[str, tuple[tuple, tuple]]:
    """Compute the modal line per constraint via orthogonal regression (first PC)."""
    bounds = [tt.max(), ee.max()]
    modal_lines = {}
    for key, fe in field_elements.items():
        matrix = (fe <= 0.5) & (
            (ndimage.shift(fe, (0, 1)) > 0.5)
            | (ndimage.shift(fe, (0, -1)) > 0.5)
            | (ndimage.shift(fe, (1, 0)) > 0.5)
            | (ndimage.shift(fe, (-1, 0)) > 0.5)
        )
        yi, xi = np.nonzero(matrix)
        if len(yi) < 3:
            continue
        pts = np.stack([tt[yi], ee[xi]], axis=1)
        centroid = pts.mean(axis=0)
        _, _, Vt = np.linalg.svd(pts - centroid, full_matrices=False)
        direction = Vt[0]
        t_lo, t_hi = -np.inf, np.inf
        for i, bound in enumerate(bounds):
            if abs(direction[i]) > 1e-10:
                ta = -centroid[i] / direction[i]
                tb = (bound - centroid[i]) / direction[i]
                t_lo = max(t_lo, min(ta, tb))
                t_hi = min(t_hi, max(ta, tb))
        if t_lo >= t_hi:
            continue
        p0 = centroid + t_lo * direction
        p1 = centroid + t_hi * direction
        modal_lines[key] = ((p0[0], p1[0]), (p0[1], p1[1]))
    return modal_lines


def _presence_transformation(
    presence: float,
    reduction_factor: float,
    saturation_level: float,
    sharpness: int = 3,
) -> float:
    """Apply the presence saturation transformation used for scatter-plot samples."""
    tmp = presence * reduction_factor
    return (
        tmp
        * saturation_level
        / ((tmp**sharpness + saturation_level**sharpness) ** (1 / sharpness))
    )


def _get_effective_capacity_value(constraint: Any, scenario: Any = None) -> Any:
    if scenario is None:
        return constraint.capacity.value
    return scenario.overrides.get(constraint.capacity, constraint.capacity.value)


def compute_sustainability_field(
    model: MolvenoModel,
    result: Any,
    scenario: Any = None,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Compute the sustainability field and per-constraint field elements."""
    field = np.ones(
        (
            result.parameter_values[model.pv_tourists].size,
            result.parameter_values[model.pv_excursionists].size,
        )
    )
    field_elements: dict = {}
    for c in model.constraints:
        usage = np.broadcast_to(result[c.usage], result.full_shape)
        cap_value = _get_effective_capacity_value(c, scenario)
        if isinstance(cap_value, Distribution):
            mask = (1.0 - cap_value.cdf(usage)).astype(float)
        else:
            if scenario is not None and c.capacity in scenario.overrides:
                cap = np.broadcast_to(cap_value, result.full_shape)
            else:
                cap = np.broadcast_to(result[c.capacity], result.full_shape)
            mask = (usage <= cap).astype(float)
        field_elem = np.tensordot(mask, result.weights, axes=([-1], [0]))
        field_elements[c.name] = field_elem
        field *= field_elem
    return field, field_elements


def _usage_uncertainty_from_params(
    params: dict[str, float], usage: list[int]
) -> list[float]:
    """Compute per-sample usage uncertainty from capacity normal params."""
    capacity = stats.norm(loc=params["loc"], scale=params["scale"])
    capacity_mean = float(capacity.mean())
    y_max = max(1, int(max(max(usage, default=0), capacity_mean) * 1.2))
    cap_cdf = [float(capacity.cdf(y)) for y in range(y_max)]
    heatmap_y = np.linspace(0, y_max, len(cap_cdf))
    result = []
    for u in usage:
        idx = int(np.abs(heatmap_y - u).argmin())
        result.append(float(f"{cap_cdf[idx]:.4f}"))
    return result


# ──────────────────────────────────────────────
# MolvenoOutput
# ──────────────────────────────────────────────


@dataclass(eq=False)
class MolvenoOutput(ModelOutput):
    """Evaluation output for the Molveno overtourism model.

    Parameters
    ----------
    field : np.ndarray
        Sustainability field of shape ``(N_t, N_e)``.
    field_elements : dict
        Per-constraint field arrays ``{name: np.ndarray}``.
    tt : np.ndarray
        Tourist parameter axis (1-D, shape ``(N_t,)``).
    ee : np.ndarray
        Excursionist parameter axis (1-D, shape ``(N_e,)``).
    sample_tourists : list[float]
        Transformed tourist presence samples for scatter-plot overlays.
    sample_excursionists : list[float]
        Transformed excursionist presence samples for scatter-plot overlays.
    usage_fields : dict[str, np.ndarray]
        Per-constraint usage field arrays ``{name: (N_t, N_e)}``.
    capacity_distributions : dict[str, dict[str, float]]
        Normal distribution params per constraint ``{name: {"loc": float, "scale": float}}``.
    """

    field: np.ndarray
    field_elements: dict
    tt: np.ndarray
    ee: np.ndarray
    sample_tourists: list[float]
    sample_excursionists: list[float]
    confidence: float = 0.8
    usage_fields: dict[str, np.ndarray] = dataclasses.field(default_factory=dict)
    capacity_distributions: dict[str, dict[str, float]] = dataclasses.field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        """Initialise the :class:`ModelOutput` base after dataclass field assignment."""
        super().__init__()

    @functools.cached_property
    def _zip_samples(self) -> list[tuple[float, float]]:
        """Zipped (tourist, excursionist) presence sample pairs."""
        return list(zip(self.sample_tourists, self.sample_excursionists))

    @functools.cached_property
    def sustainable_area(self) -> float:
        """Sustainable area under the sustainability field."""
        return compute_sustainable_area(self.field, self.tt, self.ee)

    @functools.cached_property
    def sustainability_index(self) -> tuple[float, float]:
        """Overall sustainability index and CI half-width."""
        return compute_sustainability_index_with_ci(
            self.field, self.tt, self.ee, self._zip_samples, self.confidence
        )

    @functools.cached_property
    def sustainability_by_constraint(self) -> dict[str, tuple[float, float]]:
        """Per-constraint sustainability index and CI half-width."""
        return compute_sustainability_by_constraint(
            self.field_elements, self.tt, self.ee, self._zip_samples, self.confidence
        )

    @functools.cached_property
    def modal_lines(self) -> dict[str, tuple[tuple, tuple]]:
        """Per-constraint modal lines as ``((t0, t1), (e0, e1))`` coordinate pairs."""
        return compute_modal_lines(self.field_elements, self.tt, self.ee)

    @functools.cached_property
    def kpis(self) -> dict[str, Any]:
        """KPI dict: overtourism level, critical constraint, per-constraint levels."""
        idx, ci = self.sustainability_index
        sbc = self.sustainability_by_constraint
        kpis: dict[str, Any] = {}
        kpis["overtourism_level"] = {
            "level": round((1 - idx) * 100, 4),
            "confidence": round(ci * 100, 4),
        }
        critical_name = min(sbc, key=lambda k: sbc[k][0])
        c_mean, c_ci = sbc[critical_name]
        kpis["critical constraint"] = {
            "name": critical_name,
            "level": round((1 - c_mean) * 100, 4),
            "confidence": round(c_ci * 100, 4),
        }
        for name, (c_mean, c_ci) in sbc.items():
            kpis["constraint level " + name] = {
                "level": round((1 - c_mean) * 100, 4),
                "confidence": round(c_ci * 100, 4),
            }
        return kpis

    @functools.cached_property
    def _uncertainty_at_samples(self) -> list[float]:
        """Per-sample overall sustainability field value."""
        pts = np.array(self._zip_samples)
        vals = interpolate.interpn(
            (self.tt, self.ee), self.field, pts, bounds_error=False, fill_value=0.0
        )
        return [float(f"{v:.4f}") for v in vals]

    @functools.cached_property
    def _uncertainty_by_constraint_at_samples(self) -> dict[str, list[float]]:
        """Per-sample per-constraint sustainability field values."""
        pts = np.array(self._zip_samples)
        result = {}
        for name, fe in self.field_elements.items():
            vals = interpolate.interpn(
                (self.tt, self.ee), fe, pts, bounds_error=False, fill_value=0.0
            )
            result[name] = [float(f"{v:.4f}") for v in vals]
        return result

    @functools.cached_property
    def _usage_at_samples(self) -> dict[str, list[int]]:
        """Per-sample per-constraint usage interpolated from stored usage fields."""
        pts = np.array(self._zip_samples)
        result = {}
        for name, uf in self.usage_fields.items():
            vals = interpolate.interpn(
                (self.tt, self.ee), uf, pts, bounds_error=False, fill_value=0.0
            )
            vals = np.nan_to_num(vals, nan=0.0, posinf=0.0, neginf=0.0)
            result[name] = [max(0, int(v)) for v in vals]
        return result

    @functools.cached_property
    def _aggregate_usage_at_samples(self) -> list[int]:
        """Per-sample aggregate normalized usage (0–100 scale)."""
        pts = np.array(self._zip_samples)
        n = len(self._zip_samples)
        usage = np.ones(n)
        for name, uf in self.usage_fields.items():
            cap_loc = self.capacity_distributions[name]["loc"]
            u_vals = interpolate.interpn(
                (self.tt, self.ee), uf, pts, bounds_error=False, fill_value=0.0
            )
            if np.isfinite(cap_loc) and cap_loc > 0:
                usage += u_vals / cap_loc
            else:
                usage += np.inf
        usage *= 100.0 / len(self.usage_fields)
        usage = np.nan_to_num(usage, nan=0.0, posinf=100.0, neginf=0.0)
        usage = np.clip(usage, 0.0, 100.0)
        return [int(u) for u in usage]

    @functools.cached_property
    def _capacity_mean_by_constraint(self) -> dict[str, float]:
        """Mean capacity per constraint."""
        return {
            name: params["loc"] for name, params in self.capacity_distributions.items()
        }

    @functools.cached_property
    def _capacity_mean(self) -> float:
        """Aggregate capacity mean (always 100.0 by construction)."""
        return 100.0

    @functools.cached_property
    def _usage_uncertainty_at_samples(self) -> list[float]:
        """Per-sample aggregate usage uncertainty via aggregate capacity CDF."""
        variance = sum(
            (params["scale"] ** 2) / (params["loc"] ** 2)
            for params in self.capacity_distributions.values()
            if np.isfinite(params["loc"]) and params["loc"] > 0
        )
        n_c = len(self.capacity_distributions)
        agg_scale = (variance**0.5) * 100.0 / n_c
        return _usage_uncertainty_from_params(
            {"loc": 100.0, "scale": agg_scale}, self._aggregate_usage_at_samples
        )

    @functools.cached_property
    def _usage_uncertainty_by_constraint_at_samples(self) -> dict[str, list[float]]:
        """Per-sample per-constraint usage uncertainty."""
        return {
            name: _usage_uncertainty_from_params(params, self._usage_at_samples[name])
            for name, params in self.capacity_distributions.items()
        }

    def to_snapshot(self) -> dict[str, Any]:
        """Return a compact JSON-serialisable snapshot of derived metrics.

        Always present: ``sustainable_area``, ``sustainability_index``,
        ``sustainability_by_constraint``, ``modal_lines``.

        Present when ``usage_fields`` is populated: ``sample_x``, ``sample_y``,
        ``x_max``, ``y_max``, ``uncertainty``, ``uncertainty_by_constraint``,
        ``kpis``, ``constraint_curves``, ``usage``, ``usage_by_constraint``,
        ``usage_uncertainty``, ``usage_uncertainty_by_constraint``,
        ``capacity_mean``, ``capacity_mean_by_constraint``.
        """
        d: dict[str, Any] = {}
        d["sustainable_area"] = float(self.sustainable_area)
        idx, ci = self.sustainability_index
        d["sustainability_index"] = {"value": float(idx), "ci": float(ci)}
        d["sustainability_by_constraint"] = {
            k: {"value": float(v), "ci": float(c)}
            for k, (v, c) in self.sustainability_by_constraint.items()
        }
        d["modal_lines"] = {
            k: {"t": list(t_coords), "e": list(e_coords)}
            for k, (t_coords, e_coords) in self.modal_lines.items()
        }
        if self.usage_fields:
            d["sample_x"] = [int(x) for x in self.sample_tourists]
            d["sample_y"] = [int(y) for y in self.sample_excursionists]
            d["x_max"] = float(self.tt.max())
            d["y_max"] = float(self.ee.max())
            d["uncertainty"] = self._uncertainty_at_samples
            d["uncertainty_by_constraint"] = self._uncertainty_by_constraint_at_samples
            d["kpis"] = self.kpis
            d["constraint_curves"] = {
                k: [list(t_coords), list(e_coords)]
                for k, (t_coords, e_coords) in self.modal_lines.items()
            }
            d["usage"] = self._aggregate_usage_at_samples
            d["usage_by_constraint"] = self._usage_at_samples
            d["usage_uncertainty"] = self._usage_uncertainty_at_samples
            d["usage_uncertainty_by_constraint"] = (
                self._usage_uncertainty_by_constraint_at_samples
            )
            d["capacity_mean"] = self._capacity_mean
            d["capacity_mean_by_constraint"] = self._capacity_mean_by_constraint
        return d


# ──────────────────────────────────────────────
# MolvenoEvaluator — merged evaluator
# ──────────────────────────────────────────────


class MolvenoEvaluator(ModelEvaluator[MolvenoModel, MolvenoOutput]):
    """Evaluator for the Molveno overtourism model.

    Handles the full evaluation pipeline in one place: grid construction,
    ensemble sampling, CDT evaluation, output assembly, widget-ID translation,
    situation filtering, and EN→IT constraint name mapping.

    Parameters
    ----------
    model : MolvenoModel
        The CDT model to evaluate.
    situations : list[Situation]
        Named context-variable filter presets.
    grid : Grid
        Evaluation grid: ``x_max`` / ``y_max`` / ``n_samples``.
    sampler : Sampler
        Presence sampling: ``target_presence_samples``.
    index_name_map : dict[str, str] or None
        Mapping from UI widget IDs to model index names.
    """

    def __init__(
        self,
        model: MolvenoModel,
        situations: list[Situation],
        grid: Grid,
        sampler: Sampler,
        index_name_map: dict[str, str] | None = None,
        percentage_widget_ids: set[str] | None = None,
    ) -> None:
        super().__init__(model)
        self._t_max = grid.x_max
        self._e_max = grid.y_max
        self._t_sample = grid.n_samples
        self._e_sample = grid.n_samples
        self._target_presence_samples = sampler.target_presence_samples
        self.situations = situations
        self.index_name_map = index_name_map or {}
        self._percentage_widget_ids = frozenset(percentage_widget_ids or ())
        self._reverse_map = {v: k for k, v in self.index_name_map.items()}

    # ------------------------------------------------------------------
    # Core pipeline
    # ------------------------------------------------------------------

    def _pre_compute(
        self, scenario: Any, config: EvaluationConfig
    ) -> tuple[np.ndarray, np.ndarray, dict]:
        """Build parameter axes and draw presence samples."""
        model = self._model
        tt = np.linspace(0, self._t_max, self._t_sample + 1)
        ee = np.linspace(0, self._e_max, self._e_sample + 1)
        sampling_ensemble = CrossProductEnsemble(
            type(scenario)(model),
            max_categorical_size=config.ensemble_size,
            exclude=model.pvs,
        )
        pv_samples = sample_across(
            sampling_ensemble,
            [model.pv_tourists, model.pv_excursionists],
            total=self._target_presence_samples,
        )
        return tt, ee, pv_samples

    def _build_output(
        self,
        result: EvaluationResult,
        tt: np.ndarray,
        ee: np.ndarray,
        pv_samples: dict,
        scenario: Any = None,
    ) -> MolvenoOutput:
        """Build a :class:`MolvenoOutput` from an evaluated result."""
        model = self._model
        field, field_elements = compute_sustainability_field(
            model,
            result,
            scenario=scenario,
        )
        rf_t = float(np.mean(result[model.i_p_tourists_reduction_factor]))
        sl_t = float(np.mean(result[model.i_p_tourists_saturation_level]))
        rf_e = float(np.mean(result[model.i_p_excursionists_reduction_factor]))
        sl_e = float(np.mean(result[model.i_p_excursionists_saturation_level]))
        sample_tourists = [
            _presence_transformation(s, rf_t, sl_t)
            for s in pv_samples[model.pv_tourists]
        ]
        sample_excursionists = [
            _presence_transformation(s, rf_e, sl_e)
            for s in pv_samples[model.pv_excursionists]
        ]
        usage_fields: dict[str, np.ndarray] = {}
        capacity_distributions: dict[str, dict[str, float]] = {}
        for c in model.constraints:
            # broadcast to (N_t, N_e); accommodation usage is (N_t, 1) since it
            # doesn't depend on excursionists — broadcasting makes interpn work.
            usage_fields[c.name] = np.broadcast_to(
                result.marginalize(c.usage), field.shape
            ).copy()
            cap_value = _get_effective_capacity_value(c, scenario)
            if isinstance(cap_value, Distribution):
                cap_loc = float(cap_value.mean())
                cap_scale = float(cap_value.std())
            else:
                cap_loc = float(np.mean(result[c.capacity]))
                cap_scale = 0.0
            capacity_distributions[c.name] = {"loc": cap_loc, "scale": cap_scale}
        return MolvenoOutput(
            field=field,
            field_elements=field_elements,
            tt=tt,
            ee=ee,
            sample_tourists=sample_tourists,
            sample_excursionists=sample_excursionists,
            usage_fields=usage_fields,
            capacity_distributions=capacity_distributions,
        )

    # ------------------------------------------------------------------
    # ModelEvaluator abstract interface
    # ------------------------------------------------------------------

    def evaluate(self, scenario: Any, config: EvaluationConfig) -> MolvenoOutput:
        """Translate widget overrides + situation, then run a blocking evaluation."""
        eval_scenario = self._build_eval_scenario(scenario, config)
        model = self._model
        tt, ee, pv_samples = self._pre_compute(eval_scenario, config)
        ensemble = CrossProductEnsemble(
            eval_scenario,
            max_categorical_size=config.ensemble_size,
            exclude=model.pvs,
        )
        result = Evaluation(eval_scenario).evaluate(
            ensemble=ensemble,
            parameters={model.pv_tourists: tt, model.pv_excursionists: ee},
        )
        output = self._build_output(result, tt, ee, pv_samples, scenario=eval_scenario)
        self.attach_resume(output, result)
        return output

    def run_async(
        self, scenario: Any, config: EvaluationConfig
    ) -> ModelRunHandle[MolvenoOutput]:
        """Translate widget overrides + situation, then submit an async evaluation."""
        eval_scenario = self._build_eval_scenario(scenario, config)
        model = self._model
        tt, ee, pv_samples = self._pre_compute(eval_scenario, config)
        ensemble = CrossProductEnsemble(
            eval_scenario,
            max_categorical_size=config.ensemble_size,
            exclude=model.pvs,
        )
        future = _get_default_executor().submit(
            Evaluation(eval_scenario).evaluate,
            ensemble=ensemble,
            parameters={model.pv_tourists: tt, model.pv_excursionists: ee},
        )

        def _post(result: EvaluationResult) -> MolvenoOutput:
            output = self._build_output(
                result, tt, ee, pv_samples, scenario=eval_scenario
            )
            self.attach_resume(output, result)
            return output

        return ModelRunHandle(future, _post)

    def input_schema(self) -> dict[str, dict[str, Any]]:
        """Return widget-ID → schema dict for all tunable indexes."""
        schema: dict[str, dict[str, Any]] = {}
        for widget_id in self.index_name_map:
            idx = _find_index_by_name(self._model, widget_id, self.index_name_map)
            if idx is None:
                continue
            if isinstance(idx, DistributionIndex):
                schema[widget_id] = {"type": "distribution", "params": idx.params}
            elif isinstance(idx, Index) and isinstance(idx.value, (int, float)):
                schema[widget_id] = {"type": "scalar", "default": float(idx.value)}
        return schema

    def build_output(self, data: dict[str, Any]) -> MolvenoOutput:
        """Rebuild a :class:`MolvenoOutput` from serialized data."""
        return MolvenoOutput.from_dict(data)

    def get_index_diffs(self, scenario: Any) -> dict[str, str]:
        """Return ``{widget_id: "was X -> now Y"}`` for each overridden index."""
        values = self._overrides_to_values(scenario)
        diffs = {}
        for name, new_val in values.items():
            idx = _find_index_by_name(self._model, name, self.index_name_map)
            if idx is None:
                continue
            if isinstance(idx, DistributionIndex):
                old_val = idx.params
            elif isinstance(idx, Index) and isinstance(idx.value, (int, float)):
                old_val = idx.value
            else:
                continue
            diff_str = _get_diff_str(
                idx,
                old_val,
                new_val,
                percentage_scale=name in self._percentage_widget_ids,
            )
            if diff_str is not None:
                diffs[name] = diff_str
        return diffs

    def get_model_values(self, scenario: Any) -> dict[str, Any]:
        """Return ``{widget_id: effective_value}`` for each tunable index."""
        model = self._model
        values: dict[str, Any] = {}
        for idx in model.indexes:
            if isinstance(idx, DistributionIndex):
                key = self._reverse_map.get(idx.name, idx.name)
                values[key] = idx.params
            elif isinstance(idx, Index) and isinstance(idx.value, (int, float)):
                key = self._reverse_map.get(idx.name, idx.name)
                values[key] = idx.value
        for idx, override in scenario.overrides.items():
            key = self._reverse_map.get(idx.name, idx.name)
            values[key] = override
        return values

    # ------------------------------------------------------------------
    # Scenario construction helpers
    # ------------------------------------------------------------------

    def _build_eval_scenario(
        self, scenario: Any, config: EvaluationConfig
    ) -> CDTScenario:
        """Merge situation filter + widget overrides into a CDT scenario."""
        model = self._model
        context_id = getattr(config, "context_id", None)
        values = self._overrides_to_values(scenario)
        situation_filter = self._filter_situation(context_id)
        return CDTScenario(
            model,
            overrides={
                **self._situation_to_overrides(situation_filter),
                **self._values_to_overrides(model, values),
            },
        )

    def _overrides_to_values(self, scenario: Any) -> dict[str, Any]:
        return {
            self._reverse_map.get(idx.name, idx.name): val
            for idx, val in scenario.overrides.items()
        }

    def _values_to_overrides(self, model: MolvenoModel, values: dict[str, Any]) -> dict:
        overrides: dict = {}
        for widget_id, val in values.items():
            model_name = self.index_name_map.get(widget_id, widget_id)
            for idx in model.indexes:
                if isinstance(idx, Index) and idx.name == model_name:
                    overrides[idx] = val
                    break
        return overrides

    def _filter_situation(self, context_id: str | None) -> dict:
        for s in self.situations:
            if s.name == context_id:
                return s.values
        return {}

    def _situation_to_overrides(self, situation_filter: dict) -> dict:
        overrides: dict = {}
        for cv, values_list in situation_filter.items():
            if not values_list:
                continue
            if len(values_list) == 1:
                overrides[cv] = values_list[0]
            elif hasattr(cv, "outcomes"):
                probs = {v: cv.outcomes[v] for v in values_list if v in cv.outcomes}
                total = sum(probs.values())
                overrides[cv] = {v: p / total for v, p in probs.items()}
            else:
                w = 1.0 / len(values_list)
                overrides[cv] = {v: w for v in values_list}
        return overrides
