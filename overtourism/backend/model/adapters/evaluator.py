# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
from dataclasses import dataclass

import numpy as np
from civic_digital_twins.dt_model import Evaluation
from civic_digital_twins.dt_model.model.index import (
    Distribution,
    DistributionIndex,
    Index,
)
from civic_digital_twins.dt_model.simulation.ensemble import WeightedScenario

from overtourism.backend.model.adapters.output import (
    OvertourismOutputData,
)
from overtourism.dt_manager.classes.model import ModelEvaluator

if typing.TYPE_CHECKING:
    from civic_digital_twins.dt_model.simulation.evaluation import EvaluationResult

    from overtourism.backend.model.overtourism_metamodel import (
        OvertourismModel,
    )


# ──────────────────────────────────────────────
# EN → IT constraint name mapping (remove when frontend uses English)
# ──────────────────────────────────────────────
CONSTRAINT_NAME_IT: dict[str, str] = {
    "parking": "parcheggi",
    "beach": "spiaggia",
    "accommodation": "alberghi",
    "food": "ristoranti",
}


def _translate_constraint_names(data: dict[str, typing.Any]) -> dict[str, typing.Any]:
    """Translate English constraint names to Italian in the result dict.

    Rewrites keys in ``*_by_constraint`` dicts, ``constraint_curves``,
    and name values inside ``kpis``.  Remove this function (and the map
    above) when the frontend switches to English names.
    """
    tr = CONSTRAINT_NAME_IT

    def _translate_keys(d: dict) -> dict:
        return {tr.get(k, k): v for k, v in d.items()}

    # by-constraint dicts
    for field in (
        "uncertainty_by_constraint",
        "constraint_curves",
        "usage_by_constraint",
        "usage_uncertainty_by_constraint",
        "capacity_mean_by_constraint",
    ):
        if field in data:
            data[field] = _translate_keys(data[field])

    # kpis: "critical constraint" → translate .name
    kpis = data.get("kpis", {})
    new_kpis: dict[str, typing.Any] = {}
    for k, v in kpis.items():
        if k == "critical constraint" and isinstance(v, dict):
            v = {**v, "name": tr.get(v.get("name", ""), v.get("name", ""))}
            new_kpis[k] = v
        elif k.startswith("constraint level "):
            # "constraint level parking" → "constraint level parcheggi"
            suffix = k.removeprefix("constraint level ")
            new_kpis[f"constraint level {tr.get(suffix, suffix)}"] = v
        else:
            new_kpis[k] = v
    data["kpis"] = new_kpis

    return data


# ──────────────────────────────────────────────
# OvertourismEvaluator
# ──────────────────────────────────────────────


def _get_diff_str(idx: Index, old_val, new_val) -> str | None:
    """Compute a human-readable diff string between old and new index values."""

    def tostr(v):
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
    model: OvertourismModel,
    name: str,
    index_name_map: dict[str, str] | None = None,
) -> Index | None:
    model_name = (index_name_map or {}).get(name, name)
    for idx in model.indexes:
        if isinstance(idx, Index) and idx.name == model_name:
            return idx
    return None


def _get_index_diffs(
    model: OvertourismModel,
    values: dict,
    index_name_map: dict[str, str] | None = None,
) -> dict[str, str]:
    diffs = {}
    for name, new_val in values.items():
        idx = _find_index_by_name(model, name, index_name_map)
        if idx is None:
            continue

        if isinstance(idx, DistributionIndex):
            old_val = idx.params
        else:
            val = idx.value
            if not isinstance(val, (int, float)):
                continue
            old_val = val

        diff_str = _get_diff_str(idx, old_val, new_val)
        if diff_str is not None:
            diffs[name] = diff_str
    return diffs


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
    reduction_indexes: dict[str, str]
    saturation_indexes: dict[str, str]


