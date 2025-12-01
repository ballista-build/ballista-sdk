from typing import Literal, NamedTuple, Protocol

from ballista_sdk.api.v1 import Environment, ExecutableArtifact, Project, SettingDataType


class BaseSetting(Protocol):
    data_type: SettingDataType
    name: str
    """Unique identifier."""
    title: str | None
    """Human-readable display name."""
    description: str | None
    """Human-readable description of setting."""


class SharedConfig(BaseSetting):
    """A non-sensitive Setting that is shared across all ExecutableArtifacts in an Environment."""

    sensitive: Literal[False]
    shared: Literal[True]


class SharedSecret(BaseSetting):
    """A sensitive Setting that is shared across all ExecutableArtifacts in an Environment."""

    sensitive: Literal[True]
    shared: Literal[True]


class UniqueConfig(BaseSetting):
    """A non-sensitive Setting that is unique to an ExecutableArtifact in an Environment."""

    sensitive: Literal[False]
    shared: Literal[False]


class UniqueSecret(BaseSetting):
    """A sensitive Setting that is unique to an ExecutableArtifact in an Environment."""

    sensitive: Literal[True]
    shared: Literal[False]


Config = SharedConfig | UniqueConfig
"""Any Config, regardless if it is shared."""
Secret = SharedSecret | UniqueSecret
"""Any Secret, regardless if its shared."""
SharedSetting = SharedConfig | SharedSecret
"""A Setting that is shared across all ExecutableArtifacts in an Environment."""
UniqueSetting = UniqueConfig | UniqueSecret
"""A Setting that is unique to an ExecutableArtifact in an Environment."""
Setting = SharedConfig | SharedSecret | UniqueConfig | UniqueSecret
"""Any valid Setting."""
SettingValue = bool | bytes | float | str
"""Supported setting value types."""


class ExecutableArtifactSetting(NamedTuple):
    environment: Environment
    project: Project
    artifact: ExecutableArtifact | None
    setting: Setting
    instance_ids: list[str] | None


class SettingsAdapter(Protocol):
    def delete(self, setting: ExecutableArtifactSetting):
        """Delete a setting."""
        ...

    def exists(self, setting: ExecutableArtifactSetting) -> bool:
        """Checks if a setting exists."""
        ...

    def read(self, setting: ExecutableArtifactSetting) -> SettingValue:
        """Read the value for a setting."""
        ...

    def write(self, setting: ExecutableArtifactSetting, value: SettingValue):
        """Write a value for a setting."""
        ...
