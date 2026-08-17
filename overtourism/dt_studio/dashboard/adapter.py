# SPDX-License-Identifier: Apache-2.0
"""Abstract adapter and data types for the generic overtourism dashboard.

The adapter interface decouples the Streamlit UI from any concrete
overtourism model.  String IDs (``index.name``) cross the interface boundary
— no live Python objects — making the schema fully serialisable and
API-ready.  The name→Index map-back lives inside each concrete backend's
``evaluate()`` method (see ``overtourism.cdt_ext.runner_ext.build_scenario``).

Widget specifications are ``OvertourismParameterMeta`` instances (see
``overtourism.model.common``) — there used to be a separate ``ParameterSpec``
type here, but once the backend-side metadata carries every field a widget
needs (``label``, ``description``, ``unit``, ``category``, ``step``,
``min_value``/``max_value``/``default_range``, ...) a second, identically-shaped
type was pure duplication and was removed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from overtourism.model.common.sustainability_field import OvertourismParameterMeta

__all__ = ["OvertourismAdapter", "PlotData", "ScenarioDef"]


@dataclass(frozen=True)
class ScenarioDef:
    """Immutable definition of a predefined what-if scenario.

    ``ScenarioDef`` objects are constructed once (at adapter initialisation
    time) and stored in the session.  The ``params`` dict holds the
    *complete* parameter mapping for the scenario so that loading a scenario
    is a pure state-write operation with no further model calls.

    Parameters
    ----------
    key : str
        Unique machine-readable identifier (e.g. ``"b1_shuttle_full"``).
    label : str
        Short human-readable label shown in the scenario selector.
    category : str
        Grouping label (not yet rendered in the UI but reserved for future
        grouped selectors).
    description : str
        Markdown-formatted scenario description shown in the expandable
        summary panel.
    params : dict of {str: Any}, optional
        Complete ``{name: value}`` parameter mapping for this scenario.
        Scalars are ``float``, distributions are ``(min, max)`` tuples,
        categoricals are ``str``.  Fields missing from ``params`` are reset
        to spec defaults when the scenario is loaded.  The field is excluded
        from equality comparison and hashing so that two ``ScenarioDef``
        objects with the same ``key`` / ``label`` / ``category`` /
        ``description`` are considered equal regardless of their ``params``.
    """

    key: str
    label: str
    category: str
    description: str
    params: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)


@dataclass
class PlotData:
    """All data needed to render the dashboard's main plot and KPI panel.

    Produced by :meth:`OvertourismAdapter.run` and cached in
    ``st.session_state`` between re-runs when parameters have not changed.

    Parameters
    ----------
    field : np.ndarray
        Sustainability probability field, shape ``(N_x, N_y)``.  Each entry
        is the probability that all constraints are satisfied for the
        corresponding ``(x, y)`` visitor counts.
    field_elements : dict of {str: np.ndarray}
        Per-constraint probability fields, keyed by constraint name.  Each
        array has the same shape as ``field``.
    x_values : np.ndarray
        Axis values along the x dimension (car-mode visitors), shape
        ``(N_x,)``.
    y_values : np.ndarray
        Axis values along the y dimension (non-car visitors), shape
        ``(N_y,)``.
    x_label : str
        Axis label for the x dimension.
    y_label : str
        Axis label for the y dimension.
    samples_x : list of float
        Raw x-axis presence samples used for the scatter overlay.
    samples_y : list of float
        Raw y-axis presence samples used for the scatter overlay.
    sustainability_index : tuple of (float, float)
        Overall sustainability index ``(value, ci_half_width)``.
    sustainability_by_constraint : dict of {str: (float, float)}
        Per-constraint sustainability ``{name: (value, ci_half_width)}``.
    modal_lines : dict of {str: (np.ndarray, np.ndarray)}
        Per-constraint modal lines ``{name: (x_coords, y_coords)}``.
    scenario_key : str, optional
        Key of the active scenario (informational; not used by the renderer).
    scenario_label : str, optional
        Label of the active scenario (informational).
    scenario_description : str, optional
        Markdown description of the active scenario (informational).
    """

    field: np.ndarray
    field_elements: dict[str, np.ndarray]
    x_values: np.ndarray
    y_values: np.ndarray
    x_label: str
    y_label: str
    samples_x: list[float]
    samples_y: list[float]
    sustainability_index: tuple[float, float]
    sustainability_by_constraint: dict[str, tuple[float, float]]
    modal_lines: dict[str, tuple[np.ndarray, np.ndarray]]
    scenario_key: str = ""
    scenario_label: str = ""
    scenario_description: str = ""


class OvertourismAdapter(ABC):
    """Abstract base class decoupling any overtourism model from the generic dashboard UI.

    Concrete adapters subclass :class:`OvertourismAdapter`, implement the four
    abstract members, and pass an instance to :func:`run_dashboard`.

    The interface is intentionally thin: all cross-boundary identifiers are
    plain strings (index names), plain floats/tuples, or plain dicts.  No
    live Python index objects cross the boundary.  This makes the adapter
    schema fully serialisable and forward-compatible with REST APIs.

    Implementing a new adapter
    --------------------------
    1. Subclass :class:`OvertourismAdapter`.
    2. Override :attr:`title` to return a descriptive page title.
    3. Implement :meth:`parameter_specs` — return one
       :class:`~overtourism.model.common.sustainability_field.OvertourismParameterMeta`
       per tunable index (typically ``self._backend.parameter_schema()``).
    4. Implement :meth:`predefined_scenarios` — return zero or more
       :class:`ScenarioDef` objects representing named what-if configurations.
    5. Implement :meth:`run` — accept a ``{name: value}`` override dict and
       return a fully populated :class:`PlotData`.
    """

    @property
    @abstractmethod
    def title(self) -> str:
        """Human-readable title shown as the Streamlit page title and main heading."""
        ...

    @abstractmethod
    def parameter_specs(self) -> list[OvertourismParameterMeta]:
        """Return the ordered list of tunable parameter specifications.

        Returns
        -------
        list of OvertourismParameterMeta
            One entry per index that the dashboard should expose as a sidebar
            widget.  The order determines the render order within each
            ``category`` group.
        """
        ...

    @abstractmethod
    def predefined_scenarios(self) -> list[ScenarioDef]:
        """Return the ordered list of predefined what-if scenarios.

        Returns
        -------
        list of ScenarioDef
            Each entry is shown as an option in the scenario selector.  An
            empty list hides the scenario selector entirely.
        """
        ...

    @abstractmethod
    def run(self, param_overrides: dict[str, Any]) -> PlotData:
        """Evaluate the model and return visualisation-ready data.

        Parameters
        ----------
        param_overrides : dict of {str: Any}
            Partial or complete ``{index_name: value}`` mapping of parameter
            overrides.  Keys are string index names; values are ``float`` for
            scalars, ``str`` for categoricals, and ``(float, float)`` tuples
            for distributions.  Keys absent from ``param_overrides`` use
            model defaults.  Absent categorical keys are **not** pinned
            (the distribution is averaged over all support values with their
            prior weights).

        Returns
        -------
        PlotData
            Fully populated data container ready for the renderer.
        """
        ...
