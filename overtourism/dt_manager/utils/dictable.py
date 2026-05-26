# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from enum import Enum
from typing import Any, TypeVar

from numpy import generic as numpy_generic

TDictable = TypeVar("TDictable", bound="Dictable")


class Dictable:
    """Base class providing dictionary conversion functionality.

    This class implements a method to convert nested objects into dictionaries,
    handling lists and nested Dictable objects recursively.

    Methods
    -------
    to_dict() -> dict
        Convert the object and its nested attributes to a dictionary
    """

    def to_dict(self) -> dict[str, Any]:
        """Convert the object to a dictionary recursively.

        Returns
        -------
        dict
            Dictionary representation of the object
        """
        return {key: self.to_plain(value) for key, value in self.__dict__.items()}

    @classmethod
    def from_dict(cls: type[TDictable], data: dict[str, Any]) -> TDictable:
        """Create an instance from a dictionary.

        This method can be overridden in subclasses to handle specific attribute types.

        Parameters
        ----------
        data : dict
            Dictionary containing the data to populate the object
        """
        obj = cls.__new__(cls)
        for key, value in data.items():
            setattr(obj, key, value)
        return obj

    def to_plain(self, value: Any) -> Any:
        """Convert nested values into plain Python objects.

        Parameters
        ----------
        value : Any
            Value to convert.

        Returns
        -------
        Any
            Plain Python representation of the value.
        """
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, numpy_generic):
            return value.item()
        if isinstance(value, dict):
            return {
                self.to_plain(key): self.to_plain(item) for key, item in value.items()
            }
        if isinstance(value, (list, set, tuple)):
            return [self.to_plain(item) for item in value]
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if hasattr(value, "tolist"):
            return value.tolist()
        if hasattr(value, "__dict__"):
            return {key: self.to_plain(item) for key, item in value.__dict__.items()}
        return value