class OvertourismEvaluator(ModelEvaluator):
    """ModelEvaluator for overtourism using CDT 0.8.

    Encapsulates the evaluation pipeline:
    OvertourismEnsemble → Evaluation.evaluate(..., axes) → post-process KPIs.
    """

    def __init__(
        self,
        ensemble_class: type,
        situations: list[Situation],
        grid: Grid,
        sampler: Sampler,
        index_name_map: dict[str, str] | None = None,
    ) -> None:
        self.ensemble_class = ensemble_class
        self.situations = situations
        self.grid = grid
        self.sampler = sampler
        self.index_name_map = index_name_map or {}
        self._reverse_map = {v: k for k, v in self.index_name_map.items()}

    def get_index_diffs(
        self,
        model: OvertourismModel,
        values: dict | None = None,
    ) -> dict[str, str]:
        if values is None:
            return {}
        return _get_index_diffs(model, values, self.index_name_map)

    def get_model_values(self, model: OvertourismModel) -> dict[str, typing.Any]:
        values = {}
        for idx in model.indexes:
            if isinstance(idx, DistributionIndex):
                key = self._reverse_map.get(idx.name, idx.name)
                values[key] = idx.params
            elif isinstance(idx, Index):
                val = idx.value
                if isinstance(val, (int, float)):
                    key = self._reverse_map.get(idx.name, idx.name)
                    values[key] = val
        return values

    def evaluate(
        self,
        model: OvertourismModel,
        *,
        ensemble_size: int = 20,
        values: dict | None = None,
        **kwargs: typing.Any,
    ) -> OvertourismOutputData:
        values = values if values is not None else {}
        context_id = kwargs.get("context_id")

        # Resolve situation from context_id
        situation_filter = self._filter_situation(context_id)

        # Build ensemble and evaluate
        ensemble = self.ensemble_class(
            model, situation_filter, cv_ensemble_size=ensemble_size
        )
        scenarios: list[WeightedScenario] = list(ensemble)

        # Apply value overrides to scenario assignments
        if values:
            scenarios = self._apply_overrides(model, scenarios, values)

        # Build grid axes
        tt = np.linspace(0, self.grid.x_max, self.grid.n_samples + 1)
        ee = np.linspace(0, self.grid.y_max, self.grid.n_samples + 1)
        pvs = model.pvs
        axes = {pvs[0]: tt, pvs[1]: ee}

        # Translate value overrides to model index names
        translated_values = (
            {self.index_name_map.get(k, k): v for k, v in values.items()}
            if values
            else {}
        )

        # Run evaluation
        result = Evaluation(model).evaluate(scenarios, axes=axes)

        # Compute full output
        return self._build_output(model, result, scenarios, axes, translated_values)

    def build_output(self, data: dict[str, typing.Any]) -> OvertourismOutputData:
        """Rebuild an overtourism output object from serialized data."""
        return OvertourismOutputData(**data)

    def _apply_overrides(
        self,
        model: OvertourismModel,
        scenarios: list[WeightedScenario],
        values: dict,
    ) -> list[WeightedScenario]:
        """Inject value overrides into scenario assignments."""
        # Translate widget keys to model index names
        translated = {self.index_name_map.get(k, k): v for k, v in values.items()}

        # Find indexes by name
        name_to_idx: dict[str, Index] = {}
        for idx in model.indexes:
            if isinstance(idx, Index) and idx.name in translated:
                name_to_idx[idx.name] = idx

        if not name_to_idx:
            return scenarios

        # Apply overrides to each scenario
        new_scenarios = []
        for weight, assignments in scenarios:
            new_assignments = dict(assignments)
            for name, idx in name_to_idx.items():
                new_assignments[idx] = translated[name]
            new_scenarios.append((weight, new_assignments))
        return new_scenarios

    def _build_output(
        self,
        model: OvertourismModel,
        result: EvaluationResult,
        scenarios: list[WeightedScenario],
        axes: dict,
        translated_values: dict | None = None,
    ) -> OvertourismOutputData:
        """
        Compute the output matching the old API format.

        Parameters
        ----------
        model : OvertourismModel
            The model being evaluated.
        result : EvaluationResult
            The raw evaluation result from CDT.
        scenarios : list[WeightedScenario]
            The list of scenarios with their weights and assignments.
        axes : dict
            The evaluation grid axes.
        translated_values : dict
            Optional dictionary of index value overrides translated to model index names.

        Returns
        -------
        OvertourismOutputData
            The structured output data with KPIs, uncertainty, and other metrics.
        """
        pvs = model.pvs
        constraints = model.constraints
        axes_values = list(axes.values())
        tt, ee = axes_values[0], axes_values[1]

        # Build map of overridden capacity distributions
        cap_overrides: dict[str, typing.Any] = {}
        if translated_values:
            for c in constraints:
                if c.capacity.name in translated_values:
                    cap_overrides[c.name] = translated_values[c.capacity.name]

        # ── Sustainability field ──
        field = np.ones((tt.size, ee.size))
        field_elements: dict = {}
        for c in constraints:
            usage = np.broadcast_to(result[c.usage], result.full_shape)
            cap_value = cap_overrides.get(c.name, c.capacity.value)
            if isinstance(cap_value, Distribution):
                mask = (1.0 - cap_value.cdf(usage)).astype(float)
            else:
                cap = np.broadcast_to(result[c.capacity], result.full_shape)
                mask = (usage <= cap).astype(float)
            field_elem = np.tensordot(mask, result.weights, axes=([-1], [0]))
            field_elements[c] = field_elem
            field *= field_elem

        # ── Presence samples ──
        sample_x, sample_y = self._sample_presences(model, result, scenarios, pvs)
        zip_sample = list(zip(sample_x, sample_y))

        # ── Constraint curves ──
        constraint_curves = _compute_modal_lines(field_elements, axes)

        # ── KPIs ──
        kpis = _compute_kpis(field, field_elements, axes, constraints, zip_sample)

        # ── Uncertainty ──
        uncertainty, uncertainty_by_constraint = _compute_uncertainty(
            field, field_elements, axes, constraints, zip_sample
        )

        # ── Usage and capacity ──

        (
            usage_list,
            usage_by_constraint,
            capacity_obj,
            capacity_by_constraint,
            cap_mean,
            cap_mean_by_constraint,
        ) = _compute_usage_capacity(
            result, constraints, sample_x, sample_y, axes, cap_overrides
        )

        usage_uncertainty = _compute_usage_uncertainty(capacity_obj, usage_list)
        usage_uncertainty_by_constraint = {}
        for c in constraints:
            usage_uncertainty_by_constraint[c.name] = _compute_usage_uncertainty(
                capacity_by_constraint[c.name], usage_by_constraint[c.name]
            )

        return _translate_constraint_names(
            {
                "sample_x": [int(x) for x in sample_x],
                "sample_y": [int(y) for y in sample_y],
                "kpis": kpis,
                "uncertainty": uncertainty,
                "uncertainty_by_constraint": uncertainty_by_constraint,
                "constraint_curves": constraint_curves,
                "usage": usage_list,
                "usage_by_constraint": usage_by_constraint,
                "usage_uncertainty": usage_uncertainty,
                "usage_uncertainty_by_constraint": usage_uncertainty_by_constraint,
                "capacity_mean": cap_mean,
                "capacity_mean_by_constraint": cap_mean_by_constraint,
                "x_max": self.grid.x_max,
                "y_max": self.grid.y_max,
            }
        )

    def _sample_presences(
        self,
        model: OvertourismModel,
        result: EvaluationResult,
        scenarios: list[WeightedScenario],
        pvs: list,
    ) -> tuple[list, list]:
        """Sample and transform presences from scenarios."""
        target = self.sampler.target_presence_samples

        # Get reduction/saturation values from evaluation result
        def _get_mean(idx_name):
            for idx in model.indexes:
                if isinstance(idx, Index) and idx.name == idx_name:
                    return float(np.mean(result[idx]))
            return 1.0

        samples = {pv: [] for pv in pvs}
        for pv in pvs:
            rf = _get_mean(self.sampler.reduction_indexes[pv.name])
            sl = _get_mean(self.sampler.saturation_indexes[pv.name])

            for weight, assignments in scenarios:
                nr = max(1, round(weight * target))
                raw = pv.sample(cvs=assignments, nr=nr)
                for p in raw:
                    samples[pv].append(_presence_transformation(p, rf, sl))

        return samples[pvs[0]], samples[pvs[1]]

    def _filter_situation(self, context_id: str | None) -> dict:
        for s in self.situations:
            if s.name == context_id:
                return s.values
        return {}


