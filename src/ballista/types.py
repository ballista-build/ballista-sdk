from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Any, Protocol


class ArtifactSettingType(StrEnum):
    BOOLEAN = auto()
    """A boolean."""
    INTEGER = auto()
    """32-bit integer."""
    FLOAT = auto()
    """64-bit float."""
    PASSWORD = auto()
    """String but specifically a password."""
    STRING = auto()
    """String."""


class ArtifactInjectedValue(Protocol):
    """Setting injected back to dependents."""

    @property
    def alias(self) -> str | None:
        """Alias to use to inject value instead of automatically generating it."""
        ...

    @property
    def description(self) -> str:
        """Description of setting."""
        ...

    @property
    def id(self) -> str:
        """Identifier."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of ResourceDependencyInjectedSetting."""
        ...

    @property
    def template(self) -> str | None:
        """Value template injected."""
        ...

    @property
    def type(self) -> ArtifactSettingType:
        """Type of value."""
        ...


class ResourceDependencyRequirements(Protocol):
    """Values required for a Resource dependency."""

    @property
    def prefix(self) -> str | None:
        """Key prefix for returned dependency setting values."""
        ...


class ResourceDependencyInjectedValue(ArtifactInjectedValue, Protocol):
    """Setting injected back to dependents."""

    @property
    def shared(self) -> bool:
        """Indicates setting is shared across multiple projects."""
        ...


class Resource(Protocol):
    """A platform Resource."""

    @property
    def configs(self) -> Collection[ResourceDependencyInjectedValue]:
        """Configs given to dependents."""
        ...

    @property
    def description(self) -> str:
        """Description."""
        ...

    @property
    def id(self) -> str:
        """Identifier."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of Resource."""
        ...

    @property
    def prefix(self) -> str:
        """Default prefix."""
        ...

    @property
    def requirements(self) -> ResourceDependencyRequirements:
        """Requirements for a dependency."""
        ...

    @property
    def secrets(self) -> Collection[ResourceDependencyInjectedValue]:
        """Secrets given to dependents."""
        ...


class Project(Protocol):
    @property
    def id(self) -> str:
        """Unique identifier of project, across all environments."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of project."""
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


class ArtifactBuildRequirements(Protocol):
    """Artifact requirements for building an artifact."""

    @property
    def dockerfile(self) -> str | None:
        """Name of local Dockerfile used to build artifact."""
        ...

    @property
    def dockerfile_target(self) -> str:
        """Dockerfile target used when building artifact."""
        ...


class ArtifactExecutionResourceDependency(Protocol):
    """An execution dependency for a specific Resource."""

    @property
    def config(self) -> dict:
        """Dependency data."""
        ...

    @property
    def resource_id(self) -> str:
        """Unique identifer to Resource."""
        ...


class ArtifactExecutionExecProbe(Protocol):
    """Probe that executes a collection of commands. A return code of 0 indicates a successful probe. A return code of anything else indicates a failure."""

    @property
    def commands(self) -> Collection[str]:
        """List of commands to run."""
        ...

    @property
    def shell(self) -> bool:
        """Indicates if commands are ran in a shell."""
        ...


class BaseArtifactExecutionPortProbe(Protocol):
    @property
    def port(self) -> int | None: ...

    @property
    def service_id(self) -> str | None: ...


class ArtifactExecutionGRPCProbe(BaseArtifactExecutionPortProbe, Protocol):
    """Probe that executes a GRPC Health Checking Protocol request."""

    pass


class ArtifactExecutionHTTPProbe(BaseArtifactExecutionPortProbe, Protocol):
    """Probe that executes an HTTP GET request to the path "/healthz". A status of 200 indicates a successful probe. Any other status indicates a failure."""

    @property
    def path(self) -> str | None:
        """A specific HTTP path for the probe request."""
        ...


class ArtifactExecutionTCPProbe(BaseArtifactExecutionPortProbe, Protocol):
    """Probe that executes a TCP socket connection. A connection indicates a successful probe. Inability to connect indicates a failure."""

    pass


