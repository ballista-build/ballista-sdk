from dataclasses import dataclass, field

import pytest
from kubernetes import client as kubernetes_client

from ballista_sdk.adapters.docker_compose.settings import DockerComposeSettingsAdapter
from ballista_sdk.adapters.kubernetes.settings import (
    KubernetesAPIConfigsAdapter,
    KubernetesAPISecretsAdapter,
)
from ballista_sdk.adapters.settings import SettingsAdapter
from ballista_sdk.api.v1 import (
    ArtifactReference,
    BoundSetting,
    ConfigRequirement,
    Environment,
    ResourceConfig,
    ResourceProviderReference,
    ResourceSecret,
    SecretRequirement,
    SettingDataType,
    SettingValue,
)


@dataclass
class MockKubernetesConfigsAdapter(KubernetesAPIConfigsAdapter):
    _persisted: dict[tuple[Environment, str, str], kubernetes_client.V1ConfigMap] = field(default_factory=dict)

    def _read_object(
        self, environment: Environment, namespace: str, ref_name: str
    ) -> kubernetes_client.V1ConfigMap | None:
        if obj := self._persisted.get((environment, namespace, ref_name)):
            return obj

    def _write_object(
        self, environment: Environment, namespace: str, ref_name: str, obj: kubernetes_client.V1ConfigMap
    ):
        cache_key = (environment, namespace, ref_name)

        self._persisted[cache_key] = obj
        self._loaded.pop(cache_key, None)


@dataclass
class MockKubernetesSecretsAdapter(KubernetesAPISecretsAdapter):
    _persisted: dict[tuple[Environment, str, str], kubernetes_client.V1Secret] = field(default_factory=dict)

    def _read_object(
        self, environment: Environment, namespace: str, ref_name: str
    ) -> kubernetes_client.V1Secret | None:
        if obj := self._persisted.get((environment, namespace, ref_name)):
            return obj

    def _write_object(self, environment: Environment, namespace: str, ref_name: str, obj: kubernetes_client.V1Secret):
        cache_key = (environment, namespace, ref_name)

        self._persisted[cache_key] = obj
        self._loaded.pop(cache_key, None)


@pytest.fixture(
    params=[
        pytest.param("docker_compose", marks=[pytest.mark.unit]),
        pytest.param("mock_kubernetes_config_map", marks=[pytest.mark.unit]),
        pytest.param("kubernetes_config_map", marks=[pytest.mark.integration]),
    ]
)
def configs_adapters(request) -> SettingsAdapter:
    match request.param:
        case "docker_compose":
            return DockerComposeSettingsAdapter()
        case "mock_kubernetes_config_map":
            return MockKubernetesConfigsAdapter()
        case "kubernetes_config_map":
            return KubernetesAPIConfigsAdapter()

    raise ValueError()


@pytest.fixture(
    params=[
        pytest.param("docker_compose", marks=[pytest.mark.unit]),
        pytest.param("mock_kubernetes_secret", marks=[pytest.mark.unit]),
        pytest.param("kubernetes_secret", marks=[pytest.mark.integration]),
    ]
)
def secrets_adapters(request) -> SettingsAdapter:
    match request.param:
        case "docker_compose":
            return DockerComposeSettingsAdapter()
        case "mock_kubernetes_secret":
            return MockKubernetesSecretsAdapter()
        case "kubernetes_secret":
            return KubernetesAPISecretsAdapter()

    raise ValueError()


@pytest.fixture(scope="session")
def sample_settings() -> list[tuple[str, SettingDataType, SettingValue]]:
    return [
        ("bool_false", SettingDataType.BOOL, False),
        ("bool_true", SettingDataType.BOOL, True),
        ("bytes", SettingDataType.BYTES, bytes.fromhex("2EF0F1F2")),
        ("float", SettingDataType.FLOAT, 1.24),
        ("int32_pos", SettingDataType.INT32, 36),
        ("int32_neg", SettingDataType.INT32, -24593),
        ("int64_pos", SettingDataType.INT32, 12345678901),
        ("int64_neg", SettingDataType.INT32, -5678901234),
        ("string", SettingDataType.STRING, "burgundy blue hair"),
        ("uint32", SettingDataType.UINT32, 45503),
        ("uint64", SettingDataType.UINT64, 1),
    ]


def _test_setting(
    settings_adapter: SettingsAdapter,
    environment: Environment,
    bound_setting: BoundSetting,
    setting_value: SettingValue,
    known_setting: BoundSetting,
):
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


def test_configs(
    sample_settings: list[tuple[str, SettingDataType, SettingValue]],
    configs_adapters: SettingsAdapter,
    environment: Environment,
    subtests: pytest.Subtests,
):
    artifact = ArtifactReference("ephemeral", "agasi", "1.2.3")
    resource_provider = ResourceProviderReference("ephemeral", "resource")

    for name, data_type, value in sample_settings:
        artifact_config = BoundSetting(
            artifact=artifact,
            setting=ConfigRequirement(
                name=name, description=f"{name} description", title=f"{name} Title", data_type=data_type
            ),
        )
        known_artifact_config = BoundSetting(
            artifact=artifact, setting=ConfigRequirement(name="known", data_type=SettingDataType.STRING)
        )

        with subtests.test(type="artifact", name=name):
            with configs_adapters as ca:
                ca.write(environment, known_artifact_config, "commodity")
            _test_setting(configs_adapters, environment, artifact_config, value, known_artifact_config)

        resource_config = BoundSetting(
            resource_provider=resource_provider,
            setting=ResourceConfig(
                name=name, description=f"{name} description", title=f"{name} Title", data_type=data_type, shared=True
            ),
        )
        known_resource_config = BoundSetting(
            resource_provider=resource_provider,
            setting=ResourceConfig(name="known", data_type=SettingDataType.STRING, shared=True),
        )
        with subtests.test(type="resource", name=name):
            with configs_adapters as ca:
                ca.write(environment, known_resource_config, "commodity")
            _test_setting(configs_adapters, environment, resource_config, value, known_resource_config)


def test_secrets(
    sample_settings: list[tuple[str, SettingDataType, SettingValue]],
    secrets_adapters: SettingsAdapter,
    environment: Environment,
    subtests: pytest.Subtests,
):
    artifact = ArtifactReference("ephemeral", "agasi", "1.2.3")
    resource_provider = ResourceProviderReference("ephemeral", "resource")

    for name, data_type, value in sample_settings:
        artifact_secret = BoundSetting(
            artifact=artifact,
            setting=SecretRequirement(
                name=name, description=f"{name} description", title=f"{name} Title", data_type=data_type
            ),
        )
        known_artifact_secret = BoundSetting(
            artifact=artifact, setting=SecretRequirement(name="known", data_type=SettingDataType.STRING)
        )

        with subtests.test(type="artifact", name=name):
            with secrets_adapters as sa:
                sa.write(environment, known_artifact_secret, "commodity")
            _test_setting(secrets_adapters, environment, artifact_secret, value, known_artifact_secret)

        resource_secret = BoundSetting(
            resource_provider=resource_provider,
            setting=ResourceSecret(
                name=name, description=f"{name} description", title=f"{name} Title", data_type=data_type, shared=True
            ),
        )
        known_resource_secret = BoundSetting(
            resource_provider=resource_provider,
            setting=ResourceSecret(name="known", data_type=SettingDataType.STRING, shared=True),
        )
        with subtests.test(type="resource", name=name):
            with secrets_adapters as sa:
                sa.write(environment, known_resource_secret, "commodity")
            _test_setting(secrets_adapters, environment, resource_secret, value, known_resource_secret)
