import base64
import os
from dataclasses import dataclass, field
from typing import Literal, Self, cast

import dotenv

from ballista_sdk.adapters import SettingsAdapter
from ballista_sdk.adapters.primitives import BoundSetting
from ballista_sdk.api.v1 import (
    Environment,
    SettingDataType,
    SettingValue,
)

from .generation import generate_artifact_setting_envfile_filename, generate_resource_setting_envfile_filename


@dataclass
class DockerComposeSettingsAdapter(SettingsAdapter):
    _loaded: dict[str, dict[str, str]] = field(default_factory=dict)
    _pending_writes: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def verify_before_deploy(self) -> Literal[True]:
        return True

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args) -> bool | None:
        for filename, obj in self._pending_writes.items():
            self._write_object(filename, obj)

    def _get_bound_setting_env_filename(self, environment: Environment, bound_setting: BoundSetting) -> str:
        if bound_setting.artifact:
            return generate_artifact_setting_envfile_filename(bound_setting.artifact, bound_setting.setting.sensitive)
        elif bound_setting.provided_resource:
            return generate_resource_setting_envfile_filename(
                bound_setting.provided_resource, bound_setting.setting.sensitive
            )
        else:
            raise ValueError("BoundSetting needs an artifact or resource reference.")

    def _delete_object(self, filename: str):
        self._loaded.pop(filename, None)

    def delete(self, environment: Environment, bound_setting: BoundSetting):
        filename = self._get_bound_setting_env_filename(environment, bound_setting)

        obj = self._pending_writes.get(filename) or self._read_object(filename)
        if obj is None:
            raise ValueError()

        obj.pop(bound_setting.setting.name, None)
        self._pending_writes[filename] = obj

    def exists(self, environment: Environment, bound_setting: BoundSetting) -> bool:
        filename = self._get_bound_setting_env_filename(environment, bound_setting)

        obj = self._read_cached_object(filename)
        if obj is None:
            return False

        return bound_setting.setting.name in obj

    def _read_object(self, filename: str) -> dict[str, str] | None:
        if os.path.exists(filename):
            return {k: v for k, v in dotenv.dotenv_values(filename, interpolate=False).items() if v is not None}

        return None

    def _read_cached_object(self, filename) -> dict[str, str] | None:
        if loaded_object := self._loaded.get(filename):
            return loaded_object

        return self._read_object(filename)

    def read(self, environment: Environment, bound_setting: BoundSetting) -> SettingValue:
        filename = self._get_bound_setting_env_filename(environment, bound_setting)

        obj = self._read_cached_object(filename)
        if obj is None or (value := obj[bound_setting.setting.name]) is None:
            raise ValueError()

        match bound_setting.setting.type:
            case SettingDataType.BYTES:
                return base64.b64decode(value)
            case SettingDataType.BOOL:
                return value.lower() == "true"
            case SettingDataType.DOUBLE | SettingDataType.FLOAT:
                return float(value)
            case SettingDataType.INT32 | SettingDataType.INT64 | SettingDataType.UINT32 | SettingDataType.UINT64:
                return int(value)
            case _:
                return value

    def _write_object(self, filename: str, obj: dict[str, str]):
        # Ensure file exists
        with open(filename, "w"):
            pass

        for k, v in obj.items():
            dotenv.set_key(filename, k, v)

        self._loaded.pop(filename, None)

    def write(self, environment: Environment, bound_setting: BoundSetting, value: SettingValue):
        filename = self._get_bound_setting_env_filename(environment, bound_setting)

        obj = self._pending_writes.get(filename) or self._read_object(filename) or {}

        if bound_setting.setting.type == SettingDataType.BYTES:
            encoded_value = base64.b64encode(cast(bytes, value)).decode()
        else:
            encoded_value = str(value)
        obj[bound_setting.setting.name] = encoded_value

        self._pending_writes[filename] = obj