# ─── Post-processing helpers (CDT 0.8 compatible) ─────────────────────


def _presence_transformation(presence, reduction_factor, saturation_level, sharpness=3):
    tmp = presence * reduction_factor
    return (
        tmp
        * saturation_level
        / ((tmp**sharpness + saturation_level**sharpness) ** (1 / sharpness))
    )


def _compute_modal_lines(field_elements: dict, axes: dict) -> dict:
    """Compute modal lines per constraint (boundary detection)."""
    from scipy import ndimage
    from scipy import stats as sp_stats

    axes_list = list(axes.values())
    modal_lines = {}

    for c, fe in field_elements.items():
        matrix = (fe <= 0.5) & (
            (ndimage.shift(fe, (0, 1)) > 0.5)
            | (ndimage.shift(fe, (0, -1)) > 0.5)
            | (ndimage.shift(fe, (1, 0)) > 0.5)
            | (ndimage.shift(fe, (-1, 0)) > 0.5)
        )
        (yi, xi) = np.nonzero(matrix)

        horizontal_regr = None
        vertical_regr = None
        try:
            horizontal_regr = sp_stats.linregress(axes_list[0][yi], axes_list[1][xi])
        except ValueError:
            pass
        try:
            vertical_regr = sp_stats.linregress(axes_list[1][xi], axes_list[0][yi])
        except ValueError:
            pass

        def _vertical(regr):
            if regr.slope < 0.0:
                return ((regr.intercept, 0.0), (0.0, -regr.intercept / regr.slope))
            return ((regr.intercept, regr.intercept), (0.0, 10000.0))

        def _horizontal(regr):
            if regr.slope < 0.0:
                return ((0.0, -regr.intercept / regr.slope), (regr.intercept, 0.0))
            return ((0.0, 10000.0), (regr.intercept, regr.intercept))

        if horizontal_regr and vertical_regr:
            if vertical_regr.rvalue >= horizontal_regr.rvalue:
                modal_lines[c.name] = _vertical(vertical_regr)
            else:
                modal_lines[c.name] = _horizontal(horizontal_regr)
        elif horizontal_regr:
            modal_lines[c.name] = _horizontal(horizontal_regr)
        elif vertical_regr:
            modal_lines[c.name] = _vertical(vertical_regr)

    return modal_lines


