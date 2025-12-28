from typing import Protocol

from ballista_sdk.api.v1 import BoundSetting, Environment, SettingValue


class SettingsOperation(Protocol):
    def delete(self, environment: Environment, bound_setting: BoundSetting):
        """Delete a setting."""
        ...

    def exists(self, environment: Environment, bound_setting: BoundSetting) -> bool:
        """Checks if a setting exists."""
        ...

    def read(self, environment: Environment, bound_setting: BoundSetting) -> SettingValue:
        """Read the value for a setting. Raises Exception if it doesn't exist."""
        ...

    def write(self, environment: Environment, bound_setting: BoundSetting, value: SettingValue):
        """Write a value for a setting."""
        ...


class SettingsAdapter(Protocol):
    @property
    def verify_before_deploy(self) -> bool:
        """Check for required Settings before a deployment."""
        ...

    def __enter__(self) -> SettingsOperation: ...

    def __exit__(self, *args) -> bool | None: ...
