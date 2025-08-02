from unittest.mock import Mock

import pytest

from ballista.types import (
    Artifact,
    ArtifactExecutionHealthChecks,
    ArtifactExecutionHTTPProbe,
    ArtifactExecutionProbe,
    ArtifactExecutionRequirements,
    ArtifactExecutionResourceDependency,
    ArtifactExecutionService,
    ArtifactExecutionVolume,
    ArtifactInjectedValue,
    ArtifactTypeDependency,
    Bolt,
    Environment,
    EnvironmentArtifactExecutionParameters,
    EnvironmentArtifactExecutionResources,
    EnvironmentArtifactExecutionScaling,
    EnvironmentArtifactExecutionVolume,
    Project,
)


@pytest.fixture(scope="session")
def project():
    return Mock(Project, id="typical", name="Typical Project")


@pytest.fixture(scope="session")
def docker_image_artifact_type_dependency():
    return Mock(ArtifactTypeDependency, config={"image": "hello-world:latest"}, id="docker_image")


@pytest.fixture(scope="session", params=["empty", "simple", "typical"])
def bolt(project: Project, docker_image_artifact_type_dependency: ArtifactTypeDependency, request):
    match request.param:
        case "empty":
            # An empty project, having no artifacts. Invalid.
            return Mock(Bolt, artifacts=[], project_id=project.id, version="1")
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
                                resource_id="postgres",
                                config={"database_id": "testdatabase"},
                            )
                        ],
                        secrets=[Mock(ArtifactInjectedValue, alias=None, id="secret_a", type="password")],
                        services=[Mock(ArtifactExecutionService, id="http", port=80)],
                        volumes=[volume_a],
                    ),
                    id="api",
                    type=docker_image_artifact_type_dependency,
                )
            ]
            return Mock(
                Bolt,
                artifacts=artifacts,
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
                    type=docker_image_artifact_type_dependency,
                ),
                Mock(Artifact, build=None, execution=None, id="frontend", type=docker_image_artifact_type_dependency),
            ]
            return Mock(
                Bolt,
                artifacts=artifacts,
                project_id="typical",
                version="1",
            )
        case "complex":
            # A complex project with multiple artifacts and complicated dependencies
            pass


@pytest.fixture(scope="session")
def environment():
    return Mock(Environment, hostname="localhost", id="test", name="Test Environment")


@pytest.fixture(scope="session")
def environment_artifact_execution_parameters():
    return Mock(
        EnvironmentArtifactExecutionParameters,
        resources=Mock(
            EnvironmentArtifactExecutionResources, max_cpu=None, max_memory=1.0, min_cpu=0.25, min_memory=0.1
        ),
        scaling=Mock(EnvironmentArtifactExecutionScaling),
        volumes={
            "volume_a": Mock(
                EnvironmentArtifactExecutionVolume,
                max_capacity=1.0,
                path="/custom/path",
                type="generic-storage",
            ),
            "volume_b": Mock(
                EnvironmentArtifactExecutionVolume,
                max_capacity=None,
                path="/custom/path",
                type="generic-storage",
            ),
        },
    )
