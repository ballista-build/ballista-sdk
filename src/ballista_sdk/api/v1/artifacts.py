from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from .common import BaseNamedModel, BaseOneOfModel
from .healthchecks import ProvidedHealthchecks
from .resources import ProvidedResource, ResourceRequirementRequirement
from .services import ProvidedService
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
    dockerfile_context: Annotated[str | None, Field()] = None
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
## Resources
##
class ResourceRequirement(BaseOneOfModel):
    model_config = ConfigDict(extra="allow")

    __pydantic_extra__: dict[str, dict[str, ResourceRequirementRequirement]]

    @property
    def prefix(self) -> None:
        return None

    @property
    def project_name(self) -> str:
        return self.which()

    @property
    def resource_name(self) -> str:
        if self.__pydantic_extra__:
            for f in self.__pydantic_extra__.values():
                for v in f:
                    return v

        raise Exception(self.__pydantic_extra__)

    @property
    def resource_requirement(self) -> ResourceRequirementRequirement:
        if self.__pydantic_extra__:
            for f in self.__pydantic_extra__.values():
                for v in f.values():
                    return v

        raise Exception("WTF")


##
## Secrets
##
class SecretRequirement(Secret):
    shared: ClassVar[bool] = False


##
## Services
##
class ServiceRequirement(BaseOneOfModel):
    model_config = ConfigDict(extra="allow")

    __pydantic_extra__: dict[str, dict[str, str]]
    """Project Name -> Artifact Name -> Service Name"""

    @property
    def project_name(self) -> str:
        return self.which()

    @property
    def artifact_name(self) -> str:
        if self.__pydantic_extra__:
            for f in self.__pydantic_extra__.values():
                for v in f:
                    return v

        raise Exception(self.__pydantic_extra__)

    @property
    def service_name(self) -> str:
        if self.__pydantic_extra__:
            for f in self.__pydantic_extra__.values():
                for v in f.values():
                    return v

        raise Exception(self.__pydantic_extra__)


##
## Volumes
##
class VolumeRequirement(BaseNamedModel):
    capacity: Annotated[float, Field(description="Minimum storage capacity required, measured in Gibibytes.")] = 0.01
    path: Annotated[str, Field(description="Path inside service to access volume.")]
    persistent: Annotated[
        bool, Field(description="Indicates if volume data should persist outside execution lifecycle.")
    ] = True


class ArtifactExecutionProvides(BaseModel):
    """Provides from Artifact execution."""

    healthchecks: Annotated[
        ProvidedHealthchecks | None,
        Field(description="Healthchecks to monitor execution lifecycle."),
    ] = None
    resources: Annotated[
        list[ProvidedResource], Field(description="List of Resources provided when executing the artifact.")
    ] = []
    services: Annotated[
        list[ProvidedService],
        Field(description="List of Services provided when executing the Artifact."),
    ] = []


class ArtifactExecutionRequires(BaseModel):
    """Requirements for Artifact execution."""

    configs: Annotated[
        list[ConfigRequirement], Field(description="List of non-sensitive settings optional for execution.")
    ] = []
    resources: Annotated[list[ResourceRequirement], Field(description="List of Resources required for execution.")] = []
    secrets: Annotated[
        list[SecretRequirement], Field(description="List of sensitive settings required for execution.")
    ] = []
    services: Annotated[list[ServiceRequirement], Field(description="List of Services required for execution.")] = []
    volumes: Annotated[list[VolumeRequirement], Field(description="List of Volumes required for execution.")] = []


class ArtifactExecution(BaseModel):
    provides: Annotated[ArtifactExecutionProvides, Field(default_factory=ArtifactExecutionProvides)]
    requires: Annotated[ArtifactExecutionRequires, Field(default_factory=ArtifactExecutionRequires)]


#
# Artifact Types
#


class ArtifactType(BaseNamedModel):
    pass


# TODO: Update this to be dynamic like the resource requirements have done.
class DockerImageArtifactTypeRequirement(BaseModel):
    image: Annotated[str | None, Field(description="Existing Docker image name and tag.")] = None


class VirtualArtifactTypeRequirement(BaseModel):
    """Some kind of Virtual/fake artifact that isn't a thing but gives an attachment point."""

    pass


class ArtifactTypeRequirement(BaseOneOfModel):
    docker_image: Annotated[DockerImageArtifactTypeRequirement, Field(description="Artifact is a Docker image.")]


class Artifact(BaseNamedModel):
    annotations: Annotated[dict[str, str], Field(description="Annotations describing artifact.")] = {}
    build: Annotated[BuildParameters | None, Field(description="Parameters for building artifact.")] = None
    execution: Annotated[ArtifactExecution | None, Field()] = None
    type: Annotated[ArtifactTypeRequirement, Field(description="Type of artifact.")]
