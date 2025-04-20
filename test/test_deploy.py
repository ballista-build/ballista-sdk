import pytest
from pydantic import BaseModel, Field

from ballista.adapters.docker_compose import DockerComposeExecutionEnvironmentAdapter
from ballista.adapters.types import ExecutionEnvironment, ExecutionEnvironmentAdapter
from ballista.types import BallistaArtifact, BallistaArtifactType, BallistaExecutableArtifact, BallistaProject


class PydanticBallistaArtifactType(BaseModel):
    name: str
    title: str


class PydanticBallistaProject(BaseModel):
    name: str
    title: str


class PydanticBallistaArtifact(BaseModel):
    dockerfile: str | None = None
    dockerfile_stage: str | None = None
    name: str
    project: PydanticBallistaProject
    type: PydanticBallistaArtifactType


class PydanticBallistaArtifactLocalResourceNeeds(BaseModel):
    """High-level execution resource requirements. Pretty sure all computers have these in some fashion."""

    max_cpu_cores: float | int | None
    max_memory_mb: int | None
    min_cpu_cores: float | int | None
    min_memory_mb: int | None


class PydanticBallistaArtifactExecution(BaseModel):
    local_resources: PydanticBallistaArtifactLocalResourceNeeds | None = None
    platform_resources: None = None


class PydanticBallistaExecutableArtifact(PydanticBallistaArtifact):
    execution: PydanticBallistaArtifactExecution


@pytest.fixture
def docker_image_artifact_type() -> PydanticBallistaArtifactType:
    return PydanticBallistaArtifactType(name="docker_image", title="Docker Image")


@pytest.fixture
def test_project(docker_image_artifact_type: PydanticBallistaArtifactType) -> PydanticBallistaProject:
    return PydanticBallistaProject(name="test", title="Test Project")


@pytest.fixture
def test_artifact(
    docker_image_artifact_type: PydanticBallistaArtifactType, test_project: PydanticBallistaProject
) -> PydanticBallistaArtifact:
    return PydanticBallistaExecutableArtifact(
        name="test",
        type=docker_image_artifact_type,
        execution=PydanticBallistaArtifactExecution(),
        project=test_project,
    )


def test_deployment(test_artifact: BallistaExecutableArtifact):
    adapter = DockerComposeExecutionEnvironmentAdapter()
    environment = ExecutionEnvironment(adapter=adapter, hostname="localhost", name="local", title="local")

    adapter.deploy_artifact(environment=environment, artifact=test_artifact)
