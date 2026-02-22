import base64
from dataclasses import dataclass, field
from typing import Literal, Protocol, Self, cast

from kubernetes import client

from ballista_sdk.adapters.settings import SettingsAdapter
from ballista_sdk.api.v1 import (
    ArtifactReference,
    BoundSetting,
    Environment,
    ResourceReference,
    ResourceSetting,
    Setting,
    SettingDataType,
    SettingValue,
)

from .environments import KubernetesEnvironmentConfig, get_environment_config, get_kubernetes_client
from .resources import KubernetesMetadata


class KubernetesSettingsAdapter(SettingsAdapter, Protocol):
    def add_artifact_setting(self, container_spec: dict, artifact_reference: ArtifactReference, setting: Setting): ...

    def add_resource_setting(
        self,
        container_spec: dict,
        artifact_reference: ArtifactReference,
        resource_reference: ResourceReference,
        resource_setting: ResourceSetting,
        prefix: str,
        instance: list[str],
    ): ...


@dataclass
class BaseKubernetesAPISettingsAdapter[SettingKind: object]:
    """SettingsAdapter using the Kubernetes API."""

    _loaded: dict[tuple[Environment, str, str], SettingKind] = field(default_factory=dict, init=False)
    """Loaded objects."""
    _pending_writes: dict[tuple[Environment, str, str], SettingKind] = field(default_factory=dict, init=False)
    """Objects pending being written."""
    _pending_deletes: set[tuple[Environment, str, str]] = field(default_factory=set, init=False)
    """Objects pending being deleted."""

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args) -> bool | None:
        for pending, obj in self._pending_writes.items():
            self._write_object(*pending, obj)

        self._pending_writes.clear()

        for pending in self._pending_deletes:
            self._delete_object(*pending)

        self._pending_deletes.clear()

    def _get_artifact_settings_refname(self, artifact_reference: ArtifactReference) -> str:
        return f"{artifact_reference.project_name}.{artifact_reference.artifact_name}"

    def _get_resource_settings_refname(self, resource_reference: ResourceReference) -> str:
        return f"{resource_reference.project_name}.resources.{resource_reference.resource_name}"

    def _add_setting_reference(
        self, container_spec: dict, ref_name: str, sensitive: bool, required: bool, prefix: str | None
    ):
        ref_type = "secretRef" if sensitive else "configMapRef"
        reference = {"name": ref_name, "optional": not required}

        env: dict[str, dict | str] = {ref_type: reference}
        if prefix:
            env["prefix"] = prefix + "_"

        if "envFrom" not in container_spec:
            container_spec["envFrom"] = [env]
        elif env not in container_spec["envFrom"]:
            container_spec["envFrom"].append(env)

    def add_artifact_setting(self, container_spec: dict, artifact_reference: ArtifactReference, setting: Setting):
        self._add_setting_reference(
            container_spec,
            self._get_artifact_settings_refname(artifact_reference),
            setting.sensitive,
            setting.sensitive,
            None,
        )

    def add_resource_setting(
        self,
        container_spec: dict,
        artifact_reference: ArtifactReference,
        resource_reference: ResourceReference,
        resource_setting: ResourceSetting,
        prefix: str,
        instance: list[str],
    ):
        if resource_setting.shared:
            # Shared setting means we reference it into the artifact
            self._add_setting_reference(
                container_spec,
                self._get_resource_settings_refname(resource_reference),
                resource_setting.sensitive,
                True,
                prefix,
            )

        else:
            # Unique setting is already inside the normal artifact settings
            self.add_artifact_setting(container_spec, artifact_reference, resource_setting)

    def _get_bound_setting_metadata(
        self, environment: Environment, environment_config: KubernetesEnvironmentConfig, bound_setting: BoundSetting
    ) -> KubernetesMetadata:
        if bound_setting.artifact:
            namespace = _get_reference_kubernetes_namespace(environment, environment_config, bound_setting.artifact)
            name = self._get_artifact_settings_refname(bound_setting.artifact)

            return {"labels": {}, "name": name, "namespace": namespace}
        elif bound_setting.resource:
            namespace = _get_reference_kubernetes_namespace(environment, environment_config, bound_setting.resource)
            name = self._get_resource_settings_refname(bound_setting.resource)

            return {"labels": {}, "name": name, "namespace": namespace}
        else:
            raise ValueError()

    def _get_bound_setting_names(
        self, environment: Environment, environment_config: KubernetesEnvironmentConfig, bound_setting: BoundSetting
    ) -> tuple[str, str]:
        if bound_setting.artifact:
            return _get_reference_kubernetes_namespace(
                environment, environment_config, bound_setting.artifact
            ), self._get_artifact_settings_refname(bound_setting.artifact)
        elif bound_setting.resource:
            return _get_reference_kubernetes_namespace(
                environment, environment_config, bound_setting.resource
            ), self._get_resource_settings_refname(bound_setting.resource)
        else:
            raise ValueError()

    def _delete_object(self, environment: Environment, namespace: str, ref_name: str):
        cache_key = (environment, namespace, ref_name)

        self._loaded.pop(cache_key, None)

    def delete(self, environment: Environment, bound_setting: BoundSetting):
        """Delete the value stored for the BoundSetting in specified Environment."""

        environment_config = get_environment_config(environment)
        namespace, ref_name = self._get_bound_setting_names(environment, environment_config, bound_setting)

        # Attempt to read a new copy of the object or use one that has pending writes.
        obj = self._pending_writes.get((environment, namespace, ref_name)) or self._read_object(
            environment, namespace, ref_name
        )

        if obj is None:
            raise ValueError()

        self._delete_object_value(obj, bound_setting.setting)
        self._pending_writes[(environment, namespace, ref_name)] = obj

    def exists(self, environment: Environment, bound_setting: BoundSetting) -> bool:
        """Checks if the value for the BoundSetting exists/persists."""

        environment_config = get_environment_config(environment)
        namespace, ref_name = self._get_bound_setting_names(environment, environment_config, bound_setting)
        obj = self._read_cached_object(environment, namespace, ref_name)
        if not obj:
            return False

        try:
            self._get_object_value(obj, bound_setting.setting)
            return True
        except Exception:
            return False

    def _read_object(self, environment: Environment, namespace: str, ref_name: str) -> SettingKind | None:
        return None

    def _read_cached_object(self, environment: Environment, namespace: str, ref_name: str) -> SettingKind | None:
        cache_key = (environment, namespace, ref_name)

        if loaded_object := self._loaded.get(cache_key):
            return loaded_object

        return self._read_object(environment, namespace, ref_name)

    def read(self, environment: Environment, bound_setting: BoundSetting) -> SettingValue:
        """Retrieve the value for the BoundSetting in the specified Environment."""

        environment_config = get_environment_config(environment)
        namespace, ref_name = self._get_bound_setting_names(environment, environment_config, bound_setting)
        obj = self._read_cached_object(environment, namespace, ref_name)

        if obj is None:
            raise ValueError()

        return self._get_object_value(obj, bound_setting.setting)

    def _create_object(
        self, environment: Environment, environment_config: KubernetesEnvironmentConfig, bound_setting: BoundSetting
    ) -> SettingKind: ...

    def _get_object_value(self, obj: SettingKind, setting: Setting) -> SettingValue: ...

    def _set_object_value(self, obj: SettingKind, setting: Setting, value: SettingValue): ...

    def _delete_object_value(self, obj: SettingKind, setting: Setting): ...

    def _write_object(self, environment: Environment, namespace: str, ref_name: str, obj: SettingKind):
        cache_key = (environment, namespace, ref_name)

        self._loaded.pop(cache_key, None)

    def write(
        self,
        environment: Environment,
        bound_setting: BoundSetting,
        value: SettingValue,
    ):
        environment_config = get_environment_config(environment)
        namespace, ref_name = self._get_bound_setting_names(environment, environment_config, bound_setting)

        # Attempt to read a new copy of the object or use one that has pending writes.
        obj = (
            self._pending_writes.get((environment, namespace, ref_name))
            or self._read_object(environment, namespace, ref_name)
            or self._create_object(environment, environment_config, bound_setting)
        )

        self._set_object_value(obj, bound_setting.setting, value)
        self._pending_writes[(environment, namespace, ref_name)] = obj


