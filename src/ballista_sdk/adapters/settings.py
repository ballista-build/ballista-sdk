from typing import Protocol

from ballista_sdk.api.v1 import Environment, SettingDataType, SettingValue

from .primitives import BoundSetting


class SettingsOperation[E: Environment = Environment](Protocol):
    def delete(self, environment: E, bound_setting: BoundSetting):
        """Delete a setting."""
        ...

    def exists(self, environment: E, bound_setting: BoundSetting) -> bool:
        """Checks if a setting exists."""
        ...

    def read(self, environment: E, bound_setting: BoundSetting) -> SettingValue:
        """Read the value for a setting. Raises Exception if it doesn't exist."""
        ...

    def write(self, environment: E, bound_setting: BoundSetting, value: SettingValue):
        """Write a value for a setting."""
        ...


class SettingsAdapter[E: Environment = Environment](Protocol):
    @property
    def verify_before_deploy(self) -> bool:
        """Check for required Settings before a deployment."""
        ...

    def __enter__(self) -> SettingsOperation[E]: ...

    def __exit__(self, exc_type, exc_value, traceback) -> bool | None: ...


SETTING_DEFAULT_VALUES = {
    SettingDataType.BOOL: False,
    SettingDataType.BYTES: b"",
    SettingDataType.DOUBLE: 0.0,
    SettingDataType.FLOAT: 0.0,
    SettingDataType.INT32: 0,
    SettingDataType.INT64: 0,
    SettingDataType.STRING: "",
    SettingDataType.UINT32: 0,
    SettingDataType.UINT64: 0,
}
"""Default value for each `SettingDataType`."""