class ArtifactExecutionProbe(Protocol):
    """Probe that makes a check against an executing artifact."""

    @property
    def exec(self) -> ArtifactExecutionExecProbe | None: ...

    @property
    def grpc(self) -> ArtifactExecutionGRPCProbe | None: ...

    @property
    def http(self) -> ArtifactExecutionHTTPProbe | None: ...

    @property
    def tcp(self) -> ArtifactExecutionTCPProbe | None: ...


class ArtifactExecutionHealthChecks(Protocol):
    @property
    def alive(self) -> ArtifactExecutionProbe | None: ...

    @property
    def ready(self) -> ArtifactExecutionProbe | None: ...

    @property
    def started(self) -> ArtifactExecutionProbe | None: ...


class BaseArtifactExecutionPortService(Protocol):
    @property
    def port(self) -> int:
        """Port number service is listening."""
        ...


class ArtifactExecutionGRPCService(BaseArtifactExecutionPortService, Protocol):
    """A GRPC service, running on a specified port."""

    pass


class ArtifactExecutionHTTPService(BaseArtifactExecutionPortService, Protocol):
    """A HTTP service, running on a specified port."""

    pass


class ArtifactExecutionTCPService(BaseArtifactExecutionPortService, Protocol):
    """A TCP-based service, running on a specified port."""

    pass


class ArtifactExecutionService(Protocol):
    """Networked communication on a specific port."""

    @property
    def grpc(self) -> ArtifactExecutionGRPCService | None:
        """GRPC service."""
        ...

    @property
    def http(self) -> ArtifactExecutionHTTPService | None:
        """HTTP service."""
        ...

    @property
    def id(self) -> str: ...

    @property
    def tcp(self) -> ArtifactExecutionTCPService | None:
        """TCP service."""
        ...


class ArtifactExecutionVolume(Protocol):
    """Volume with mounted path exposed as an Environment Variable."""

    @property
    def capacity(self) -> float:
        """Minimum storage capacity required, measured in Gigabytes."""
        ...

    @property
    def id(self) -> str:
        """Unique identifier of volume."""
        ...

    @property
    def name(self) -> str:
        """Human-readable name of volume."""
        ...

    @property
    def path(self) -> str:
        """Path to mount volume."""
        ...

    @property
    def persistent(self) -> bool:
        """Flag indicating volume persists."""
        ...


class ArtifactExecutionRequirements(Protocol):
    """Artifact's declared requirements for execution."""

    @property
    def configs(self) -> Collection[ArtifactInjectedValue]:
        """Collection of non-sensitive settings optional for artifact execution."""
        ...

    @property
    def healthchecks(self) -> ArtifactExecutionHealthChecks:
        """Healthchecks to ensure correct execution."""
        ...

    @property
    def resources(self) -> Collection[ArtifactExecutionResourceDependency]:
        """Collection of resource dependencies required for artifact execution."""
        ...

    @property
    def secrets(self) -> Collection[ArtifactInjectedValue]:
        """Collection of sensitive settings required for artifact execution."""
        ...

    @property
    def services(self) -> Collection[ArtifactExecutionService]:
        """Collection of services required for execution to process."""
        ...

    @property
    def volumes(self) -> Collection[ArtifactExecutionVolume]:
        """Collection of volumes required for artifact execution."""
        ...


class Artifact(Protocol):
    """Artifact uniquely identified by `id` fields."""

    @property
    def build(self) -> ArtifactBuildRequirements | None:
        """Requirements to build artifact."""
        ...

    @property
    def execution(self) -> ArtifactExecutionRequirements | None:
        """Requirements to execute artifact."""
        ...

    @property
    def id(self) -> str:
        """Unique identifier of artifact."""
        ...

    @property
    def resource(self) -> Resource | None:
        """Resource provided by artifact."""
        ...

    @property
    def type(self) -> ArtifactTypeDependency:
        """Type of artifact."""
        ...


#
# Building
#


class BuildableArtifact(Artifact, Protocol):
    """An artifact that can be built."""

    @property
    def build(self) -> ArtifactBuildRequirements:
        """Requirements to build artifact."""
        ...


#
# Execution
#


class ExecutableArtifact(Artifact, Protocol):
    """An artifact that can be executed in an environment."""

    @property
    def execution(self) -> ArtifactExecutionRequirements:
        """Requirements to execute artifact."""
        ...


