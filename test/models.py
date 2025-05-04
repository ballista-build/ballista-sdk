from pydantic import BaseModel


class PydanticArtifactType(BaseModel):
    id: str
    name: str


class PydanticProject(BaseModel):
    id: str
    name: str


class PydanticArtifactLocalResourceNeeds(BaseModel):
    """High-level execution resource requirements. Pretty sure all computers have these in some fashion."""

    max_cpu: float | None = None
    max_memory: float | None = None
    min_cpu: float | None = None
    min_memory: float | None = None


class PydanticArtifactExecution(BaseModel):
    local_resources: PydanticArtifactLocalResourceNeeds | None = None
    platform_resources: None = None


class PydanticArtifact(BaseModel):
    dockerfile: str | None = None
    dockerfile_stage: str | None = None
    execution: PydanticArtifactExecution | None = None
    id: str
    type: PydanticArtifactType


class PydanticBolt(BaseModel):
    artifacts: list[PydanticArtifact]
    project: PydanticProject
    version: str

    @property
    def executable_artifacts(self) -> list[PydanticArtifact]:
        return [a for a in self.artifacts if a.execution]

    def to_dict(self) -> dict:
        return self.model_dump()


class PydanticExecutionEnvironment(BaseModel):
    hostname: str
    """Name of the environment host. Typically used for cluster name, server name, etc."""
    id: str
    """Unique identifier."""
    name: str
