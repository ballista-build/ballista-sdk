from collections.abc import Sequence
from typing import Any, Protocol


class Project(Protocol):
    @property
    def id(self) -> str:
        """Unique identifier of project, across all environments."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of project."""
        ...


class ArtifactBuildParameters(Protocol):
    """Parameters for building an artifact."""

    @property
    def dockerfile(self) -> str | None:
        """Name of local Dockerfile used to build artifact."""
        ...

    @property
    def dockerfile_target(self) -> str:
        """Dockerfile target used when building artifact."""
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
    @property
    def id(self) -> str:
        """Identifer."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of PlatformResource."""
        ...


class PlatformResourceDependency(Protocol):
    """An execution dependency for a specific Platform Resource."""

    @property
    def config(self) -> dict:
        """Dependency data."""
        ...

    @property
    def platform_resource_id(self) -> str:
        """Unique identifer to Platform Resource."""
        ...


class ArtifactType(Protocol):
    """Type of artifact."""

    @property
    def id(self) -> str:
        """Identifier for type, unique to environment scope."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of type."""
        ...


class DockerImageArtifactConfiguration(Protocol):
    @property
    def image(self) -> str | None:
        """Docker image name to use."""
        ...


class ArtifactTypeDependency(Protocol):
    @property
    def artifact_type_id(self) -> str:
        """Identifier of ArtifactType."""
        ...

    @property
    def config(self) -> dict[str, Any]:
        """Dependency data."""
        ...


class ArtifactExecutionParameters(Protocol):
    @property
    def local_resources(self) -> ArtifactExecutionLocalResourceNeeds | None:
        """Local, machine-level resources for execution."""
        ...

    # @property
    # def platform_resources(self) -> Sequence[PlatformResourceDependency]:
    #     """Platform Resource dependencies required for execution."""
    #     ...


class Artifact(Protocol):
    """Artifact uniquely identified by `id` and `version` fields."""

    @property
    def build(self) -> ArtifactBuildParameters | None:
        """Build parameters."""
        ...

    @property
    def execution(self) -> ArtifactExecutionParameters | None:
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


#
# Building
#


class BuildableArtifact(Artifact, Protocol):
    """An artifact that can be built."""

    @property
    def build(self) -> ArtifactBuildParameters:
        """Parameters to build artifact."""
        ...


#
# Execution
#


class ExecutableArtifact(Artifact, Protocol):
    """An artifact that can be executed."""

    @property
    def execution(self) -> ArtifactExecutionParameters:
        """Execution parameters."""
        ...


class ExecutionEnvironment(Protocol):
    """An environment that can execute artifacts."""

    @property
    def hostname(self) -> str:
        """Name of the environment host. Typically used for cluster name, server name, etc."""
        ...

    @property
    def id(self) -> str:
        """Unique identifier."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of environment."""
        ...


class BoltService(Protocol):
    def create_bolt(self, project_id: str) -> Bolt:
        """Create a new project with an empty Bolt."""
        ...

    def get_bolt(self, bolt_data: dict[str, Any]) -> Bolt:
        """Get a validated Bolt from bolt_data."""
        ...