@dataclass(frozen=True)
class Environment:
    """An environment that can execute ExecutableArtifacts."""

    id: str
    """Unique identifier of environment."""

    name: str
    """Human-readable name of environment."""

    config: dict | None = None
    """Configuration for environment, adapter specific."""


class EnvironmentArtifactExecutionResourceParameters(Protocol):
    """High-level execution resource requirements."""

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


class EnvironmentArtifactExecutionScalingParameters(Protocol):
    @property
    def max_replicas(self) -> int | None:
        """Maximum number of replicas."""
        ...

    @property
    def min_replicas(self) -> int | None:
        """Minimum number of replicas."""
        ...


class EnvironmentArtifactExecutionServiceParameters(Protocol):
    """Parameters for an ArtifactExecutionService in an Environment."""

    @property
    def host(self) -> str:
        """External host."""
        ...

    @property
    def path(self) -> str | None:
        """External path."""
        ...

    @property
    def port(self) -> int:
        """External port"""
        ...


class EnvironmentArtifactExecutionVolume(Protocol):
    @property
    def max_capacity(self) -> float | None:
        """Maximum storage capacity, measures in Gigabytes."""
        ...

    @property
    def path(self) -> str | None:
        """Path inside volume to use as mount root."""
        ...

    @property
    def type(self) -> str | None:
        """Specific type of volume to use."""
        ...


class EnvironmentArtifactExecutionParameters(Protocol):
    """Parameters for executing artifacts in an environment."""

    # TODO: Service ports!!

    @property
    def resources(self) -> EnvironmentArtifactExecutionResourceParameters:
        """Compute resources."""
        ...

    @property
    def scaling(self) -> EnvironmentArtifactExecutionScalingParameters:
        """Scaling parameters."""
        ...

    @property
    def services(self) -> Mapping[str, EnvironmentArtifactExecutionServiceParameters]:
        """Service parameters."""
        ...

    @property
    def volumes(self) -> Mapping[str, EnvironmentArtifactExecutionVolume]:
        """Volume parameters"""
        ...


class EnvironmentProjectExecutionParameters(Protocol):
    @property
    def artifacts(self) -> Mapping[str, EnvironmentArtifactExecutionParameters]:
        """Mapping of artifact IDs to individual EnvironmentArtifactExecutionParameters."""
        ...


# TODO: These should be something better than tuples
ArtifactReference = tuple[Artifact, str, str]
"""Reference to a version of an Artifact in a project. artifact,version,project_id"""


ExecutableArtifactReference = tuple[ExecutableArtifact, str, str]
"""Reference to a version of an ExecutableArtifact in a project."""


ResourceWithArtifactProvider = tuple[Resource, ArtifactReference]
"""A Resource paired with the Artifact providing it."""


class Bolt(Protocol):
    """Multiple artifacts bundled together with a version and organized under a project."""

    @property
    def artifacts(self) -> Sequence[Artifact]:
        """Collection of artifacts included in Bolt."""
        ...

    @property
    def buildable_artifacts(self) -> Sequence[BuildableArtifact]:
        """Collection of BuildableArtifacts from the Bolt artifact collection."""
        ...

    @property
    def executable_artifacts(self) -> Sequence[ExecutableArtifact]:
        """Collection of ExecutableArtifacts from the Bolt artifact collection."""
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
# Settings
#


class BaseSetting(Protocol):
    @property
    def alias(self) -> str: ...

    @property
    def id(self) -> str: ...

    @property
    def type(self) -> ArtifactSettingType: ...


class ServiceConfig(BaseSetting, Protocol):
    pass


class ServiceSecret(BaseSetting, Protocol):
    pass


class SharedConfig(BaseSetting, Protocol):
    pass


class SharedSecret(BaseSetting, Protocol):
    pass


class BoltService(Protocol):
    def create_bolt(self, project_id: str) -> Bolt:
        """Create a new project with an empty Bolt."""
        ...

    def get_bolt(self, bolt_data: dict[str, Any]) -> Bolt:
        """Get a validated Bolt from bolt_data."""
        ...
