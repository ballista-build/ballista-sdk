from __future__ import annotations

from typing import Protocol, Sequence
from unittest.mock import Mock

from ballista.types import (
    ArtifactExecutionExecProbe,
    ArtifactExecutionHealthChecks,
    ArtifactExecutionProbe,
    ArtifactExecutionRequirements,
    ArtifactExecutionResourceDependency,
    ArtifactExecutionService,
    ArtifactExecutionTCPService,
    ArtifactExecutionVolume,
    ArtifactInjectedValue,
    ArtifactSettingType,
    ArtifactType,
    ArtifactTypeDependency,
    Bolt,
    Environment,
    EnvironmentArtifactExecutionParameters,
    ExecutableArtifact,
    ExecutableArtifactReference,
    Resource,
    ResourceDependencyInjectedValue,
    ResourceDependencyRequirements,
    ResourceWithArtifactProvider,
)


class EnvironmentExecutionAdapter(Protocol):
    """Adapter for executing artifacts in an environment."""

    def deploy(
        self,
        bolt: Bolt,
        artifacts: Sequence[ExecutableArtifact],
        environment: Environment,
        execution_parameters: EnvironmentArtifactExecutionParameters,
    ):
        """Deploy a Bolt and collection of ExecutableArtifacts in the specified Environment with ArtifactExecutionParameters."""
        ...

    def list_artifact_types(self, environment: Environment) -> Sequence[ArtifactType]:
        """List available ArtifactTypes in the specified environment."""
        ...

    def list_executable_artifacts(self, environment: Environment) -> Sequence[ExecutableArtifactReference]:
        """List ExecutableArtifacts in the specified Environment."""
        ...

    def list_project_bolts(self, projecte_id: str) -> Sequence[Bolt]:
        """List Bolts associated with a Project."""
        ...

    def list_resources(self, environment: Environment) -> Sequence[ResourceWithArtifactProvider]:
        """List available Resources with a providing ArtifactReference in the specified Environment."""
        ...

    def resolve_resource_dependency(
        self, resource_dependency: ArtifactExecutionResourceDependency, environment: Environment
    ) -> ResourceWithArtifactProvider:
        """Resolves a dependency for a resource in the specified Environment. Throws exception if dependency cannot be met."""
        ...

    def teardown(
        self,
        bolt: Bolt,
        artifacts: Sequence[ExecutableArtifact],
        environment: Environment,
        execution_parameters: EnvironmentArtifactExecutionParameters,
    ):
        """Teardown a running bolt."""
        ...


EnvironmentWithExecutionAdapter = tuple[EnvironmentExecutionAdapter, Environment]


#
# This exists until the adapters can do this.
#
def fake_artifact_types() -> list[ArtifactType]:
    docker_type = Mock(ArtifactType, id="docker_image")
    docker_type.name = "Docker Image"

    return [docker_type]


#
# This exists until the adapters can actually retrieve artifacts.
#
def fake_executable_artifacts() -> list[ExecutableArtifactReference]:
    """Creates mock ExecutableArtifact definitions for postgres and redis."""

    # Fake Postgres
    class PostgresRequirements(ResourceDependencyRequirements):
        prefix: str | None = None
        """Key prefix."""
        database_id: str
        """ID of database."""

    postgres = Mock(
        ExecutableArtifact,
        build=None,
        execution=Mock(
            ArtifactExecutionRequirements,
            configs=[],
            healthchecks=Mock(
                ArtifactExecutionHealthChecks,
                alive=None,
                ready=Mock(
                    ArtifactExecutionProbe,
                    exec=Mock(ArtifactExecutionExecProbe, commands=["pg_isready -U $POSTGRES_USER"], shell=True),
                    grpc=None,
                    http=None,
                    port=None,
                ),
                started=Mock(
                    ArtifactExecutionProbe,
                    exec=Mock(ArtifactExecutionExecProbe, commands=["pg_isready -U $POSTGRES_USER"], shell=True),
                    grpc=None,
                    http=None,
                    port=None,
                ),
            ),
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
        resource=Mock(
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
        ),
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

    postgres_resource = postgres.resource
    postgres_resource.id = "postgres"
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

    redis = Mock(
        ExecutableArtifact,
        build=None,
        execution=Mock(
            ArtifactExecutionRequirements,
            configs=[],
            healthchecks=Mock(ArtifactExecutionHealthChecks, alive=None, ready=None, started=None),
            resources=[],
            secrets=[],
            services=[
                Mock(ArtifactExecutionService, grpc=None, http=None, tcp=Mock(ArtifactExecutionTCPService, port=6379))
            ],
            volumes=[],
        ),
        resource=Mock(
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
        ),
        type=Mock(ArtifactTypeDependency, artifact_type_id="docker_image", config={"image": "redis:8"}),
    )
    redis.id = "server"

    execution = redis.execution
    execution.services[0].id = "redis"

    redis_resource = redis.resource
    redis_resource.id = "redis"
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

    return [(postgres, "17.5", "postgres"), (redis, "8", "redis")]
