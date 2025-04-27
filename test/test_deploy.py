import pytest
from pydantic import BaseModel

from ballista.adapters.docker_compose import DockerComposeExecutionEnvironmentAdapter
from ballista.adapters.kubernetes import KubernetesExecutionEnvironmentAdapter


class PydanticExecutionEnvironment(BaseModel):
    hostname: str
    id: str
    name: str


class PydanticArtifactType(BaseModel):
    id: str
    name: str


class PydanticProject(BaseModel):
    id: str
    name: str


class PydanticArtifact(BaseModel):
    dockerfile: str | None = None
    dockerfile_stage: str | None = None
    id: str
    project: PydanticProject
    type: PydanticArtifactType


class PydanticBolt(BaseModel):
    artifacts: list[PydanticArtifact]
    project: PydanticProject
    version: str

    def to_dict(self) -> dict:
        return self.model_dump()


class PydanticArtifactLocalResourceNeeds(BaseModel):
    """High-level execution resource requirements. Pretty sure all computers have these in some fashion."""

    max_cpu_cores: float | int | None = None
    max_memory_mb: int | None = None
    min_cpu_cores: float | int | None = None
    min_memory_mb: int | None = None


class PydanticArtifactExecution(BaseModel):
    local_resources: PydanticArtifactLocalResourceNeeds | None = None
    platform_resources: None = None


class PydanticExecutableArtifact(PydanticArtifact):
    execution: PydanticArtifactExecution


@pytest.fixture
def docker_image_artifact_type() -> PydanticArtifactType:
    return PydanticArtifactType(id="docker_image", name="Docker Image")


@pytest.fixture
def project(docker_image_artifact_type: PydanticArtifactType) -> PydanticProject:
    return PydanticProject(id="test", name="Test Project")


@pytest.fixture
def executable_artifact(docker_image_artifact_type: PydanticArtifactType, project: PydanticProject) -> PydanticArtifact:
    return PydanticExecutableArtifact(
        id="test",
        type=docker_image_artifact_type,
        execution=PydanticArtifactExecution(
            local_resources=PydanticArtifactLocalResourceNeeds(max_cpu_cores=1.5, min_memory_mb=1024)
        ),
        project=project,
    )


@pytest.fixture
def bolt(project: PydanticProject, executable_artifact: PydanticExecutableArtifact) -> PydanticBolt:
    return PydanticBolt(artifacts=[executable_artifact], project=project, version="1.0.0")


def test_deployment(bolt: PydanticBolt, executable_artifact: PydanticExecutableArtifact):
    # adapter = DockerComposeExecutionEnvironmentAdapter()
    adapter = KubernetesExecutionEnvironmentAdapter()
    environment = PydanticExecutionEnvironment(hostname="localhost", id="local", name="local")

    adapter.deploy(bolt=bolt, environment=environment, artifacts=[executable_artifact])
