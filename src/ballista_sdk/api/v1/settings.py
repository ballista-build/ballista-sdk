from abc import ABC
from enum import StrEnum, auto
from typing import Annotated, Literal

from pydantic import Field

from .common import BaseNamedModel


class SettingDataType(StrEnum):
    BOOLEAN = auto()
    """A boolean."""
    BYTES = auto()
    """Raw bytes."""
    INTEGER = auto()
    """32-bit integer."""
    FLOAT = auto()
    """64-bit float."""
    STRING = auto()
    """UTF-8 encoded string."""


class BaseSetting(BaseNamedModel, ABC, frozen=True):
    data_type: Annotated[SettingDataType, Field(description="Data type of value.")]


class Config(BaseSetting):
    @property
    def sensitive(self) -> Literal[False]:
        return False


class Secret(BaseSetting):
    @property
    def sensitive(self) -> Literal[True]:
        return True
