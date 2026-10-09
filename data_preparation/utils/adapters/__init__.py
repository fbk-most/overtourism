"""Adapters registry. Importing the package registers all the built-in adapters."""

from utils.adapters import popolazione, presenze, strutture, vodafone  # noqa: F401
from utils.adapters.base import (  # noqa: F401
    KIND_DATASETS,
    KIND_SCHEMAS,
    Adapter,
    RawData,
    SchemaMismatchError,
    check_adapter_params,
    get_adapter,
    list_adapters,
    register_adapter,
    validate_schema,
)
