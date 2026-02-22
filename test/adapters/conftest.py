import pytest

from ballista_sdk.adapters import InfrastructureAdapter
from ballista_sdk.adapters.docker_compose import DockerComposeInfrastructureAdapter
from ballista_sdk.adapters.kubernetes import KubernetesAPIInfrastructureAdapter
from ballista_sdk.api.v1 import Bolt


@pytest.fixture(scope="session")
def docker_compose_adapter(fake_bolts: list[Bolt]) -> InfrastructureAdapter:
    return DockerComposeInfrastructureAdapter(_bolts=fake_bolts)


@pytest.fixture(scope="session")
def kubernetes_api_adapter(fake_bolts: list[Bolt]) -> InfrastructureAdapter:
    return KubernetesAPIInfrastructureAdapter(_bolts=fake_bolts)


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
