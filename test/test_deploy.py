import models
import pytest

from ballista.adapters.kubernetes import KubernetesExecutionEnvironmentAdapter
from ballista.adapters.types import ExecutionEnvironment
from ballista.types import ArtifactType, Bolt, ExecutableArtifact, Project


@pytest.fixture
def executable_artifact(docker_image_artifact_type: ArtifactType, project: Project) -> ExecutableArtifact:
    return models.PydanticArtifact(
        id="test",
        type=docker_image_artifact_type,
        execution=models.PydanticArtifactExecution(
            local_resources=models.PydanticArtifactLocalResourceNeeds(max_cpu=1.5, min_memory=1)
        ),
        project=project,
    )


@pytest.mark.parametrize("bolt", ["simple"], indirect=["bolt"])
def test_deployment(bolt: Bolt, executable_artifact: ExecutableArtifact, execution_environment: ExecutionEnvironment):
    # adapter = DockerComposeExecutionEnvironmentAdapter()
    adapter = KubernetesExecutionEnvironmentAdapter()

    adapter.deploy(bolt=bolt, environment=execution_environment, artifacts=[executable_artifact])
