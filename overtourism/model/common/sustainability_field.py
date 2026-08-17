# SPDX-License-Identifier: Apache-2.0
"""Shared config, output type, and field math for the overtourism model family.

See `overtourism/BACKEND_DESIGN.md` §4. `compute_sustainable_area`,
`compute_sustainability_index_with_ci`, `compute_sustainability_by_constraint`,
and `compute_modal_lines` were, before this module existed, near-identical
copies duplicated across `fazzon_model.py`, `molveno_model.py`, and
`portofino_model.py`. They are pure array math (field + axes + presences +
confidence in; tuple/dict out) with no model-specific coupling.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any

import numpy as np
from overtourism.cdt_ext.runner_ext import EnsembleEvaluationConfig, ParameterMeta
from scipy import interpolate, ndimage
from scipy import stats as scipy_stats

from civic_digital_twins.dt_model import DistributionIndex, EvaluationResult
from civic_digital_twins.dt_model.simulation.runner import ModelOutput

__all__ = [
    "OvertourismEvaluationConfig",
    "OvertourismParameterMeta",
    "SustainabilityFieldOutput",
    "compute_modal_lines",
    "compute_sustainability_by_constraint",
    "compute_sustainability_field",
    "compute_sustainability_index_with_ci",
    "compute_sustainable_area",
]


# ---------------------------------------------------------------------------
# OvertourismParameterMeta
# ---------------------------------------------------------------------------


@dataclass
class OvertourismParameterMeta(ParameterMeta):
    """`ParameterMeta` extended with presentation content for the dashboards.

    Built via plain dataclass inheritance (see the rationale on
    `cdt_ext.runner_ext.ParameterMeta`). Superset of the fields
    `overtourism.dt_studio.dashboard.adapter.ParameterSpec` used to carry separately —
    that class is removed since it duplicated this one exactly.
    """

    label: str = ""
    description: str = ""
    unit: str = ""
    category: str = ""
    step: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    default_range: tuple[float, float] | None = None


# ---------------------------------------------------------------------------
# OvertourismEvaluationConfig
# ---------------------------------------------------------------------------


@dataclass
class OvertourismEvaluationConfig(EnsembleEvaluationConfig):
    """`EnsembleEvaluationConfig` extended with presence-sampling/statistical parameters.

    Concepts — scatter-overlay sampling, a sustainability-index confidence
    interval — that don't exist outside this model family.
    """

    sample_seed: int | None = None
    target_presence_samples: int = 2000
    confidence: float = 0.8


# ---------------------------------------------------------------------------
# Shared field math
# ---------------------------------------------------------------------------


def compute_sustainability_field(
    constraints: Any,
    result: EvaluationResult,
    x_param: Any,
    y_param: Any,
    scenario: Any = None,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Compute the sustainability field and per-constraint field elements.

    Shape is ``(N_x, N_y)`` matching the ``x_param``/``y_param`` parameter
    axes passed to the evaluation.

    Parameters
    ----------
    constraints : Iterable[Any]
        Objects exposing ``.name`` (str), ``.usage`` (Index), and
        ``.capacity`` (Index) — the model's ``Constraint`` list. Structurally
        typed rather than importing a shared ``Constraint`` class: each
        model keeps its own (Fazzon's, Molveno's, Portofino's), and none of
        that is model-specific from this function's point of view.
    result : EvaluationResult
        Evaluated ensemble result (usage values and weights).
    x_param, y_param : Any
        The two PARAMETER-axis indexes swept by ``result`` (used only to
        read the field shape from ``result.parameter_values``).
    scenario : Scenario, optional
        When provided, capacity distributions are resolved via
        ``scenario.effective_distribution(capacity_index)``, so that
        scenario overrides of distribution-backed capacities are correctly
        reflected in the field. When ``None`` the index's built-in default
        distribution is used.
    """
    field = np.ones(
        (
            result.parameter_values[x_param].size,
            result.parameter_values[y_param].size,
        )
    )
    field_elements: dict[str, np.ndarray] = {}
    for c in constraints:
        usage = np.broadcast_to(result[c.usage], result.full_shape)
        if isinstance(c.capacity, DistributionIndex):
            dist = (
                scenario.effective_distribution(c.capacity) if scenario is not None else c.capacity.frozen_distribution
            )
            mask = (1.0 - dist.cdf(usage)).astype(float)
        else:
            cap = np.broadcast_to(result[c.capacity], result.full_shape)
            mask = (usage <= cap).astype(float)
        field_elem = np.tensordot(mask, result.weights, axes=([-1], [0]))
        field_elements[c.name] = field_elem
        field *= field_elem
    return field, field_elements


def compute_sustainable_area(field: np.ndarray, x_values: np.ndarray, y_values: np.ndarray) -> float:
    """Integral approximation of the sustainable area under the field."""
    return field.sum() * functools.reduce(
        lambda a, b: a * b,
        [axis.max() / (axis.size - 1) + 1 for axis in (x_values, y_values)],
    )


def compute_sustainability_index_with_ci(
    field: np.ndarray,
    x_values: np.ndarray,
    y_values: np.ndarray,
    presences: list,
    confidence: float = 0.8,
) -> tuple[float, float]:
    """Return ``(sustainability_index, ci_half_width)`` over the sampled presences."""
    index = interpolate.interpn((x_values, y_values), field, np.array(presences), bounds_error=False, fill_value=0.0)
    m, se = np.mean(index), scipy_stats.sem(index)
    h = float(se * scipy_stats.t.ppf((1 + confidence) / 2.0, index.size - 1))
    return float(m), h


