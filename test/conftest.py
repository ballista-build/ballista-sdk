from unittest.mock import Mock

import pytest

from ballista.types import (
    Artifact,
    ArtifactExecutionRequirements,
    ArtifactExecutionSetting,
    ArtifactExecutionVolume,
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
    return Mock(Project, id="simple", name="Simple Project")


@pytest.fixture(scope="session")
def docker_image_artifact_type_dependency():
    return Mock(ArtifactTypeDependency, config={"image": "hello-world:latest"}, id="docker_image")


@pytest.fixture(scope="session", params=["empty", "simple"])
def bolt(project: Project, docker_image_artifact_type_dependency: ArtifactTypeDependency, request):
    if request.param == "empty":
        return Mock(Bolt, artifacts=[], project_id=project.id, version="1")

    elif request.param == "simple":
        # Name cannot be mocked via the constructor.
        volume = Mock(
            ArtifactExecutionVolume,
            id="volume_a",
            path="/var/volume_a",
            persistent=True,
        )
        volume.name = "Volume A"

        artifacts = [
            Mock(
                Artifact,
                build=None,
                execution=Mock(
                    ArtifactExecutionRequirements,
                    configs=[Mock(ArtifactExecutionSetting, alias=None, id="option_a", type="string")],
                    secrets=[Mock(ArtifactExecutionSetting, alias=None, id="secret_a", type="password")],
                    volumes=[volume],
                ),
                id="api",
                type=docker_image_artifact_type_dependency,
            )
        ]
        return Mock(
            Bolt,
            artifacts=artifacts,
            project_id=project.id,
            version="1",
        )

    elif request.param == "platform_resource":
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
                min_storage=0.25,
                max_storage=1.0,
                path="/custom/path",
                type="generic-storage",
            )
        },
    )
