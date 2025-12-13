from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from ballista_sdk.api.v1 import ArtifactReference, Environment, ResourceReference, SettingDataType


class BaseSetting(Protocol):
    @property
    def data_type(self) -> SettingDataType:
        """DataType of the setting value."""
        ...

    @property
    def description(self) -> str | None:
        """Description"""
        ...

    @property
    def name(self) -> str:
        """Separated pieces that form a unique identifer."""
        ...

    @property
    def title(self) -> str | None:
        """Title"""
        ...


class Config(BaseSetting, Protocol):
    """A non-sensitive Setting."""

    @property
    def sensitive(self) -> Literal[False]:
        return False


class Secret(BaseSetting, Protocol):
    """A sensitive Setting."""

    @property
    def sensitive(self) -> Literal[True]:
        return True


Setting = Config | Secret
"""Any valid Setting."""
SettingValue = bool | bytes | float | str
"""Supported setting value types."""


@dataclass
class BoundSetting:
    """A Setting bound to an owner."""

    setting: Setting
    artifact: ArtifactReference | None = None
    """Artifact setting exists in."""
    resource: ResourceReference | None = None
    """Resource setting exists in."""
    resource_instance: Sequence[str] | None = None


class SettingsAdapter(Protocol):
    @property
    def verify_before_deploy(self) -> bool:
        """Check for required Settings before a deployment."""
        ...

    def delete(self, environment: Environment, bound_setting: BoundSetting):
        """Delete a setting."""
        ...

    def exists(self, environment: Environment, bound_setting: BoundSetting) -> bool:
        """Checks if a setting exists."""
        ...

    def read(self, environment: Environment, bound_setting: BoundSetting) -> SettingValue:
        """Read the value for a setting."""
        ...

    def write(self, environment: Environment, bound_setting: BoundSetting, value: SettingValue):
        """Write a value for a setting."""
        ...
