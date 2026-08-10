from enum import StrEnum, auto
from typing import Annotated

from pydantic import BaseModel, Field

from .artifacts import Artifact
from .bolts import Bolt
from .common import BaseNamedModel


class ExecutionStatus(StrEnum):
    """Statuses for Artifact execution.

    - "unknown": Artifact execution status is unknown.
    - "not_found": Artifact cannot be found.
    - "pending": Artifact execution is pending.
    - "executing": Artifact execution has started and is healthy.
    - "unhealthy": Artifact execution has started but is not healthy.
    - "succeeded": Artifact execution has ended in a healthy state.
    - "failed": Artifact execution has ended but in an unhealthy state."
    """

    UNKNOWN = auto()
    """Artifact execution status is unknown."""
    NOT_FOUND = auto()
    """Artifact cannot be found."""
    PENDING = auto()
    """Artifact execution is pending."""
    EXECUTING = auto()
    """Artifact execution has started and is healthy."""
    UNHEALTHY = auto()
    """Artifact execution has started but is not healthy."""
    SUCCEEDED = auto()
    """Artifact execution has ended in a healthy state."""
    FAILED = auto()
    """Artifact execution has ended but in an unhealthy state."""


class EnvironmentTier(StrEnum):
    DEVELOPMENT = auto()
    """Suitable for iteration and debugging."""

    STAGING = auto()
    """Suitable for verification and stability."""

    PRODUCTION = auto()
    """The one true environment."""


class Environment(BaseNamedModel):
    """An environment that can execute ExecutableArtifacts."""

    tier: EnvironmentTier
    """Tier of Environment."""

    config: dict | None = None
    """Configuration for environment, adapter specific."""


class ComputeExecutionParameters(BaseModel, frozen=True):
    """High-level execution compute bounds."""

    max_cpu: Annotated[float | None, Field(description="Maximum CPU allowed, measured in cores.", gt=0)] = None
    """Maximum CPU allowed, measured in cores."""
    max_gpu: float | None = None
    """Maximum GPU allowed, measured in cores."""
    max_memory: float | None = None
    """Maximum memory allowed, measured in Gibibytes."""
    min_cpu: Annotated[float | None, Field(description="Minimum CPU required, measured in cores.", gt=0)] = None
    """Minimum CPU required, measured in cores."""
    min_gpu: float | None = None
    """Minimum GPU required, measured in cores."""
    min_memory: float | None = None
    """Minimum memory required, measured in Gibibytes."""


class ExternalizedServiceParameters(BaseModel, frozen=True):
    """Parameters to externalize a ServiceRequirement, granting outside access."""

    host: str | None = None
    """External host."""

    port: int | None = None
    """External port."""

    path: str | None = None
    """External path."""

    secure: bool = False
    """Secure connection."""


class ScalingExecutionParameters(BaseModel, frozen=True):
    """Parameters to scale execution of an artifact."""

    max_replicas: int | None = None
    """Maximum number of replicas."""

    min_replicas: int | None = None
    """Minimum number of replicas."""


class VolumeExecutionParameters(BaseModel, frozen=True):
    """Parameters to execute a VolumeRequirement."""

    max_capacity: float | None = None
    """Maximum storage capacity, measured in Gigabytes."""

    path: str | None = None
    """Path inside volume to use as mount root."""

    type: str | None = None
    """Specific type of volume to use."""


class ArtifactExecutionParameters(BaseModel, frozen=True):
    """Parameters for executing a specific ExecutableArtifact."""

    compute: ComputeExecutionParameters = Field(default_factory=ComputeExecutionParameters)
    external_services: dict[str, ExternalizedServiceParameters] = {}
    scaling: ScalingExecutionParameters = Field(default_factory=ScalingExecutionParameters)
    volumes: dict[str, VolumeExecutionParameters] = {}


class DefaultExecutionParameters(BaseModel, frozen=True):
    """Default parameters for executing any ExecutableArtifact in an environment."""

    # TODO: Something for artifact types so they can be configured.
    # Example: Docker Images are all pulled from a specific registry (ECR, etc.)
    compute: ComputeExecutionParameters = Field(default_factory=ComputeExecutionParameters)
    external_service: ExternalizedServiceParameters = Field(default_factory=ExternalizedServiceParameters)
    scaling: ScalingExecutionParameters = Field(default_factory=ScalingExecutionParameters)
    volume: VolumeExecutionParameters = Field(default_factory=VolumeExecutionParameters)


class ExecutionParameters(BaseModel, frozen=True):
    """Parameters for executing ExecutableArtifacts across all environments and projects."""

    initial: DefaultExecutionParameters = Field(default_factory=DefaultExecutionParameters)
    environments: dict[str, DefaultExecutionParameters] = {}
    projects: dict[tuple[str, str], DefaultExecutionParameters] = {}
    artifacts: dict[tuple[str, str, str], DefaultExecutionParameters] = {}
    """environment,project,artifact"""
    external_services: dict[tuple[str, str, str, str], ExternalizedServiceParameters] = {}
    """environment,project,artifact,service"""
    volumes: dict[tuple[str, str, str, str], VolumeExecutionParameters] = {}
    """environment,project,artifact,volumne"""

    def params_for_artifact(
        self, environment: Environment, bolt: Bolt, artifact: Artifact
    ) -> ArtifactExecutionParameters:
        if not artifact.execution:
            return ArtifactExecutionParameters()

        defaults = self.defaults_for_artifact(environment, bolt, artifact)
        default_service = defaults.external_service.model_dump()
        default_volume = defaults.volume.model_dump()

        external_services = {
            s.name: ExternalizedServiceParameters(**default_service) for s in artifact.execution.provides.services
        }
        volumes = {v.name: VolumeExecutionParameters(**default_volume) for v in artifact.execution.requires.volumes}

        return ArtifactExecutionParameters(
            compute=defaults.compute,
            external_services=external_services,
            scaling=defaults.scaling,
            volumes=volumes,
        )

    def defaults_for_artifact(
        self, environment: Environment, bolt: Bolt, artifact: Artifact
    ) -> DefaultExecutionParameters:
        defaults = self.initial.model_dump()

        if environment_defaults := self.environments.get(environment.name):
            defaults.update(environment_defaults.model_dump())

        if project_defaults := self.projects.get((environment.name, bolt.project)):
            defaults.update(project_defaults.model_dump())

        if artifact_defaults := self.artifacts.get((environment.name, bolt.project, artifact.name)):
            defaults.update(artifact_defaults.model_dump())

        return DefaultExecutionParameters(
            compute=ComputeExecutionParameters(**defaults["compute"]),
            external_service=ExternalizedServiceParameters(**defaults["external_service"]),
            scaling=ScalingExecutionParameters(**defaults["scaling"]),
            volume=VolumeExecutionParameters(**defaults["volume"]),
        )

    def defaults_for_environment(self, environment: Environment) -> DefaultExecutionParameters:
        params = self.initial.model_dump()

        if environment_defaults := self.environments.get(environment.name):
            params.update(environment_defaults.model_dump())

        return DefaultExecutionParameters(**params)

    def defaults_for_project(self, environment: Environment, bolt: Bolt) -> DefaultExecutionParameters:
        defaults = self.initial.model_dump()

        if environment_defaults := self.environments.get(environment.name):
            defaults.update(environment_defaults.model_dump())

        if project_defaults := self.projects.get((environment.name, bolt.project)):
            defaults.update(project_defaults.model_dump())

        return DefaultExecutionParameters(**defaults)
