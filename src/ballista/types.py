from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class BallistaArtifactLocalResourceNeeds(Protocol):
    """High-level execution resource requirements. Pretty sure all computers have these in some fashion."""

    max_cpu_cores: float | int | None
    max_memory_mb: int | None
    min_cpu_cores: float | int | None
    min_memory_mb: int | None


class BallistaPlatformResource(Protocol):
    key: str
    name: str


class BallistaPlatformResourceDependency(Protocol):
    """An execution dependency for a specific Platform Resource."""

    key: str
    """Reference key to Platform Resource."""


class BallistaArtifactType(Protocol):
    name: str
    key: str


class BallistaArtifact(Protocol):
    dockerfile: str | None
    """Name of local Dockerfile used to build artifact."""
    dockerfile_stage: str | None
    """Dockerfile target used when building artifact."""

    name: str
    type: dict[str, Any]


class BallistaArtifactExecution(Protocol):
    @property
    def local_resources(self) -> BallistaArtifactLocalResourceNeeds | None:
        """Local, machine-level resources for execution."""
        ...

    @property
    def platform_resources(self) -> Sequence[Mapping[str, Any]] | None:
        """Platform Resource dependencies required for execution."""
        ...


class BallistaExecutableArtifact(BallistaArtifact, Protocol):
    """An artifact that can be executed."""

    @property
    def execution(self) -> BallistaArtifactExecution: ...


class BallistaProject(Protocol):
    key: str
    name: str


class BallistaBolt(Protocol):
    api_version: str

    @property
    def artifacts(self) -> Sequence[BallistaArtifact]: ...

    project: str
    version: str

    def to_dict(self) -> dict[str, Any]:
        """Get Bolt data in dictionary form."""
        ...


class BoltService(Protocol):
    def create_bolt(self, project: str) -> BallistaBolt:
        """Create a new project with an empty Bolt."""
        ...

    def get_bolt(self, bolt_data: dict[str, Any]) -> BallistaBolt:
        """Get a validated Bolt from bolt_data."""
        ...
