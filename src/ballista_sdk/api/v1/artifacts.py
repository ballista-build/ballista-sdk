from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from . import actions
from .common import BaseNamedModel, BaseOneOfModel
from .resources import Resource
from .settings import Config, Secret


#
# Build
#
class BuildParameters(BaseModel):
    """Parameters dictating how to build the Artifact."""

    dockerfile: Annotated[
        str | None,
        Field(
            description="Name of Dockerfile, relative to project root, to find the indicated `dockerfile_target`.",
        ),
    ] = None
    dockerfile_target: Annotated[
        str | None,
        Field(
            description="Name of stage inside Dockerfile that will contain the artifact. Required for building.",
            title="Dockerfile Target",
        ),
    ] = None


#
# Execution
#


##
## Configs
##
class ConfigRequirement(Config):
    shared: ClassVar[bool] = False


##
## Healthchecks
##
class GRPCHealthCheckAction(actions.GRPCAction):
    """Action that uses the GPRC Health Checking Protocol."""

    pass


class HealthcheckProbe(BaseOneOfModel):
    exec: Annotated[actions.ExecAction | None, Field()] = None
    grpc: Annotated[GRPCHealthCheckAction | None, Field()] = None
    http: Annotated[actions.HTTPGETAction | None, Field()] = None
    tcp: Annotated[actions.TCPAction | None, Field()] = None


class HealthcheckRequirements(BaseModel):
    alive: HealthcheckProbe | None = None
    ready: HealthcheckProbe | None = None
    started: HealthcheckProbe | None = None


##
## Resources
##
class ResourceRequirement(BaseModel):
    """A Resource requirement with optional prefix."""

    model_config = ConfigDict(extra="allow")

    prefix: Annotated[
        str | None, Field(description="Prefix for injected Resource values. Defaults to Resource's prefix if not set.")
    ] = None
    # service: Annotated[str | None, Field(description="Connect to referenced service by name.")] = None

    @property
    def requirement(self) -> BaseModel:
        for f in self.model_fields_set:
            if f != "prefix":
                return getattr(self, f)

        raise Exception("WTF")

    @property
    def resource_name(self) -> str:
        for f in self.model_fields_set:
            if f != "prefix":
                return f

        raise Exception("WTF")


class ProjectResourceRequirement(BaseOneOfModel):
    """Execution requirement for a specific Project Resource."""

    model_config = ConfigDict(extra="allow")

    def which(self) -> str | None:
        which = super().which()
        if which:
            return which

        # Check extra data
        raise Exception(self.__pydantic_extra__)

    @property
    def _resource_requirement(self) -> ResourceRequirement:
        if which := self.which():
            return getattr(self, which)

        # Check extra data for an unregistered requirement
        raise Exception(self.__pydantic_extra__)

    @property
    def prefix(self) -> str | None:
        return self._resource_requirement.prefix

    @property
    def requirement(self) -> BaseModel:
        return self._resource_requirement.requirement

    @property
    def resource_name(self) -> str:
        """Unique identifier for Resource."""
        return self._resource_requirement.resource_name


##
## Secrets
##
class SecretRequirement(Secret):
    shared: ClassVar[bool] = False


##
## Services
##
class ServiceRequirement(BaseNamedModel):
    """A network-connected port with unique identifier."""

    grpc: Annotated[int | None, Field(description="GRPC service available on specified port.")] = None
    http: Annotated[int | None, Field()] = None
    tcp: Annotated[int | None, Field()] = None


##
## Volumes
##
class VolumeRequirement(BaseNamedModel):
    capacity: Annotated[float, Field(description="Minimum storage capacity required, measured in Gibibytes.")] = 0.01
    path: Annotated[str, Field(description="Path inside service to access volume.")]
    persistent: Annotated[
        bool, Field(description="Indicates if volume data should persist outside execution lifecycle.")
    ] = True


class ExecutionRequirements(BaseModel):
    configs: Annotated[
        list[ConfigRequirement], Field(description="List of non-sensitive settings optional for execution.")
    ] = []
    healthchecks: Annotated[
        HealthcheckRequirements | None,
        Field(description="Healthchecks to ensure monitor execution lifecycle."),
    ] = None
    resources: Annotated[
        list[ProjectResourceRequirement], Field(description="List of Resources required for execution.")
    ] = []
    secrets: Annotated[
        list[SecretRequirement], Field(description="List of sensitive settings required for execution.")
    ] = []
    services: Annotated[
        list[ServiceRequirement],
        Field(description="List of Services required for execution to process."),
    ] = []
    volumes: Annotated[list[VolumeRequirement], Field(description="List of Volumes required for execution.")] = []


#
# Artifact Types
#


class ArtifactType(BaseNamedModel):
    pass


class DockerImageArtifactTypeRequirement(BaseModel):
    image: Annotated[str | None, Field(description="Existing Docker image name and tag.")] = None


class ArtifactTypeRequirement(BaseOneOfModel):
    docker_image: Annotated[DockerImageArtifactTypeRequirement, Field(description="Artifact is a Docker image.")]


class Artifact(BaseNamedModel):
    annotations: Annotated[dict[str, str], Field(description="Annotations describing artifact.")] = {}
    build: Annotated[BuildParameters | None, Field(description="Parameters for building artifact.")] = None
    execution: Annotated[ExecutionRequirements | None, Field(description="Requirements for artifact execution.")] = None
    provides: Annotated[list[Resource], Field(description="Resources provided by the artifact.")] = []
    type: Annotated[ArtifactTypeRequirement, Field(description="Type of artifact.")]


class BuildableArtifact(Artifact):
    build: Annotated[BuildParameters, Field(description="Parameters for building artifact.")]


class ExecutableArtifact(Artifact):
    """An artifact that can be executed in an environment."""

    execution: Annotated[ExecutionRequirements, Field(description="Requirements for artifact execution.")]
