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
    project: BallistaProject
    type: BallistaArtifactType


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


def test_deployment():
    adapter = DockerComposeExecutionEnvironmentAdapter()
    docker_artifact_type = PydanticBallistaArtifactType(name="docker_image", title="Docker Image")
    environment = ExecutionEnvironment(adapter=adapter, hostname="localhost", name="local", title="local")
    project = PydanticBallistaProject(name="test", title="Test Project")

    artifact = PydanticBallistaExecutableArtifact(
        name="test", type=docker_artifact_type, execution=PydanticBallistaArtifactExecution(), project=project
    )

    adapter.deploy_artifact(environment=environment, artifact=artifact)
