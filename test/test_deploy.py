import pytest
from pydantic import BaseModel

from ballista.adapters.docker_compose import DockerComposeExecutionEnvironmentAdapter


class PydanticExecutionEnvironment(BaseModel):
    hostname: str
    id: str
    name: str


class PydanticBallistaArtifactType(BaseModel):
    id: str
    name: str


class PydanticBallistaProject(BaseModel):
    id: str
    name: str


class PydanticBallistaArtifact(BaseModel):
    dockerfile: str | None = None
    dockerfile_stage: str | None = None
    id: str
    project: PydanticBallistaProject
    type: PydanticBallistaArtifactType


class PydanticBallistaBolt(BaseModel):
    artifacts: list[PydanticBallistaArtifact]
    project: PydanticBallistaProject
    version: str

    def to_dict(self) -> dict:
        return self.model_dump()


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
    return PydanticBallistaArtifactType(id="docker_image", name="Docker Image")


@pytest.fixture
def project(docker_image_artifact_type: PydanticBallistaArtifactType) -> PydanticBallistaProject:
    return PydanticBallistaProject(id="test", name="Test Project")


@pytest.fixture
def executable_artifact(
    docker_image_artifact_type: PydanticBallistaArtifactType, project: PydanticBallistaProject
) -> PydanticBallistaArtifact:
    return PydanticBallistaExecutableArtifact(
        id="test",
        type=docker_image_artifact_type,
        execution=PydanticBallistaArtifactExecution(),
        project=project,
    )


@pytest.fixture
def bolt(project: PydanticBallistaProject, executable_artifact: PydanticBallistaArtifact) -> PydanticBallistaBolt:
    return PydanticBallistaBolt(artifacts=[executable_artifact], project=project, version="1")


def test_deployment(bolt: PydanticBallistaBolt):
    adapter = DockerComposeExecutionEnvironmentAdapter()
    environment = PydanticExecutionEnvironment(hostname="localhost", id="local", name="local")

    adapter.deploy(bolt=bolt, environment=environment, artifacts=[bolt.artifacts[0]])
