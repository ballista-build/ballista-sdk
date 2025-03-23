import pytest
from pydantic import BaseModel, Field

from ballista.adapters.docker_compose import DockerComposeExecutionEnvironmentAdapter
from ballista.adapters.types import ExecutionEnvironment, ExecutionEnvironmentAdapter
from ballista.types import BallistaArtifact, BallistaExecutableArtifact


class PydanticBallistaArtifact(BaseModel):
    dockerfile: str | None = None
    dockerfile_stage: str | None = None
    name: str
    type: dict[str, dict]


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
    environment = ExecutionEnvironment(adapter=adapter, cluster="local", name="local", namespace="local")

    artifact = PydanticBallistaExecutableArtifact(
        name="test", type={"docker_image": {}}, execution=PydanticBallistaArtifactExecution()
    )

    adapter.deploy_artifact(environment=environment, artifact=artifact)
