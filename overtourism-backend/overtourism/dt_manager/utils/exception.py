# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations


class StoreException(Exception):
    """Base exception for store-related errors."""


class EntityDoesNotExist(StoreException):
    """Raised when an entity cannot be found in the store."""


class ScenarioManagerException(Exception):
    """Base exception for scenario, proposal, and configuration errors."""


class ScenarioAlreadyExists(ScenarioManagerException):
    """Raised when a scenario already exists."""


class ScenarioDoesNotExist(ScenarioManagerException):
    """Raised when a scenario cannot be found."""


class SessionDoesNotExist(ScenarioManagerException):
    """Raised when a session cannot be found."""


class ProposalAlreadyExists(ScenarioManagerException):
    """Raised when a proposal already exists."""


class ProposalDoesNotExist(ScenarioManagerException):
    """Raised when a proposal cannot be found."""


class EvaluationManagerException(ScenarioManagerException):
    """Base exception for evaluation errors."""


class EvaluationAlreadyExists(EvaluationManagerException):
    """Raised when an evaluation already exists."""


class EvaluationDoesNotExist(EvaluationManagerException):
    """Raised when an evaluation cannot be found."""


class ConfigurationError(ScenarioManagerException):
    """Raised when an invalid configuration is encountered."""
