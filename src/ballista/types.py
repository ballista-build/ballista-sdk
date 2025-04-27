from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class Project(Protocol):
    id: str
    """Unique identifer of project, across all environments."""
    name: str
    """Human-readable name of project."""


class ArtifactLocalResourceNeeds(Protocol):
    """High-level execution resource requirements. Pretty sure all computers have these in some fashion."""

    max_cpu_cores: float | int | None
    max_memory_mb: int | None
    min_cpu_cores: float | int | None
    min_memory_mb: int | None


class PlatformResource(Protocol):
    id: str
    name: str


class PlatformResourceDependency(Protocol):
    """An execution dependency for a specific Platform Resource."""

    id: str
    """Reference to Platform Resource."""


class ArtifactType(Protocol):
    id: str
    """Identifier of type, unique to environment scope."""
    name: str
    """Human-readable name of type."""


class Artifact(Protocol):
    dockerfile: str | None
    """Name of local Dockerfile used to build artifact."""
    dockerfile_stage: str | None
    """Dockerfile target used when building artifact."""

    id: str
    """Identifier of artifact, unique to project scope."""

    @property
    def project(self) -> Project:
        """Project artifact exists."""
        ...

    @property
    def type(self) -> ArtifactType:
        """Type of artifact."""
        ...


class ArtifactExecution(Protocol):
    @property
    def local_resources(self) -> ArtifactLocalResourceNeeds | None:
        """Local, machine-level resources for execution."""
        ...

    @property
    def platform_resources(self) -> Sequence[Mapping[str, Any]] | None:
        """Platform Resource dependencies required for execution."""
        ...


class ExecutableArtifact(Artifact, Protocol):
    """An artifact that can be executed."""

    @property
    def execution(self) -> ArtifactExecution: ...


class Bolt(Protocol):
    """Multiple artifacts bundled together with a version and organized under a project."""

    @property
    def artifacts(self) -> Sequence[Artifact]: ...

    @property
    def project(self) -> Project:
        """Project bolt is associated with."""
        ...

    version: str
    """Semantic version of entire bundle of artifacts."""

    def to_dict(self) -> dict[str, Any]:
        """Get Bolt data in dictionary form."""
        ...


class BoltService(Protocol):
    def create_bolt(self, project_id: str) -> Bolt:
        """Create a new project with an empty Bolt."""
        ...

    def get_bolt(self, bolt_data: dict[str, Any]) -> Bolt:
        """Get a validated Bolt from bolt_data."""
        ...
