from unittest.mock import Mock

import pytest
from pydantic import BaseModel

from ballista_sdk.types import (
    Artifact,
    ArtifactExecutionComputeParameters,
    ArtifactExecutionExternalServiceParameters,
    ArtifactExecutionHealthChecks,
    ArtifactExecutionHTTPProbe,
    ArtifactExecutionProbe,
    ArtifactExecutionRequirements,
    ArtifactExecutionResourceDependency,
    ArtifactExecutionService,
    ArtifactExecutionVolume,
    ArtifactExecutionVolumeParameters,
    ArtifactInjectedValue,
    ArtifactSettingType,
    ArtifactTypeDependency,
    Bolt,
    DefaultExecutionParameters,
    Environment,
    EnvironmentTier,
    ExecutionParameters,
    Project,
    Resource,
    ResourceDependencyInjectedValue,
)


@pytest.fixture(scope="session")
def project():
    return Mock(Project, id="typical", name="Typical Project")


@pytest.fixture(scope="session")
def docker_image_artifact_type_dependency():
    return Mock(ArtifactTypeDependency, config={"image": "hello-world:latest"}, id="docker_image")


@pytest.fixture(scope="session", params=["empty", "simple", "typical", "resource_provider"])
def bolt(docker_image_artifact_type_dependency: ArtifactTypeDependency, request):
    match request.param:
        case "empty":
            # An empty project, having no artifacts. Invalid.
            return Mock(
                Bolt, buildable_artifacts=[], artifacts=[], executable_artifacts=[], project_id="empty", version="1"
            )
        case "simple":
            # A simple project with one ExecutableArtifact
            # Name cannot be mocked via the constructor.
            volume_a = Mock(
                ArtifactExecutionVolume, capacity=0.01, id="volume_a", path="/var/volume_a", persistent=True
            )
            volume_a.name = "Volume A"
            artifacts = [
                Mock(
                    Artifact,
                    build=None,
                    execution=Mock(
                        ArtifactExecutionRequirements,
                        configs=[Mock(ArtifactInjectedValue, alias=None, id="option_a", type="string")],
                        healthchecks=Mock(
                            ArtifactExecutionHealthChecks,
                            alive=None,
                            ready=Mock(
                                ArtifactExecutionProbe,
                                exec=None,
                                grpc=None,
                                http=Mock(ArtifactExecutionHTTPProbe, path=None, port=None, service_id="http"),
                                port=None,
                            ),
                            started=None,
                        ),
                        resources=[
                            Mock(
                                ArtifactExecutionResourceDependency,
                                resource_id="postgres-database",
                                config={"database_id": "testdatabase"},
                            )
                        ],
                        secrets=[Mock(ArtifactInjectedValue, alias=None, id="secret_a", type="password")],
                        services=[Mock(ArtifactExecutionService, grpc=None, http=Mock(port=80), id="http", tcp=None)],
                        volumes=[volume_a],
                    ),
                    id="api",
                    provided_resources=[],
                    type=docker_image_artifact_type_dependency,
                )
            ]
            return Mock(
                Bolt,
                artifacts=artifacts,
                buildable_artifacts=[],
                executable_artifacts=artifacts,
                project_id="simple",
                version="1",
            )
        case "typical":
            # A typical project with two artifacts using various dependencies
            # Name cannot be mocked via the constructor.
            volume_a = Mock(
                ArtifactExecutionVolume, capacity=0.01, id="volume_a", path="/var/volume_a", persistent=True
            )
            volume_a.name = "Volume A"
            volume_b = Mock(
                ArtifactExecutionVolume, capacity=0.25, id="volume_b", path="/var/volume_b", persistent=False
            )
            volume_b.name = "Volume B"

            artifacts = [
                Mock(
                    Artifact,
                    build=None,
                    execution=Mock(
                        ArtifactExecutionRequirements,
                        configs=[Mock(ArtifactInjectedValue, alias=None, id="option_a", type="string")],
                        healthchecks=Mock(
                            ArtifactExecutionHealthChecks,
                            alive=None,
                            ready=None,
                            started=None,
                        ),
                        resources=[],
                        secrets=[Mock(ArtifactInjectedValue, alias=None, id="secret_a", type="password")],
                        services=[],
                        volumes=[volume_a, volume_b],
                    ),
                    id="api",
                    provided_resources=[],
                    type=docker_image_artifact_type_dependency,
                ),
                Mock(Artifact, build=None, execution=None, id="frontend", type=docker_image_artifact_type_dependency),
            ]
            return Mock(
                Bolt,
                artifacts=artifacts,
                buildable_artifacts=[],
                executable_artifacts=[artifacts[0]],
                project_id="typical",
                version="1",
            )
        case "resource_provider":
            # A project with artifacts that provide resources
            class ResourceRequirements(BaseModel):
                prefix: str | None = None
                """Key prefix."""
                database_id: str
                """ID of database."""

            resource1 = Mock(
                Resource,
                configs=[
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Host of Database server.",
                        id="host",
                        shared=True,
                        template="",
                        type=ArtifactSettingType.STRING,
                    ),
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Port Database server listens on.",
                        id="port",
                        shared=True,
                        template="",
                        type=ArtifactSettingType.INTEGER,
                    ),
                ],
                dependency_id_fields=["database_id"],
                description="Resource Description",
                id="resource_provider-resource1",
                prefix="RESOURCE",
                requirements=ResourceRequirements,
                secrets=[
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Name of database",
                        id="database",
                        shared=False,
                        template="",
                        type=ArtifactSettingType.STRING,
                    ),
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Login username to access database",
                        id="username",
                        shared=False,
                        template="",
                        type=ArtifactSettingType.STRING,
                    ),
                    Mock(
                        ResourceDependencyInjectedValue,
                        description="Login password to access database",
                        id="password",
                        shared=False,
                        template=None,
                        type=ArtifactSettingType.PASSWORD,
                    ),
                ],
            )
            resource1.name = "Resource Provider Resource"
            resource1.configs[0].name = "Host"
            resource1.configs[1].name = "Port"
            resource1.secrets[0].name = "Database"
            resource1.secrets[1].name = "Username"
            resource1.secrets[2].name = "Password"

            resource2 = Mock(Resource, id="service-resource2")
            artifact = Mock(
                Artifact,
                build=None,
                execution=Mock(
                    ArtifactExecutionRequirements,
                    configs=[],
                    healthchecks=Mock(ArtifactExecutionHealthChecks, alive=None, ready=None, started=None),
                    resources=[],
                    secrets=[],
                    services=[],
                    volumes=[],
                ),
                id="server",
                provided_resources=[resource1],
                type=docker_image_artifact_type_dependency,
            )

            return Mock(
                Bolt,
                artifacts=[artifact],
                buildable_artifacts=[],
                executable_artifacts=[artifact],
                project_id="resource_provider",
                version="1",
            )


@pytest.fixture(scope="session")
def environment() -> Environment:
    return Environment(id="test", name="Test Environment", tier=EnvironmentTier.DEVELOPMENT)


@pytest.fixture(scope="session")
def execution_parameters() -> ExecutionParameters:
    return ExecutionParameters(
        DefaultExecutionParameters(
            compute=ArtifactExecutionComputeParameters(max_memory=1.0, min_cpu=0.25, min_memory=0.1),
            external_service=ArtifactExecutionExternalServiceParameters(host="test.ballista.build"),
            volume=ArtifactExecutionVolumeParameters(max_capacity=1.0, path="/custom/path", type="generic-storage"),
        )
    )
