import models
import pytest
from semver import Version


@pytest.fixture(scope="session")
def project():
    return models.PydanticProject(id="example", name="Example Project")


@pytest.fixture(scope="session")
def docker_image_artifact_type():
    return models.PydanticArtifactType(id="docker_image", name="Docker Image")


@pytest.fixture(scope="session")
def bolt(project: models.PydanticProject, docker_image_artifact_type: models.PydanticArtifactType, request):
    return {
        "empty": models.PydanticBolt(artifacts=[], project=project, version=Version(1)),
        "simple": models.PydanticBolt(
            artifacts=[
                models.PydanticArtifact(
                    id="api",
                    execution=models.PydanticArtifactExecution(
                        local_resources=models.PydanticArtifactLocalResourceNeeds(
                            max_memory=1, min_cpu=0.25, min_memory=0.1
                        )
                    ),
                    type=docker_image_artifact_type,
                )
            ],
            project=project,
            version=Version(1),
        ),
    }[request.param]


@pytest.fixture(scope="session")
def execution_environment():
    return models.PydanticExecutionEnvironment(hostname="localhost", id="test", name="Test Environment")
