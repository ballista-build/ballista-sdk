from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class BallistaProject(Protocol):
    id: str
    name: str


class BallistaArtifactLocalResourceNeeds(Protocol):
    """High-level execution resource requirements. Pretty sure all computers have these in some fashion."""

    max_cpu_cores: float | int | None
    max_memory_mb: int | None
    min_cpu_cores: float | int | None
    min_memory_mb: int | None


class BallistaPlatformResource(Protocol):
    id: str
    name: str


class BallistaPlatformResourceDependency(Protocol):
    """An execution dependency for a specific Platform Resource."""

    id: str
    """Reference to Platform Resource."""


class BallistaArtifactType(Protocol):
    id: str
    """Name of type, unique to environment scope."""
    name: str
    """Human-readable name of type."""


class BallistaArtifact(Protocol):
    dockerfile: str | None
    """Name of local Dockerfile used to build artifact."""
    dockerfile_stage: str | None
    """Dockerfile target used when building artifact."""

    id: str
    """Identifier of artifact, unique to project scope."""

    @property
    def project(self) -> BallistaProject:
        """Project artifact exists."""
        ...

    @property
    def type(self) -> BallistaArtifactType:
        """Type of artifact."""
        ...


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


class BallistaBolt(Protocol):
    """Multiple artifacts bundled together with a version and organized under a project."""

    @property
    def artifacts(self) -> Sequence[BallistaArtifact]: ...

    @property
    def project(self) -> BallistaProject:
        """Project bolt is associated with."""
        ...

    version: str

    def to_dict(self) -> dict[str, Any]:
        """Get Bolt data in dictionary form."""
        ...


class BoltService(Protocol):
    def create_bolt(self, project_id: str) -> BallistaBolt:
        """Create a new project with an empty Bolt."""
        ...

    def get_bolt(self, bolt_data: dict[str, Any]) -> BallistaBolt:
        """Get a validated Bolt from bolt_data."""
        ...
