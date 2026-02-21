from abc import ABC
from enum import StrEnum, auto
from typing import Annotated, Literal

from pydantic import Field

from .common import BaseNamedModel


class SettingDataType(StrEnum):
    BOOL = auto()
    """A boolean."""
    BYTES = auto()
    """Raw bytes."""
    DOUBLE = auto()
    """64-bit floating point number."""
    FLOAT = auto()
    """32-bit floating point number."""
    INT32 = auto()
    """Signed 32-bit integer."""
    INT64 = auto()
    """Signed 64-bit integer."""
    STRING = auto()
    """UTF-8 encoded string."""
    UINT32 = auto()
    """32-bit unsigned integer."""
    UINT64 = auto()
    """Unsigned 64-bit integer."""


SettingValue = bool | bytes | float | str
"""Supported setting value types."""


class BaseSetting(BaseNamedModel, ABC):
    data_type: Annotated[SettingDataType, Field(description="Data type of value.")]


class Config(BaseSetting):
    @property
    def sensitive(self) -> Literal[False]:
        return False


class Secret(BaseSetting):
    @property
    def sensitive(self) -> Literal[True]:
        return True


Setting = Config | Secret