def _compute_kpis(
    field: np.ndarray,
    field_elements: dict,
    axes: dict,
    constraints: list,
    zip_sample: list[tuple[float, float]],
) -> dict:
    """Compute KPIs: overtourism level, critical constraint, per-constraint levels."""
    from scipy import interpolate
    from scipy import stats as sp_stats

    axes_list = list(axes.values())
    kpis = {}

    # Overall sustainability index with CI
    index_vals = interpolate.interpn(
        axes_list, field, np.array(zip_sample), bounds_error=False, fill_value=0.0
    )
    m, se = np.mean(index_vals), sp_stats.sem(index_vals)
    h = se * sp_stats.t.ppf(0.9, index_vals.size - 1)
    kpis["overtourism_level"] = {
        "level": round((1 - m) * 100, 4),
        "confidence": round(h * 100, 4),
    }

    # Per-constraint sustainability index with CI
    indexes_per_constraint = {}
    for c in constraints:
        c_vals = interpolate.interpn(
            axes_list,
            field_elements[c],
            np.array(zip_sample),
            bounds_error=False,
            fill_value=0.0,
        )
        c_m = np.mean(c_vals)
        c_se = sp_stats.sem(c_vals)
        c_h = c_se * sp_stats.t.ppf(0.9, c_vals.size - 1)
        indexes_per_constraint[c] = (float(c_m), float(c_h))

    # Critical constraint
    critical = min(indexes_per_constraint, key=lambda c: indexes_per_constraint[c][0])
    crit_level = round((1 - indexes_per_constraint[critical][0]) * 100, 4)
    crit_conf = round(indexes_per_constraint[critical][1] * 100, 4)
    kpis["critical constraint"] = {
        "name": critical.name,
        "level": crit_level,
        "confidence": crit_conf,
    }

    # Per-constraint level
    for c in constraints:
        c_level = round((1 - indexes_per_constraint[c][0]) * 100, 4)
        c_conf = round(indexes_per_constraint[c][1] * 100, 4)
        kpis["constraint level " + c.name] = {
            "level": c_level,
            "confidence": c_conf,
        }

    return kpis


