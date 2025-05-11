from unittest.mock import Mock

import pytest

from ballista.adapters.types import ExecutionEnvironment
from ballista.types import (
    Artifact,
    ArtifactExecution,
    ArtifactExecutionLocalResourceNeeds,
    ArtifactTypeDependency,
    Bolt,
    Project,
)


@pytest.fixture(scope="session")
def project():
    return Mock(Project, id="example", name="Example Project")


@pytest.fixture(scope="session")
def docker_image_artifact_type_dependency():
    return Mock(ArtifactTypeDependency, config={"name": "hello-world:latest"}, id="docker_image")


@pytest.fixture(scope="session", params=["empty", "simple"])
def bolt(project: Project, docker_image_artifact_type_dependency: ArtifactTypeDependency, request):
    if request.param == "empty":
        return Mock(Bolt, artifacts=[], project_id=project.id, version="1")

    elif request.param == "simple":
        artifacts = [
            Mock(
                Artifact,
                dockerfile=None,
                dockerfile_stage=None,
                id="api",
                execution=Mock(
                    ArtifactExecution,
                    local_resources=Mock(
                        ArtifactExecutionLocalResourceNeeds, max_cpu=None, max_memory=1.0, min_cpu=0.25, min_memory=0.1
                    ),
                ),
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
def execution_environment():
    return Mock(ExecutionEnvironment, hostname="localhost", id="test", name="Test Environment")
