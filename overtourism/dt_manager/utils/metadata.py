# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExtrasConfig:
    """Declare which dictionary keys should be treated as domain-specific extras.

    Parameters
    ----------
    problem_keys : frozenset[str], optional
        Keys extracted as problem extras.
    proposal_keys : frozenset[str], optional
        Keys extracted as proposal extras.
    scenario_keys : frozenset[str], optional
        Keys extracted as scenario extras.
    """

    problem_keys: frozenset[str] = field(default_factory=frozenset)
    proposal_keys: frozenset[str] = field(default_factory=frozenset)
    scenario_keys: frozenset[str] = field(default_factory=frozenset)

    def problem_extras_from_dict(self, data: dict) -> dict:
        """Extract problem-specific extras from a dictionary.

        Parameters
        ----------
        data : dict
            Source dictionary.

        Returns
        -------
        dict
            Problem extras.
        """
        return {k: data[k] for k in self.problem_keys if k in data}

    def proposal_extras_from_dict(self, data: dict) -> dict:
        """Extract proposal-specific extras from a dictionary.

        Parameters
        ----------
        data : dict
            Source dictionary.

        Returns
        -------
        dict
            Proposal extras.
        """
        return {k: data[k] for k in self.proposal_keys if k in data}

    def scenario_extras_from_dict(self, data: dict) -> dict:
        """Extract scenario-specific extras from a dictionary.

        Parameters
        ----------
        data : dict
            Source dictionary.

        Returns
        -------
        dict
            Scenario extras.
        """
        return {k: data[k] for k in self.scenario_keys if k in data}