def _compute_uncertainty(
    field: np.ndarray,
    field_elements: dict,
    axes: dict,
    constraints: list,
    zip_sample: list[tuple[float, float]],
) -> tuple[list[float], dict[str, list[float]]]:
    """Compute sustainability uncertainty per sample point."""
    from scipy import interpolate

    axes_list = list(axes.values())

    # Overall uncertainty
    uncertainty = []
    for pt in zip_sample:
        sust = interpolate.interpn(
            axes_list, field, np.array([pt]), bounds_error=False, fill_value=0.0
        )
        uncertainty.append(float("{:.4f}".format(sust[0])))

    # Per-constraint uncertainty
    uncertainty_by_constraint = {}
    for c in constraints:
        c_unc = []
        for pt in zip_sample:
            sust = interpolate.interpn(
                axes_list,
                field_elements[c],
                np.array([pt]),
                bounds_error=False,
                fill_value=0.0,
            )
            c_unc.append(float("{:.4f}".format(sust[0])))
        uncertainty_by_constraint[c.name] = c_unc

    return uncertainty, uncertainty_by_constraint


def _compute_usage_capacity(
    result: EvaluationResult,
    constraints: list,
    sample_x: list,
    sample_y: list,
    axes: dict,
    cap_overrides: dict | None = None,
) -> tuple:
    """Compute usage and capacity statistics per sample."""
    from scipy import interpolate
    from scipy import stats as sp_stats

    cap_overrides = cap_overrides or {}
    axes_list = list(axes.values())
    n = len(sample_x)
    points = np.array(list(zip(sample_x, sample_y)))

    usage_by_constraint = {}
    capacity_by_constraint = {}
    usage = np.ones(n)
    variance = 0.0

    for c in constraints:
        # Marginalize usage over scenarios
        usage_field = result.marginalize(c.usage)
        # Interpolate at sample points
        u_vals = interpolate.interpn(
            axes_list, usage_field, points, bounds_error=False, fill_value=0.0
        )
        usage_by_constraint[c.name] = [int(u) for u in u_vals.tolist()]

        cap_value = cap_overrides.get(c.name, c.capacity.value)
        if isinstance(cap_value, Distribution):
            cap = cap_value.mean()
            var = cap_value.std() ** 2
            capacity_by_constraint[c.name] = cap_value
        else:
            cap = float(np.mean(result[c.capacity]))
            var = 0.0
            capacity_by_constraint[c.name] = sp_stats.norm(loc=cap, scale=0.0)

        usage += u_vals / cap
        variance += var / (cap**2)

    usage *= 100.0 / len(constraints)
    std = (variance**0.5) * 100.0 / len(constraints)
    capacity_obj = sp_stats.norm(loc=100.0, scale=std)
    cap_mean = float(capacity_obj.mean())

    cap_mean_by_constraint = {}
    for c in constraints:
        cap_mean_by_constraint[c.name] = float(capacity_by_constraint[c.name].mean())

    return (
        [int(u) for u in usage.tolist()],
        usage_by_constraint,
        capacity_obj,
        capacity_by_constraint,
        cap_mean,
        cap_mean_by_constraint,
    )


def _compute_usage_uncertainty(capacity, usage: list[float]) -> list[float]:
    """Compute per-sample usage uncertainty via capacity CDF."""
    capacity_mean = float(capacity.mean())
    y_max = int(max(max(usage), capacity_mean) * 1.2)
    rangey = range(y_max)
    cap_cdf = [float(capacity.cdf(y)) for y in rangey]
    heatmap_y = np.linspace(0, y_max, len(cap_cdf))

    result = []
    for u in usage:
        idx = int(np.abs(heatmap_y - u).argmin())
        result.append(float("{:.4f}".format(cap_cdf[idx])))
    return result
