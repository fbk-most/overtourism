# SPDX-License-Identifier: Apache-2.0
"""Staging area for `runner.py` extensions — see `overtourism/BACKEND_DESIGN.md` §3.

Every item here is judged against one test: would a non-overtourism `dt_model`
domain plausibly need it too? Nothing here is specific to the overtourism
examples — domain/example-family-specific code (shared field math, unified
output type, presentation metadata) lives in `overtourism.model.common` instead.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from civic_digital_twins.dt_model import Scenario
from civic_digital_twins.dt_model.simulation.runner import EvaluationConfig
from scipy import stats as scipy_stats

__all__ = ["EnsembleEvaluationConfig", "ParameterMeta", "build_scenario"]


# ---------------------------------------------------------------------------
# ParameterMeta
# ---------------------------------------------------------------------------


@dataclass
class ParameterMeta:
    """Structural parameter metadata: a typed replacement for the plain schema dict.

    A typed replacement for the ``dict[str, dict[str, Any]]`` schema that
    ``ModelEvaluator.input_schema()`` currently returns.

    Deliberately minimal: it carries only what generic code needs to
    **validate or reconstruct** a submitted override — nothing that only
    affects how a specific widget renders it. In particular:

    - ``min_value``/``max_value``/a UI-facing default range are curated
      widget-exploration bounds, not hard domain constraints, and
      :func:`build_scenario` never reads them — so they are excluded here.
    - ``default``/``default_category`` mirror the model's own baked-in
      ``Index`` default (a hard fact, independent of any frontend), so they
      stay.
    - Presentation content (``label``, ``description``, ``unit``,
      ``category``, ``step``, a UI-facing value range, ...) belongs on a
      subclass built via plain dataclass inheritance — see
      ``overtourism.model.common.sustainability_field.OvertourismParameterMeta``. :func:`build_scenario`
      only ever touches the fields declared here, so it works unmodified
      against any conforming subclass.

    ``ModelEvaluator.input_schema()`` keeps returning ``dict[str,
    ParameterMeta]`` — the natural shape for the hand-authored literal each
    evaluator writes. ``name`` is kept on the object (not left to the dict
    key alone) so that a ``list[ParameterMeta]`` view — always *derived*
    (``list(schema.values())``), never hand-authored separately — is
    self-describing wherever it travels (e.g. a JSON array in a future
    FastAPI ``/schema`` response).
    """

    name: str  # matches index.name exactly; used as the boundary key
    kind: str  # "scalar" | "categorical" | "distribution"
    distribution_family: str | None = None
    distribution_fixed_params: dict[str, Any] | None = None
    support: list[str] = field(default_factory=list)
    default: float | None = None
    default_category: str | None = None


# ---------------------------------------------------------------------------
# EnsembleEvaluationConfig
# ---------------------------------------------------------------------------


@dataclass
class EnsembleEvaluationConfig(EvaluationConfig):
    """``EvaluationConfig`` extended with ``CrossProductEnsemble`` reproducibility knobs.

    ``ensemble_seed``/``n_samples_per_combo`` are not new concepts — they are
    constructor parameters :class:`~dt_model.CrossProductEnsemble` already
    accepts. This class makes them explicit, injectable evaluation config
    instead of the hardcoded class constants (and, in some current evaluators,
    a config field that is silently never read) that exist today.

    Unlike :class:`ParameterMeta`, this class has no long-term identity of
    its own: it stages two fields that are meant to land directly on
    ``EvaluationConfig`` in the library. On that migration this class is
    deleted outright, not renamed — callers switch to a plain (now-richer)
    ``EvaluationConfig``.
    """

    ensemble_seed: int | None = None
    n_samples_per_combo: int = 1


# ---------------------------------------------------------------------------
# build_scenario
# ---------------------------------------------------------------------------


def build_scenario(
    model: Any,
    param_overrides: Mapping[str, Any],
    index_map: Mapping[str, Any],
    spec_map: Mapping[str, ParameterMeta],
    parameter_axes: list[Any] | None = None,
) -> Scenario:
    """Resolve string-keyed ``param_overrides`` into a :class:`Scenario`.

    Handles three value types transparently, dispatching on
    ``spec_map[name].kind``:

    - **Scalar** (``float``): passed directly as the index override.
    - **Distribution** (``(float, float)`` tuple): reconstructed as a frozen
      ``scipy.stats`` distribution via ``ParameterMeta.distribution_family``
      and ``.distribution_fixed_params``, using the convention ``loc = lo``,
      ``scale = hi - lo``. This convention belongs to the frontends that
      produce ``(lo, hi)`` endpoint pairs, not to ``DistributionIndex``
      itself.
    - **Categorical** (``str``): passed directly as the index override.

    Keys absent from ``param_overrides``, or present but missing from
    ``index_map``/``spec_map``, are left unoverridden — model defaults apply.

    Parameters
    ----------
    model : Any
        The model the resulting :class:`Scenario` wraps.
    param_overrides : Mapping[str, Any]
        Partial ``{index_name: value}`` mapping from a frontend.
    index_map : Mapping[str, Any]
        ``index.name -> Index`` object lookup.
    spec_map : Mapping[str, ParameterMeta]
        ``index.name -> ParameterMeta`` lookup, used to dispatch on ``kind``
        and to reconstruct distribution overrides. Accepts any
        ``ParameterMeta`` subclass (e.g.
        ``overtourism.model.common.sustainability_field.OvertourismParameterMeta``) — declared as
        ``Mapping`` rather than ``dict`` so the covariant value type doesn't
        reject a richer subclass's schema dict.
    parameter_axes : list[Any] or None, optional
        Presence-variable axes to declare as PARAMETER axes on the returned
        ``Scenario`` (see :class:`Scenario`). ``None`` for models with no
        parameter grid to sweep.

    Returns
    -------
    Scenario
        A scenario wrapping ``model`` with the resolved overrides and
        ``parameter_axes`` applied.
    """
    overrides: dict[Any, Any] = {}
    for name, value in param_overrides.items():
        idx = index_map.get(name)
        spec = spec_map.get(name)
        if idx is None or spec is None:
            continue
        if spec.kind == "distribution":
            lo, hi = value
            lo, hi = float(lo), float(hi)
            family = spec.distribution_family or "uniform"
            fixed = dict(spec.distribution_fixed_params or {})
            dist_cls = getattr(scipy_stats, family)
            overrides[idx] = dist_cls(**{**fixed, "loc": lo, "scale": hi - lo})
        elif spec.kind == "categorical":
            overrides[idx] = str(value)
        else:
            overrides[idx] = float(value)
    return Scenario(model, overrides=overrides, parameter_axes=parameter_axes)
