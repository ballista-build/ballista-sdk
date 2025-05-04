from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from semver import Version


class Project(Protocol):
    id: str
    """Unique identifer of project, across all environments."""
    name: str
    """Human-readable name of project."""


class ArtifactLocalResourceNeeds(Protocol):
    """High-level execution resource requirements. Pretty sure all computers have these in some fashion."""

    max_cpu: float | int | None
    """Maximum CPU allowed, measured in cores."""
    max_memory: float | None
    """Maximum memory allowed, measured in Gibibytes."""
    min_cpu: float | int | None
    """Minimum CPU required, measured in cores."""
    min_memory: float | None
    """Minimum memory required, measured in Gibibytes."""


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


class ArtifactExecution(Protocol):
    @property
    def local_resources(self) -> ArtifactLocalResourceNeeds | None:
        """Local, machine-level resources for execution."""
        ...

    @property
    def platform_resources(self) -> Sequence[Mapping[str, Any]] | None:
        """Platform Resource dependencies required for execution."""
        ...


class Artifact(Protocol):
    dockerfile: str | None
    """Name of local Dockerfile used to build artifact."""
    dockerfile_stage: str | None
    """Dockerfile target used when building artifact."""

    @property
    def execution(self) -> ArtifactExecution | None: ...

    id: str
    """Identifier of artifact, unique to project scope."""

    @property
    def type(self) -> ArtifactType:
        """Type of artifact."""
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
    def executable_artifacts(self) -> Sequence[ExecutableArtifact]:
        """Sequence of ExecutableArtifacts only."""
        ...

    @property
    def project(self) -> Project:
        """Project bolt is associated with."""
        ...

    version: Version
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
