from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class Project(Protocol):
    @property
    def id(self) -> str:
        """Unique identifer of project, across all environments."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of project."""
        ...


class ArtifactExecutionLocalResourceNeeds(Protocol):
    """High-level execution resource requirements. Pretty sure all computers have these in some fashion."""

    @property
    def max_cpu(self) -> float | None:
        """Maximum CPU allowed, measured in cores."""
        ...

    @property
    def max_memory(self) -> float | None:
        """Maximum memory allowed, measured in Gibibytes."""
        ...

    @property
    def min_cpu(self) -> float | None:
        """Minimum CPU required, measured in cores."""
        ...

    @property
    def min_memory(self) -> float | None:
        """Minimum memory required, measured in Gibibytes."""
        ...


class PlatformResource(Protocol):
    id: str
    name: str


class PlatformResourceDependency(Protocol):
    """An execution dependency for a specific Platform Resource."""

    id: str
    """Reference to Platform Resource."""


class ArtifactType(Protocol):
    config: dict
    """Configuration structure of type."""
    id: str
    """Identifier of type, unique to environment scope."""
    name: str
    """Human-readable name of type."""


class DockerImageArtifactConfiguration(Protocol):
    @property
    def name(self) -> str | None:
        """Docker image name to use."""
        ...


class ArtifactTypeDependency(Protocol):
    @property
    def id(self) -> str:
        """Identifier of ArtifactType."""
        ...

    @property
    def config(self) -> dict:
        """Dependency data."""
        ...


class ArtifactExecution(Protocol):
    @property
    def local_resources(self) -> ArtifactExecutionLocalResourceNeeds | None:
        """Local, machine-level resources for execution."""
        ...

    @property
    def platform_resources(self) -> Sequence[Mapping[str, Any]] | None:
        """Platform Resource dependencies required for execution."""
        ...


class Artifact(Protocol):
    """Artifact uniquely identified by `id` and `version` fields."""

    @property
    def dockerfile(self) -> str | None:
        """Name of local Dockerfile used to build artifact."""
        ...

    @property
    def dockerfile_stage(self) -> str | None:
        """Dockerfile target used when building artifact."""
        ...

    @property
    def execution(self) -> ArtifactExecution | None:
        """Execution parameters."""
        ...

    @property
    def id(self) -> str:
        """Identifier of artifact."""
        ...

    @property
    def type(self) -> ArtifactTypeDependency:
        """Type of artifact."""
        ...


class BuildableArtifact(Artifact, Protocol):
    """An artifact that can be built."""

    @property
    def dockerfile_stage(self) -> str:
        """Dockerfile target used when building artifact."""
        ...


class ExecutableArtifact(Artifact, Protocol):
    """An artifact that can be executed."""

    @property
    def execution(self) -> ArtifactExecution: ...


class Bolt(Protocol):
    """Multiple artifacts bundled together with a version and organized under a project."""

    @property
    def artifacts(self) -> Sequence[Artifact]:
        """Sequence of all Artifacts included in Bolt."""
        ...

    @property
    def project_id(self) -> str:
        """Unique identifier of project the Bolt is associated with."""
        ...

    @property
    def version(self) -> str:
        """Version of entire bundle of artifacts."""
        ...

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
