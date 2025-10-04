from unittest.mock import Mock

import pytest

from ballista_sdk.types import (
    ArtifactExecutionExecProbe,
    ArtifactExecutionHealthChecks,
    ArtifactExecutionProbe,
    ArtifactExecutionRequirements,
    ArtifactExecutionService,
    ArtifactExecutionTCPService,
    ArtifactExecutionVolume,
    ArtifactInjectedValue,
    ArtifactSettingType,
    ArtifactTypeDependency,
    ExecutableArtifact,
    Resource,
    ResourceDependencyInjectedValue,
    ResourceDependencyRequirements,
    SpecificArtifact,
)


@pytest.fixture(scope="session")
def fake_executable_artifacts() -> list[SpecificArtifact]:
    """Creates mock ExecutableArtifact definitions for postgres and redis."""

    # Fake Postgres
    class PostgresRequirements(ResourceDependencyRequirements):
        prefix: str | None = None
        """Key prefix."""
        database_id: str
        """ID of database."""

    postgres_probe = Mock(
        ArtifactExecutionProbe,
        exec=Mock(ArtifactExecutionExecProbe, commands=["pg_isready -U $POSTGRES_USER"], shell=True),
        grpc=None,
        http=None,
        port=None,
    )
    postgres = Mock(
        ExecutableArtifact,
        build=None,
        execution=Mock(
            ArtifactExecutionRequirements,
            configs=[],
            healthchecks=Mock(
                ArtifactExecutionHealthChecks, alive=postgres_probe, ready=postgres_probe, started=postgres_probe
            ),
            id="postgres-database",
            resources=[],
            secrets=[
                Mock(
                    ArtifactInjectedValue,
                    alias="POSTGRES_USER",
                    description="Username for the default/root login.",
                    id="root_user",
                    name="Root username",
                    template="postgres",
                    type=ArtifactSettingType.STRING,
                ),
                Mock(
                    ArtifactInjectedValue,
                    alias="POSTGRES_PASSWORD",
                    description="Password for the default/root login",
                    id="root_password",
                    name="Root Password",
                    template=None,
                    type=ArtifactSettingType.PASSWORD,
                ),
            ],
            services=[
                Mock(ArtifactExecutionService, grpc=None, http=None, tcp=Mock(ArtifactExecutionTCPService, port=5432))
            ],
            volumes=[Mock(ArtifactExecutionVolume, capacity=0.1, path="/var/lib/postgresql/data", persistent=True)],
        ),
        provided_resources=[
            Mock(
                Resource,
                configs=[
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Host of Postgres server.",
                        shared=True,
                        template="",
                        type=ArtifactSettingType.STRING,
                    ),
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Port Postgres server listens on.",
                        shared=True,
                        template="",
                        type=ArtifactSettingType.INTEGER,
                    ),
                ],
                description="Postgres Database",
                prefix="POSTGRES",
                requirements=PostgresRequirements,
                secrets=[
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Name of postgres database",
                        shared=False,
                        template="",
                        type=ArtifactSettingType.STRING,
                    ),
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Login username to access database",
                        shared=False,
                        template="",
                        type=ArtifactSettingType.STRING,
                    ),
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Login password to access database",
                        shared=False,
                        template=None,
                        type=ArtifactSettingType.PASSWORD,
                    ),
                ],
            )
        ],
        type=Mock(ArtifactTypeDependency, artifact_type_id="docker_image", config={"image": "postgres:17.5"}),
    )
    postgres.id = "server"

    execution = postgres.execution
    execution.services[0].id = "postgres"
    execution.secrets[0].id = "user"
    execution.secrets[0].name = "User"
    execution.secrets[1].id = "password"
    execution.secrets[1].name = "Password"
    execution.volumes[0].id = "data"
    execution.volumes[0].name = "PostgreSQL Data"

    postgres_resource = postgres.provided_resources[0]
    postgres_resource.id = "postgres-database"
    postgres_resource.name = "Postgres Database"

    configs = postgres_resource.configs
    configs[0].id = "host"
    configs[0].name = "Host"
    configs[1].id = "port"
    configs[1].name = "Port"

    secrets = postgres_resource.secrets
    secrets[0].id = "database"
    secrets[0].name = "Database"
    secrets[1].id = "username"
    secrets[1].name = "Username"
    secrets[2].id = "password"
    secrets[2].name = "Password"

    # Fake Redis
    class RedisRequirements(ResourceDependencyRequirements):
        prefix: str | None = None
        """Key prefix."""
        index_id: str | None = None
        """ID of index."""

    redis_probe = Mock(
        ArtifactExecutionProbe,
        exec=Mock(ArtifactExecutionExecProbe, commands=["redis-cli ping | grep PONG"], shell=True),
        grpc=None,
        http=None,
        tcp=None,
    )
    redis = Mock(
        ExecutableArtifact,
        build=None,
        execution=Mock(
            ArtifactExecutionRequirements,
            configs=[],
            healthchecks=Mock(ArtifactExecutionHealthChecks, alive=redis_probe, ready=redis_probe, started=redis_probe),
            resources=[],
            secrets=[],
            services=[
                Mock(ArtifactExecutionService, grpc=None, http=None, tcp=Mock(ArtifactExecutionTCPService, port=6379))
            ],
            volumes=[],
        ),
        provided_resources=[
            Mock(
                Resource,
                configs=[
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Host of Redis server",
                        shared=True,
                        template="",
                        type=ArtifactSettingType.STRING,
                    ),
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Port of Redis server",
                        shared=True,
                        template="",
                        type=ArtifactSettingType.INTEGER,
                    ),
                ],
                description="Redis Index",
                prefix="REDIS",
                requirements=RedisRequirements,
                secrets=[
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Index",
                        shared=False,
                        template="",
                        type=ArtifactSettingType.STRING,
                    ),
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Login user for index",
                        shared=False,
                        template="",
                        type=ArtifactSettingType.STRING,
                    ),
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Login password for index",
                        shared=False,
                        template=None,
                        type=ArtifactSettingType.PASSWORD,
                    ),
                ],
            )
        ],
        type=Mock(ArtifactTypeDependency, artifact_type_id="docker_image", config={"image": "redis:8"}),
    )
    redis.id = "server"

    execution = redis.execution
    execution.services[0].id = "redis"

    redis_resource = redis.provided_resources[0]
    redis_resource.id = "redis-index"
    redis_resource.name = "Redis Index"

    configs = redis_resource.configs
    configs[0].id = "host"
    configs[0].name = "Host"
    configs[1].id = "port"
    configs[1].name = "Port"

    secrets = redis_resource.secrets
    secrets[0].id = "index"
    secrets[0].name = "Index"
    secrets[1].id = "username"
    secrets[1].name = "Username"
    secrets[2].id = "password"
    secrets[2].name = "Password"

    return [SpecificArtifact(postgres, "17.5", "postgres"), SpecificArtifact(redis, "8", "redis")]