def compute_sustainability_by_constraint(
    field_elements: dict[str, np.ndarray],
    x_values: np.ndarray,
    y_values: np.ndarray,
    presences: list,
    confidence: float = 0.8,
) -> dict[str, tuple[float, float]]:
    """Return ``(index, ci_half_width)`` per constraint name."""
    result: dict[str, tuple[float, float]] = {}
    for name, fe in field_elements.items():
        index = interpolate.interpn((x_values, y_values), fe, np.array(presences), bounds_error=False, fill_value=0.0)
        m, se = np.mean(index), scipy_stats.sem(index)
        h = float(se * scipy_stats.t.ppf((1 + confidence) / 2.0, index.size - 1))
        result[name] = (float(m), h)
    return result


def compute_modal_lines(
    field_elements: dict[str, np.ndarray],
    x_values: np.ndarray,
    y_values: np.ndarray,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Compute per-constraint modal lines via orthogonal regression (first PC)."""
    bounds = [x_values.max(), y_values.max()]
    modal_lines: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for name, fe in field_elements.items():
        matrix = (fe <= 0.5) & (
            (ndimage.shift(fe, (0, 1)) > 0.5)
            | (ndimage.shift(fe, (0, -1)) > 0.5)
            | (ndimage.shift(fe, (1, 0)) > 0.5)
            | (ndimage.shift(fe, (-1, 0)) > 0.5)
        )
        yi, xi = np.nonzero(matrix)
        if len(yi) < 3:
            continue
        pts = np.stack([x_values[yi], y_values[xi]], axis=1)
        centroid = pts.mean(axis=0)
        _, _, vt = np.linalg.svd(pts - centroid, full_matrices=False)
        direction = vt[0]
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
        modal_lines[name] = (np.array([p0[0], p1[0]]), np.array([p0[1], p1[1]]))
    return modal_lines


# ---------------------------------------------------------------------------
# SustainabilityFieldOutput
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class SustainabilityFieldOutput(ModelOutput):
    """Unified evaluation output for 2D sustainability-field models.

    Covers presence-vs-presence models (Fazzon, Molveno; Portofino as a
    future migration). Replaces per-model output classes directly — no per-model subclass is
    needed since, once the field math above is shared, no model has a field
    to add beyond this common set.

    Attributes
    ----------
    field : np.ndarray
        Shape ``(N_x, N_y)``. Each entry is the probability that all
        constraints are satisfied at the corresponding ``(x, y)`` presence.
    field_elements : dict[str, np.ndarray]
        Per-constraint field arrays, same shape as ``field``.
    x_values, y_values : np.ndarray
        1-D parameter-grid axes, shape ``(N_x,)`` / ``(N_y,)``.
    x_axis_name, y_axis_name : str
        Human-readable axis labels (domain metadata, not rendering config).
    samples_x, samples_y : list[float]
        Raw presence samples for the scatter overlay.
    confidence : float
        Confidence level for the sustainability CI (default 0.8).
    """

    field: np.ndarray
    field_elements: dict[str, np.ndarray]
    x_values: np.ndarray
    y_values: np.ndarray
    x_axis_name: str
    y_axis_name: str
    samples_x: list[float]
    samples_y: list[float]
    confidence: float = 0.8

    def __post_init__(self) -> None:
        """Initialise the base `ModelOutput`."""
        super().__init__()

    @functools.cached_property
    def _zip_samples(self) -> list[tuple[float, float]]:
        """Zip x/y presence samples into coordinate pairs."""
        return list(zip(self.samples_x, self.samples_y))

    @functools.cached_property
    def sustainable_area(self) -> float:
        """Integral approximation of the sustainable area under the field."""
        return compute_sustainable_area(self.field, self.x_values, self.y_values)

    @functools.cached_property
    def sustainability_index(self) -> tuple[float, float]:
        """Return ``(index, ci_half_width)`` over the sampled presences."""
        return compute_sustainability_index_with_ci(
            self.field, self.x_values, self.y_values, self._zip_samples, self.confidence
        )

    @functools.cached_property
    def sustainability_by_constraint(self) -> dict[str, tuple[float, float]]:
        """Return ``(index, ci_half_width)`` per constraint."""
        return compute_sustainability_by_constraint(
            self.field_elements, self.x_values, self.y_values, self._zip_samples, self.confidence
        )

    @functools.cached_property
    def modal_lines(self) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        """Per-constraint modal lines via orthogonal regression."""
        return compute_modal_lines(self.field_elements, self.x_values, self.y_values)

    def to_snapshot(self) -> dict[str, Any]:
        """Serialise to a plain dict snapshot, including derived KPIs."""
        d = super().to_snapshot()
        d["sustainable_area"] = float(self.sustainable_area)
        idx, ci = self.sustainability_index
        d["sustainability_index"] = {"value": float(idx), "ci": float(ci)}
        d["sustainability_by_constraint"] = {
            k: {"value": float(v), "ci": float(c)} for k, (v, c) in self.sustainability_by_constraint.items()
        }
        d["modal_lines"] = {
            k: {"x": list(x_coords), "y": list(y_coords)} for k, (x_coords, y_coords) in self.modal_lines.items()
        }
        return d
