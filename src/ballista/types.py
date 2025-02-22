from typing import Protocol


class BallistaArtifactLocalResourceNeeds(Protocol):
    max_cpu_cores: float | None = None
    max_memory_mb: int | None = None
    min_cpu_cores: float | None = None
    min_memory_mb: int | None = None


class BallistaPlatformResource(Protocol):
    pass


class BallistaArtifactExecution(Protocol):
    local_resources: BallistaArtifactLocalResourceNeeds
    platform_resources: list[BallistaPlatformResource]


class BallistaArtifactType(Protocol):
    name: str
    key: str


class BallistaArtifact(Protocol):
    name: str
    type: BallistaArtifactType
    dockerfile: str | None = None
    dockerfile_stage: str | None = None
    execution: BallistaArtifactExecution | None = None


class BallistaProject(Protocol):
    key: str
    name: str


class BallistaBolt(Protocol):
    api_version: str
    artifacts: list[BallistaArtifact]
    project: str
    version: str
