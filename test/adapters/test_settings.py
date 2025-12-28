from dataclasses import dataclass, field

import pytest
from kubernetes import client as kubernetes_client

from ballista_sdk.adapters.docker_compose import DockerComposeSettingsAdapter
from ballista_sdk.adapters.kubernetes import (
    KubernetesConfigsAdapter,
    KubernetesInfrastructureAdapter,
    KubernetesSecretsAdapter,
)
from ballista_sdk.adapters.settings import SettingsAdapter
from ballista_sdk.api.v1 import (
    ArtifactReference,
    BoundSetting,
    ConfigRequirement,
    Environment,
    ResourceConfig,
    ResourceReference,
    ResourceSecret,
    SecretRequirement,
    SettingDataType,
    SettingValue,
)


@dataclass
class MockKubernetesConfigsAdapter(KubernetesConfigsAdapter):
    _persisted: dict[tuple[str, str], kubernetes_client.V1ConfigMap] = field(default_factory=dict)

    def _read_object(self, namespace: str, ref_name: str) -> kubernetes_client.V1ConfigMap | None:
        if obj := self._persisted.get((namespace, ref_name)):
            return obj

    def _write_object(self, namespace: str, ref_name: str, obj: kubernetes_client.V1ConfigMap):
        cache_key = (namespace, ref_name)

        self._persisted[cache_key] = obj
        self._loaded.pop(cache_key, None)


@dataclass
class MockKubernetesSecretsAdapter(KubernetesSecretsAdapter):
    _persisted: dict[tuple[str, str], kubernetes_client.V1Secret] = field(default_factory=dict)

    def _read_object(self, namespace: str, ref_name: str) -> kubernetes_client.V1Secret | None:
        if obj := self._persisted.get((namespace, ref_name)):
            return obj

    def _write_object(self, namespace: str, ref_name: str, obj: kubernetes_client.V1Secret):
        cache_key = (namespace, ref_name)

        self._persisted[cache_key] = obj
        self._loaded.pop(cache_key, None)


@pytest.fixture(
    params=[
        pytest.param("docker_compose", marks=[pytest.mark.unit]),
        pytest.param("mock_kubernetes_configmap", marks=[pytest.mark.unit]),
    ]
)
def configs_adapters(request, kubernetes_adapter: KubernetesInfrastructureAdapter) -> SettingsAdapter:
    match request.param:
        case "docker_compose":
            return DockerComposeSettingsAdapter()
        case "mock_kubernetes_configmap":
            return MockKubernetesConfigsAdapter(kubernetes_adapter)

    raise ValueError()


@pytest.fixture(
    params=[
        pytest.param("docker_compose", marks=[pytest.mark.unit]),
        pytest.param("mock_kubernetes_secret", marks=[pytest.mark.unit]),
    ]
)
def secrets_adapters(request, kubernetes_adapter: KubernetesInfrastructureAdapter) -> SettingsAdapter:
    match request.param:
        case "docker_compose":
            return DockerComposeSettingsAdapter()
        case "mock_kubernetes_secret":
            return MockKubernetesSecretsAdapter(kubernetes_adapter)

    raise ValueError()


@pytest.fixture(
    scope="session", params=["bool_false", "bool_true", "bytes", "float", "integer_neg", "integer_pos", "string"]
)
def sample_settings(request) -> tuple[str, SettingDataType, SettingValue]:
    match request.param:
        case "bool_false":
            data_type, value = SettingDataType.BOOLEAN, False
        case "bool_true":
            data_type, value = SettingDataType.BOOLEAN, True
        case "bytes":
            data_type, value = SettingDataType.BYTES, bytes.fromhex("2EF0F1F2")
        case "float":
            data_type, value = SettingDataType.FLOAT, 1.24
        case "integer_pos":
            data_type, value = SettingDataType.INTEGER, 36
        case "integer_neg":
            data_type, value = SettingDataType.INTEGER, -24593
        case "string":
            data_type, value = SettingDataType.STRING, "burgundy blue hair"
        case _:
            raise ValueError()

    return request.param, data_type, value


@pytest.fixture
def sample_artifact_configs(
    sample_settings: tuple[str, SettingDataType, SettingValue],
) -> tuple[ConfigRequirement, SettingValue]:
    name, data_type, value = sample_settings
    return ConfigRequirement(
        name=name, description=f"{name} description", title=f"{name} Title", data_type=data_type
    ), value


@pytest.fixture
def sample_artifact_secrets(
    sample_settings: tuple[str, SettingDataType, SettingValue],
) -> tuple[SecretRequirement, SettingValue]:
    name, data_type, value = sample_settings
    return SecretRequirement(
        name=name, description=f"{name} description", title=f"{name} Title", data_type=data_type
    ), value


