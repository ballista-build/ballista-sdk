from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from ballista.types import ArtifactSettingType


class Resource(BaseModel, extra="forbid", frozen=True):
    id: Annotated[str, Field(description="Unique identifier of Resource.", title="ID")]
    name: Annotated[str, Field(description="Human-readable name of Resource.")]


class ArtifactBuildRequirements(BaseModel, extra="forbid", frozen=True, title="Artifact Build Requirements"):
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


class ArtifactExecutionResourceDependency(
    BaseModel, extra="forbid", frozen=True, title="Artifact Execution Resource Dependency"
):
    pass


class BaseArtifactExecutionSetting(BaseModel, extra="forbid", frozen=True):
    alias: Annotated[str | None, Field(description="Alias used when injecting value.")] = None
    id: Annotated[str, Field(description="Identifier", title="ID")]
    type: Annotated[ArtifactSettingType, Field(description="Type of secret value.", title="Type")]


class ArtifactExecutionConfig(BaseArtifactExecutionSetting, title="Artifact Execution Config"):
    """ArtifactExecution config value. Non-sensitive and optional."""

    pass


class ArtifactExecutionSecret(BaseArtifactExecutionSetting, title="Artifact Execution Secret"):
    """ArtifactExecution secret value. Sensitive and required."""

    pass


class ArtifactExecutionVolume(BaseModel, extra="forbid", frozen=True, title="Artifact Execution Volume"):
    id: Annotated[str, Field(description="Unique identifier of volume.", title="ID")]
    name: Annotated[str, Field(description="Human-readable name of volume.")]
    path: Annotated[str, Field(description="Path inside service to access volume.")]
    persistent: Annotated[
        bool, Field(description="Indicates if volume data should persist outside execution lifecycle.")
    ] = True


class ArtifactExecutionRequirements(BaseModel, extra="forbid", frozen=True, title="Artifact Execution Requirements"):
    configs: Annotated[
        list[ArtifactExecutionConfig], Field(description="List of non-sensitive settings optional for execution.")
    ] = []

    resources: Annotated[
        list[ArtifactExecutionResourceDependency], Field(description="List of Resources required for execution.")
    ] = []

    secrets: Annotated[
        list[ArtifactExecutionSecret], Field(description="List of sensitive settings required for execution.")
    ] = []

    volumes: Annotated[
        list[ArtifactExecutionVolume], Field(description="List of storage volumes required for execution.")
    ] = []


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


class ArtifactType(BaseModel, extra="forbid", frozen=True, title="Artifact Type"):
    id: Annotated[str, Field(description="Unique identifier of Artifact Type.", title="ID")]
    name: Annotated[str, Field(description="Human-readable name of Artifact Type.")]


class Artifact(BaseModel, extra="forbid", frozen=True):
    build: Annotated[ArtifactBuildRequirements | None, Field(description="Requirements for building artifact.")] = None
    execution: Annotated[
        ArtifactExecutionRequirements | None, Field(description="Requirements for artifact execution.")
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


class Environment(BaseModel, extra="forbid", frozen=True):
    """Environment that executes Artifacts."""

    hostname: Annotated[str, Field(description="Hostname of environment.")]
    id: Annotated[str, Field(description="Unique environment identifier.")]
    name: Annotated[str, Field(description="Human-readable name of environment.")]


class EnvironmentArtifactExecutionResources(BaseModel, extra="forbid", frozen=True):
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


class EnvironmentArtifactExecutionScaling(BaseModel, extra="forbid", frozen=True):
    max_replicas: int | None = None
    min_replicas: int | None = None