@dataclass
class KubernetesAPIConfigsAdapter(BaseKubernetesAPISettingsAdapter[client.V1ConfigMap], KubernetesSettingsAdapter):
    """Configs adapter using the Kubernetes API."""

    @property
    def verify_before_deploy(self) -> Literal[True]:
        return True

    def _create_object(
        self, environment: Environment, environment_config: KubernetesEnvironmentConfig, bound_setting: BoundSetting
    ) -> client.V1ConfigMap:
        return client.V1ConfigMap(
            api_version="v1",
            kind="ConfigMap",
            metadata=self._get_bound_setting_metadata(environment, environment_config, bound_setting),
        )

    def _read_object(self, environment: Environment, namespace: str, ref_name: str) -> client.V1ConfigMap | None:
        api_client = get_kubernetes_client(environment)
        api = client.CoreV1Api(api_client)
        try:
            return api.read_namespaced_config_map(name=ref_name, namespace=namespace)
        except client.ApiException:
            return None

    def _write_object(self, environment: Environment, namespace: str, ref_name: str, obj: client.V1ConfigMap):
        api_client = get_kubernetes_client(environment)

        api = client.CoreV1Api(api_client)
        try:
            api.read_namespaced_config_map(name=ref_name, namespace=namespace)
        except client.ApiException:
            api.create_namespaced_config_map(namespace=namespace, body=obj)
        else:
            api.replace_namespaced_config_map(name=ref_name, namespace=namespace, body=obj)

        self._loaded.pop((environment, namespace, ref_name), None)

    def _get_object_value(self, obj: client.V1ConfigMap, setting: Setting) -> SettingValue:
        source = obj.binary_data if setting.data_type == SettingDataType.BYTES else obj.data

        if source and (value := source.get(setting.name)):
            match setting.data_type:
                case SettingDataType.BOOL:
                    return value.lower() == "true"
                case SettingDataType.BYTES:
                    return base64.b64decode(value)
                case SettingDataType.DOUBLE | SettingDataType.FLOAT:
                    return float(value)
                case SettingDataType.INT32 | SettingDataType.INT64 | SettingDataType.UINT32 | SettingDataType.UINT64:
                    return int(value)
                case SettingDataType.STRING:
                    return value

        raise ValueError()

    def _set_object_value(self, obj: client.V1ConfigMap, setting: Setting, value: SettingValue):
        if setting.data_type == SettingDataType.BYTES:
            # Bytes go into binary_data as a base64 encoded string.
            encoded_value = base64.b64encode(cast(bytes, value)).decode()

            obj.binary_data = obj.binary_data or {}
            obj.binary_data[setting.name] = encoded_value
        else:
            encoded_value = str(value)

            obj.data = obj.data or {}
            obj.data[setting.name] = encoded_value

    def _delete_object_value(self, obj: client.V1ConfigMap, setting: Setting):
        if setting.data_type == SettingDataType.BYTES:
            if obj.binary_data and setting.name in obj.binary_data:
                obj.binary_data.pop(setting.name)
                return

        else:
            if obj.data and setting.name in obj.data:
                obj.data.pop(setting.name)
                return

        raise ValueError()