@pytest.fixture
def sample_resource_configs(
    sample_settings: tuple[str, SettingDataType, SettingValue],
) -> tuple[ResourceConfig, SettingValue]:
    name, data_type, value = sample_settings
    return ResourceConfig(
        name=name, description=f"{name} description", title=f"{name} Title", data_type=data_type, shared=True
    ), value


@pytest.fixture
def sample_resource_secrets(
    sample_settings: tuple[str, SettingDataType, SettingValue],
) -> tuple[ResourceSecret, SettingValue]:
    name, data_type, value = sample_settings
    return ResourceSecret(
        name=name, description=f"{name} description", title=f"{name} Title", data_type=data_type, shared=True
    ), value


def _test_setting(settings_adapter, environment, bound_setting, setting_value, known_setting):
    # Setting doesn't exist prior.
    with settings_adapter as sa:
        exists = sa.exists(environment, bound_setting)
        assert exists is False
        with pytest.raises(Exception):
            sa.read(environment, bound_setting)

        known_exists = sa.exists(environment, known_setting)
        assert known_exists is True
        known_value = sa.read(environment, known_setting)
        assert known_value == "commodity"

        sa.write(environment, bound_setting, setting_value)

    # Setting now exists.
    with settings_adapter as sa:
        exists = sa.exists(environment, bound_setting)
        assert exists is True
        value = sa.read(environment, bound_setting)
        assert value == setting_value

        known_exists = sa.exists(environment, known_setting)
        assert known_exists is True
        known_value = sa.read(environment, known_setting)
        assert known_value == "commodity"

        sa.delete(environment, bound_setting)

    # Setting no longer exists.
    with settings_adapter as sa:
        exists = sa.exists(environment, bound_setting)
        assert exists is False
        with pytest.raises(Exception):
            sa.read(environment, bound_setting)

        known_exists = sa.exists(environment, known_setting)
        assert known_exists is True
        known_value = sa.read(environment, known_setting)
        assert known_value == "commodity"


def test_artifact_configs(
    sample_artifact_configs: tuple,
    configs_adapters: SettingsAdapter,
    environment: Environment,
):
    config, setting_value = sample_artifact_configs
    artifact = ArtifactReference("ephemeral", "agasi", "1.2.3")
    bound_config = BoundSetting(setting=config, artifact=artifact)

    # Write a known config to ensure isolation
    known_config = BoundSetting(
        setting=ConfigRequirement(name="known", data_type=SettingDataType.STRING), artifact=artifact
    )
    with configs_adapters as ca:
        ca.write(environment, known_config, "commodity")

    _test_setting(configs_adapters, environment, bound_config, setting_value, known_config)


def test_artifact_secrets(
    sample_artifact_secrets: tuple,
    secrets_adapters: SettingsAdapter,
    environment: Environment,
):
    secret, setting_value = sample_artifact_secrets
    artifact = ArtifactReference("ephemeral", "agasi", "1.2.3")
    bound_secret = BoundSetting(setting=secret, artifact=artifact)

    # Write a known setting to ensure isolation
    known_secret = BoundSetting(
        setting=SecretRequirement(name="known", data_type=SettingDataType.STRING), artifact=artifact
    )
    with secrets_adapters as sa:
        sa.write(environment, known_secret, "commodity")

    _test_setting(secrets_adapters, environment, bound_secret, setting_value, known_secret)


def test_resource_configs(
    sample_resource_configs: tuple,
    configs_adapters: SettingsAdapter,
    environment: Environment,
):
    config, setting_value = sample_resource_configs
    resource = ResourceReference("ephemeral", "resource")
    bound_config = BoundSetting(setting=config, resource=resource)

    # Write a known config to ensure isolation
    known_config = BoundSetting(
        setting=ResourceConfig(name="known", data_type=SettingDataType.STRING, shared=True), resource=resource
    )
    with configs_adapters as ca:
        ca.write(environment, known_config, "commodity")

    _test_setting(configs_adapters, environment, bound_config, setting_value, known_config)


def test_resource_secrets(
    sample_resource_secrets: tuple,
    secrets_adapters: SettingsAdapter,
    environment: Environment,
):
    secret, setting_value = sample_resource_secrets
    resource = ResourceReference("ephemeral", "resource")
    bound_secret = BoundSetting(setting=secret, resource=resource)

    # Write a known setting to ensure isolation
    known_secret = BoundSetting(
        setting=SecretRequirement(name="known", data_type=SettingDataType.STRING), resource=resource
    )
    with secrets_adapters as sa:
        sa.write(environment, known_secret, "commodity")

    _test_setting(secrets_adapters, environment, bound_secret, setting_value, known_secret)
