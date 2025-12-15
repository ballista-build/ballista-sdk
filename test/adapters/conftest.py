import pytest

from ballista_sdk.adapters.infrastructure import InfrastructureAdapter
from ballista_sdk.adapters.settings import SettingsAdapter, SettingValue
from ballista_sdk.api.v1 import (
    Bolt,
    ConfigRequirement,
    ResourceConfig,
    ResourceSecret,
    SecretRequirement,
    SettingDataType,
)


@pytest.fixture(
    scope="session", params=["bool_false", "bool_true", "bytes", "float", "integer_neg", "integer_pos", "string"]
)
def sample_artifact_configs(request) -> tuple[ConfigRequirement, SettingValue]:
    match request.param:
        case "bool_true":
            return ConfigRequirement(name="Bool True", data_type=SettingDataType.BOOLEAN), True
        case "bool_false":
            return ConfigRequirement(name="Bool False", data_type=SettingDataType.BOOLEAN), False
        case "bytes":
            return ConfigRequirement(name="Bytes", data_type=SettingDataType.BYTES), bytes.fromhex("2EF0F1F2")
        case "float":
            return ConfigRequirement(name="Float", data_type=SettingDataType.FLOAT), 1.24
        case "integer_pos":
            return ConfigRequirement(name="Integer Positive", data_type=SettingDataType.INTEGER), 36
        case "integer_neg":
            return ConfigRequirement(name="Integer Negative", data_type=SettingDataType.INTEGER), -24593
        case "string":
            return ConfigRequirement(name="String", data_type=SettingDataType.STRING), "burgundy blue hair"
        case _:
            raise ValueError()


class InfrastructureAdapterTester[Adapter: InfrastructureAdapter]:
    pass


class SettingsAdapterTester[Adapter: SettingsAdapter]:
    pass


@pytest.fixture(scope="session")
def fake_bolts(
    postgres_bolt: Bolt,
) -> list[Bolt]:
    """Creates mock ExecutableArtifact definitions for postgres and redis."""

    return [postgres_bolt]

    # Fake Redis
    # class RedisRequirements(ResourceDependencyRequirements):
    #     prefix: str | None = None
    #     """Key prefix."""
    #     index_id: str | None = None
    #     """ID of index."""

    # redis_probe = Mock(
    #     ArtifactExecutionProbe,
    #     exec=Mock(ArtifactExecutionExecProbe, commands=["redis-cli ping | grep PONG"], shell=True),
    #     grpc=None,
    #     http=None,
    #     tcp=None,
    # )
    # redis = Mock(
    #     ExecutableArtifact,
    #     build=None,
    #     execution=Mock(
    #         ArtifactExecutionRequirements,
    #         configs=[],
    #         healthchecks=Mock(ArtifactExecutionHealthChecks, alive=redis_probe, ready=redis_probe, started=redis_probe),
    #         resources=[],
    #         secrets=[],
    #         services=[
    #             Mock(ArtifactExecutionService, grpc=None, http=None, tcp=Mock(ArtifactExecutionTCPService, port=6379))
    #         ],
    #         volumes=[],
    #     ),
    #     provided_resources=[
    #         Mock(
    #             Resource,
    #             configs=[
    #                 Mock(
    #                     ResourceDependencyInjectedValue,
    #                     description="Host of Redis server",
    #                     shared=True,
    #                     template="",
    #                     type=ArtifactSettingType.STRING,
    #                 ),
    #                 Mock(
    #                     ResourceDependencyInjectedValue,
    #                     description="Port of Redis server",
    #                     shared=True,
    #                     template="",
    #                     type=ArtifactSettingType.INTEGER,
    #                 ),
    #             ],
    #             description="Redis Index",
    #             prefix="REDIS",
    #             requirements=RedisRequirements,
    #             secrets=[
    #                 Mock(
    #                     ResourceDependencyInjectedValue,
    #                     description="Index",
    #                     shared=False,
    #                     template="",
    #                     type=ArtifactSettingType.STRING,
    #                 ),
    #                 Mock(
    #                     ResourceDependencyInjectedValue,
    #                     description="Login user for index",
    #                     shared=False,
    #                     template="",
    #                     type=ArtifactSettingType.STRING,
    #                 ),
    #                 Mock(
    #                     ResourceDependencyInjectedValue,
    #                     description="Login password for index",
    #                     shared=False,
    #                     template=None,
    #                     type=ArtifactSettingType.PASSWORD,
    #                 ),
    #             ],
    #         )
    #     ],
    #     type=Mock(ArtifactTypeDependency, artifact_type_id="docker_image", config={"image": "redis:8"}),
    # )
    # redis.id = "server"

    # execution = redis.execution
    # execution.services[0].id = "redis"

    # redis_resource = redis.provided_resources[0]
    # redis_resource.id = "redis-index"
    # redis_resource.name = "Redis Index"

    # configs = redis_resource.configs
    # configs[0].id = "host"
    # configs[0].name = "Host"
    # configs[1].id = "port"
    # configs[1].name = "Port"

    # secrets = redis_resource.secrets
    # secrets[0].id = "index"
    # secrets[0].name = "Index"
    # secrets[1].id = "username"
    # secrets[1].name = "Username"
    # secrets[2].id = "password"
    # secrets[2].name = "Password"

    # return [(postgres, "17.5", "postgres"), SpecificArtifact(redis, "8", "redis")]
