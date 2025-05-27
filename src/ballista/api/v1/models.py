from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from ballista.types import ArtifactSettingType


class ArtifactBuildParameters(BaseModel, extra="forbid", frozen=True):
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


class ArtifactExecutionLocalResourceNeeds(BaseModel, extra="forbid", frozen=True):
    max_cpu: Annotated[
        float | None,
        Field(
            description="Maximum CPU allowed, measured in cores.",
            title="Maximum Allowed CPU",
            gt=0,
            examples=[1.0, 0.05],
        ),
    ] = None
    max_memory: Annotated[
        float | None,
        Field(
            description="Maximum memory allowed, measured in Gibibytes.",
            title="Maximum Allowed Memory",
            gt=0,
            examples=[1.0, 0.25],
        ),
    ] = None
    min_cpu: Annotated[
        float | None,
        Field(
            description="Minimum CPU required, measured in cores.",
            title="Minimum Required CPU",
            gt=0,
            examples=[1.0, 0.05],
        ),
    ] = None
    min_memory: Annotated[
        float | None,
        Field(
            description="Minimum memory required, measured in Gibibytes.",
            title="Minimum Required Memory",
            gt=0,
            examples=[1.0, 0.25],
        ),
    ] = None


class BaseArtifactExecutionSetting(BaseModel, extra="forbid", frozen=True):
    alias: Annotated[str | None, Field(description="Alias used when injecting value.")] = None
    id: Annotated[str, Field(description="Identifier")]
    type: Annotated[ArtifactSettingType, Field(description="Type of secret value.")]


class ArtifactExectionConfig(BaseArtifactExecutionSetting):
    """ArtifactExecution config value. Non-sensitive and optional."""

    pass


class ArtifactExecutionSecret(BaseArtifactExecutionSetting):
    """ArtifactExecution secret value. Sensitive and required."""

    pass


class ArtifactExecutionParameters(BaseModel, extra="forbid", frozen=True):
    configs: Annotated[list[ArtifactExectionConfig], Field(description="List of optional configurations.")] = []

    # dependency_variables: Annotated[
    #     list[ArtifactExecutionDependencyVariable],
    #     Field(description="List of Variables injected to dependent services."),
    # ] = []
    local_resources: Annotated[
        ArtifactExecutionLocalResourceNeeds,
        Field(
            description="Local environment resources required for execution.",
        ),
    ] = ArtifactExecutionLocalResourceNeeds()
    # platform_resources: Annotated[
    #     list[PlatformResourceDependency], Field(description="List of platform resources needed.")
    # ] = []
    #

    secrets: Annotated[list[ArtifactExecutionSecret], Field(description="List of required secrets.")] = []


class DockerImageArtifactConfiguration(BaseModel, extra="forbid", frozen=True):
    image: Annotated[str | None, Field(description="Name of image to use.")] = None


class DockerImageArtifactTypeDependency(BaseModel, extra="forbid", frozen=True):
    docker_image: DockerImageArtifactConfiguration


# Artifact Types


# TODO: Do fancier setup here later
class ArtifactTypeDependency(DockerImageArtifactTypeDependency):
    @property
    def artifact_type_id(self) -> str:
        return "docker_image"

    @property
    def config(self) -> dict[str, Any]:
        return getattr(self, self.artifact_type_id).model_dump()


class ArtifactType(BaseModel, extra="forbid", frozen=True):
    id: Annotated[str, Field(description="Unique identifier of Artifact Type.")]
    name: Annotated[str, Field(description="Human-readable name of Artifact Type.")]


class PlatformResource(BaseModel, extra="forbid", frozen=True):
    id: Annotated[str, Field(description="Unique identifier of Platform Resource.")]
    name: Annotated[str, Field(description="Human-readable name of Platform Resource.")]


# class PlatformResourceDependency(BaseModel, extra="forbid", frozen=True):
#     platform_resource_id: Annotated[str, Field()]
#     config: Annotated[dict, Field()] = {}


class Artifact(BaseModel, extra="forbid", frozen=True):
    build: Annotated[ArtifactBuildParameters | None, Field(description="Parameters for building artifact.")] = None
    execution: Annotated[
        ArtifactExecutionParameters | None, Field(description="Parameters artifact requires for execution.")
    ] = None
    id: Annotated[str, Field(description="Unique identifier of artifact within project.", title="ID")]
    type: Annotated[
        ArtifactTypeDependency,
        Field(description="Type of artifact."),
    ]


class Project(BaseModel, extra="forbid", frozen=True):
    id: Annotated[str, Field(description="Unique identifer of project, across all environments.", title="ID")]
    name: Annotated[str, Field(description="Human-readable name of project.")]


class Bolt(BaseModel, extra="forbid", frozen=True):
    """A bundle of artifact definitions."""

    # TODO: Fix the versioning thing
    api_version: Annotated[
        Literal["v1"], Field(description="API version the Bolt is adhering to.", title="API Version")
    ]
    artifacts: Annotated[list[Artifact], Field(description="List of artifacts.", min_length=1)]
    project_id: Annotated[str, Field(description="Project identifier.", title="Project ID")]
    version: Annotated[str, Field(description="Version of Bolt.")]

    @property
    def executable_artifacts(self) -> list[Artifact]:
        return [a for a in self.artifacts if a.execution]


class ExecutionEnvironment(BaseModel, extra="forbid", frozen=True):
    """Environment that executes Artifacts."""

    hostname: Annotated[str, Field(description="Hostname of environment.")]
    id: Annotated[str, Field(description="Unique environment identifier.")]
    name: Annotated[str, Field(description="Human-readable name of environment.")]