@dataclass
class KubernetesAPISecretsAdapter(BaseKubernetesAPISettingsAdapter[client.V1Secret], KubernetesSettingsAdapter):
    @property
    def verify_before_deploy(self) -> Literal[True]:
        return True

    def _create_object(
        self, environment: Environment, environment_config: KubernetesEnvironmentConfig, bound_setting: BoundSetting
    ) -> client.V1Secret:
        return client.V1Secret(
            api_version="v1",
            kind="Secret",
            metadata=self._get_bound_setting_metadata(environment, environment_config, bound_setting),
            type="Opaque",
        )

    def _read_object(self, environment: Environment, namespace: str, ref_name: str) -> client.V1Secret | None:
        api_client = get_kubernetes_client(environment)

        api = client.CoreV1Api(api_client)
        try:
            return api.read_namespaced_secret(name=ref_name, namespace=namespace)
        except client.ApiException:
            return None

    def _write_object(self, environment: Environment, namespace: str, ref_name: str, obj: client.V1Secret):
        api_client = get_kubernetes_client(environment)

        api = client.CoreV1Api(api_client)
        try:
            api.read_namespaced_secret(name=ref_name, namespace=namespace)
        except client.ApiException:
            api.create_namespaced_secret(namespace=namespace, body=obj)
        else:
            api.replace_namespaced_secret(name=ref_name, namespace=namespace, body=obj)

        self._loaded.pop((environment, namespace, ref_name), None)

    def _get_object_value(self, obj: client.V1Secret, setting: Setting) -> SettingValue:
        if obj.data and (value := obj.data.get(setting.name)):
            bytes_value = base64.b64decode(value)

            if setting.data_type == SettingDataType.BYTES:
                return bytes_value

            decoded_string = bytes_value.decode()
            match setting.data_type:
                case SettingDataType.BOOL:
                    return decoded_string.lower() == "true"
                case SettingDataType.DOUBLE | SettingDataType.FLOAT:
                    return float(decoded_string)
                case SettingDataType.INT32 | SettingDataType.INT64 | SettingDataType.UINT32 | SettingDataType.UINT64:
                    return int(decoded_string)
                case _:
                    return decoded_string

        raise ValueError()

    def _set_object_value(self, obj: client.V1Secret, setting: Setting, value: SettingValue):
        bytes_value = cast(bytes, value) if setting.data_type == SettingDataType.BYTES else str(value).encode()

        obj.data = obj.data or {}
        obj.data[setting.name] = base64.b64encode(bytes_value).decode()

    def _delete_object_value(self, obj: client.V1Secret, setting: Setting):
        if obj.data and setting.name in obj.data:
            del obj.data[setting.name]

        else:
            raise ValueError()


@dataclass
class ExternalSecretsAdapter(KubernetesSettingsAdapter):
    @property
    def verify_before_deploy(self) -> Literal[False]:
        return False


def _get_reference_kubernetes_namespace(
    environment: Environment,
    environment_config: KubernetesEnvironmentConfig,
    reference: ArtifactReference | ResourceReference,
) -> str:
    if environment_config.project_namespaces:
        return f"{reference.project_name}-{environment.name}"
    else:
        return environment.name
