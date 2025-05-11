from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


# Artifact Types
class ArtifactType(BaseModel):
    id: str = Field(description="Reference key")
    name: str = Field(description="Human-readable name")


class DockerImageArtifactConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(description="Name of image to use.")] = None


class DockerImageArtifactTypeDependency(BaseModel):
    model_config = ConfigDict(extra="forbid")

    docker_image: DockerImageArtifactConfiguration


# TODO: Do fancier setup here later
class ArtifactTypeDependency(DockerImageArtifactTypeDependency):
    @property
    def config(self) -> dict:
        return self.docker_image.model_dump()

    @property
    def id(self) -> str:
        return "docker_image"


class PlatformResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Annotated[str, Field(description="Reference key")]
    name: Annotated[str, Field(description="Human-readable name")]

    launch_target_key: Annotated[str, Field(description="Launch Target platform resource exists")]


# Platform Resource Needs
class BasePlatformResourceNeed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlatformResourceNeed(BasePlatformResourceNeed):
    pass


class PlatformResourceDependency(BaseModel):
    pass


class ArtifactExecutionLocalResourceNeeds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_cpu: Annotated[
        float | None,
        Field(
            description="Maximum CPU allowed, measured in cores.", title="Max Allowed CPU", gt=0, examples=[1.0, 0.05]
        ),
    ] = None
    max_memory: Annotated[
        float | None,
        Field(
            description="Maximum memory allowed, measured in Gibibytes.",
            title="Max Allowed Memory",
            gt=0,
            examples=[1, 0.25],
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
            examples=[1, 0.25],
        ),
    ] = None


class ArtifactExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # dependency_variables: Annotated[
    #     list[ArtifactExecutionDependencyVariable],
    #     Field(description="List of Variables injected to dependent services."),
    # ] = []
    local_resources: Annotated[
        ArtifactExecutionLocalResourceNeeds,
        Field(
            description="Local environment resources required for execution.",
            title="Local Resources",
        ),
    ] = ArtifactExecutionLocalResourceNeeds()
    platform_resources: Annotated[
        list[PlatformResourceNeed], Field(description="List of platform resources needed.")
    ] = []


class Artifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dockerfile: Annotated[
        str | None,
        Field(
            description="Name of Dockerfile, relative to project root, to find the indicated `dockerfile_stage`.",
        ),
    ] = None
    dockerfile_stage: Annotated[
        str | None,
        Field(
            description="Name of stage inside Dockerfile that will contain the artifact. Required for building.",
            title="Dockerfile Stage",
        ),
    ] = None
    execution: Annotated[ArtifactExecution | None, Field(description="Resources artifact requires for execution.")] = (
        None
    )
    id: Annotated[str, Field(description="Unique identifier of artifact within project.")]
    type: Annotated[
        ArtifactTypeDependency,
        Field(description="Type of artifact."),
    ]
    version: Annotated[str | None, Field(description="Artifact-specified version.")] = None


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Annotated[str, Field(description="Unique identifer of project, across all environments.")]
    name: Annotated[str, Field(description="Human-readable name of project.")]


class Bolt(BaseModel):
    """A bundle of artifact definitions."""

    # TODO: Fix the versioning thing
    api_version: Annotated[
        Literal["v1"], Field(description="API version the Bolt is adhering to.", title="API Version")
    ]
    artifacts: Annotated[list[Artifact], Field(description="List of artifacts.", min_length=1)]
    project_id: Annotated[str, Field(description="Project identifier.")]
    version: Annotated[str, Field(description="Version of Bolt.")]

    @property
    def executable_artifacts(self) -> list[Artifact]:
        return [a for a in self.artifacts if a.execution]
