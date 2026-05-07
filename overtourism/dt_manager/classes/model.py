# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass

if typing.TYPE_CHECKING:
    from civic_digital_twins.dt_model.model import Model


@dataclass
class ModelOutput(ABC):
    """Structured output from model evaluation.

    Subclasses must implement :meth:`to_dict`.
    """

    @abstractmethod
    def to_dict(self) -> dict:
        """Convert the model output to a dictionary.

        Returns
        -------
        dict
            Serialized output data.
        """


class ModelEvaluator(ABC):
    """Model-specific bridge for evaluation and model introspection."""

    @abstractmethod
    def evaluate(
        self,
        model: Model,
        *,
        ensemble_size: int,
        **kwargs: typing.Any,
    ) -> ModelOutput:
        """Evaluate the model and return structured outputs.

        Returns
        -------
        ModelOutput
            Structured evaluation output.
        """

    @abstractmethod
    def build_output(self, data: dict[str, typing.Any]) -> ModelOutput:
        """Rebuild a structured output object from serialized data."""

    @abstractmethod
    def get_index_diffs(
        self, model: Model, values: dict | None = None
    ) -> dict[str, str]:
        """Get human-readable differences in index values from the baseline.

        Returns
        -------
        dict[str, str]
            Human-readable index differences.
        """

    @abstractmethod
    def get_model_values(self, model: Model) -> dict[str, typing.Any]:
        """Get the model's current values as a dictionary.

        Returns
        -------
        dict[str, typing.Any]
            Current model values.
        """
