from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, Field

from ballista.types import ArtifactSettingType


class BaseOneOfModel(BaseModel, json_schema_extra={"maxProperties": 1, "minProperties": 1}):
    pass


class Resource(BaseModel, frozen=True):
    """Resource available to use as an artifact dependency."""

    id: Annotated[str, Field(description="Unique identifier of Resource.", title="ID")]
    name: Annotated[str, Field(description="Human-readable name of Resource.")]


class ArtifactExecutionResourceDependency(BaseOneOfModel, frozen=True, title="Artifact Execution Resource Dependency"):
    @property
    def config(self) -> dict:
        return {}

    @property
    def resource_id(self) -> str:
        return "TEST"


class BaseArtifactExecutionResource(BaseModel, frozen=True):
    pass


class ArtifactBuildRequirements(BaseModel, frozen=True, title="Artifact Build Requirements"):
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


class BaseArtifactExecutionSetting(BaseModel, frozen=True):
    alias: Annotated[str | None, Field(description="Alias used when injecting value.")] = None
    id: Annotated[str, Field(description="Identifier", title="ID")]
    type: Annotated[ArtifactSettingType, Field(description="Type of secret value.", title="Type")]


class ArtifactExecutionConfig(BaseArtifactExecutionSetting, title="Artifact Execution Config"):
    """ArtifactExecution config value. Non-sensitive and optional."""

    pass


class ArtifactExecutionExecProbe(BaseModel, frozen=True):
    """Probe that executes a list of commands."""

    commands: Annotated[list[str], Field(description="List of commands executed.")]


class BaseArtifactExecutionPortProbe(BaseModel):
    port: Annotated[int | None, Field(description="Port number to probe.")] = None
    service_id: Annotated[
        str | None, Field(description="Unique identifier of service to probe.", title="Service ID")
    ] = None


class ArtifactExecutionPortProbe(BaseArtifactExecutionPortProbe, frozen=True):
    """Probe that uses a TCP port."""

    pass


class ArtifactExecutionGRPCProbe(BaseArtifactExecutionPortProbe, frozen=True):
    """Probe that uses the standard GRPC Healthcheck V1 service."""

    pass


class ArtifactExecutionHTTPProbe(BaseArtifactExecutionPortProbe, frozen=True):
    """Probe that uses HTTP."""

    path: Annotated[str | None, Field(description="HTTP path to probe.")] = None


class ArtifactExecutionProbe(BaseOneOfModel):
    exec: Annotated[ArtifactExecutionExecProbe | None, Field()] = None
    grpc: Annotated[ArtifactExecutionGRPCProbe | None, Field()] = None
    http: Annotated[ArtifactExecutionHTTPProbe | None, Field()] = None
    port: Annotated[ArtifactExecutionPortProbe | None, Field()] = None


class ArtifactExecutionHealthchecks(BaseModel):
    alive: ArtifactExecutionProbe | None = None
    ready: ArtifactExecutionProbe | None = None
    started: ArtifactExecutionProbe | None = None


class ArtifactExecutionSecret(BaseArtifactExecutionSetting, title="Artifact Execution Secret"):
    """ArtifactExecution secret value. Sensitive and required."""

    pass


class ArtifactExecutionService(BaseModel):
    """A network-connected port with unique identifier."""

    id: Annotated[str, Field(description="Unique identifier of the service.", title="Service ID")]
    port: Annotated[int, Field(description="Port number connected by the service.")]


class ArtifactExecutionVolume(BaseModel, frozen=True, title="Artifact Execution Volume"):
    capacity: Annotated[float, Field(description="Minimum storage capacity required, measured in Gibibytes.")] = 0.01
    id: Annotated[str, Field(description="Unique identifier of volume.", title="ID")]
    name: Annotated[str, Field(description="Human-readable name of volume.")]
    path: Annotated[str, Field(description="Path inside service to access volume.")]
    persistent: Annotated[
        bool, Field(description="Indicates if volume data should persist outside execution lifecycle.")
    ] = True


class ArtifactExecutionRequirements(BaseModel, frozen=True, title="Artifact Execution Requirements"):
    configs: Annotated[
        list[ArtifactExecutionConfig], Field(description="List of non-sensitive settings optional for execution.")
    ] = []

    healthchecks: Annotated[
        ArtifactExecutionHealthchecks | None, Field(description="Healthchecks to ensure correct execution.")
    ] = None

    resources: Annotated[
        list[ArtifactExecutionResourceDependency], Field(description="List of Resources required for execution.")
    ] = []

    secrets: Annotated[
        list[ArtifactExecutionSecret], Field(description="List of sensitive settings required for execution.")
    ] = []

    services: Annotated[
        list[ArtifactExecutionService],
        Field(description="List of services required for execution to process."),
    ] = []

    volumes: Annotated[
        list[ArtifactExecutionVolume], Field(description="List of storage volumes required for execution.")
    ] = []


class DockerImageArtifactConfiguration(BaseModel, frozen=True):
    image: Annotated[str | None, Field(description="Name of image to use.")] = None


class DockerImageArtifactTypeDependency(BaseOneOfModel, frozen=True):
    docker_image: DockerImageArtifactConfiguration


# Artifact Types


# TODO: Do fancier setup here later
class ArtifactTypeDependency(DockerImageArtifactTypeDependency):
    artifact_type_id: ClassVar[Literal["docker_image"]] = "docker_image"

    @property
    def config(self) -> dict[str, Any]:
        return getattr(self, self.artifact_type_id).model_dump()


class ArtifactType(BaseModel, frozen=True, title="Artifact Type"):
    id: Annotated[str, Field(description="Unique identifier of Artifact Type.", title="ID")]
    name: Annotated[str, Field(description="Human-readable name of Artifact Type.")]


class Artifact(BaseModel, frozen=True):
    build: Annotated[ArtifactBuildRequirements | None, Field(description="Requirements for building artifact.")] = None
    execution: Annotated[
        ArtifactExecutionRequirements | None, Field(description="Requirements for artifact execution.")
    ] = None
    id: Annotated[str, Field(description="Unique identifier of artifact within project.", title="ID")]
    type: Annotated[
        ArtifactTypeDependency,
        Field(description="Type of artifact."),
    ]


class Project(BaseModel, frozen=True):
    id: Annotated[str, Field(description="Unique identifer of project, across all environments.", title="ID")]
    name: Annotated[str, Field(description="Human-readable name of project.")]


class Bolt(BaseModel, frozen=True):
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


class Environment(BaseModel, frozen=True):
    """Environment that executes Artifacts."""

    hostname: Annotated[str, Field(description="Hostname of environment.")]
    id: Annotated[str, Field(description="Unique environment identifier.")]
    name: Annotated[str, Field(description="Human-readable name of environment.")]


class EnvironmentArtifactExecutionResources(BaseModel, frozen=True):
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


class EnvironmentArtifactExecutionScaling(BaseModel, frozen=True):
    max_replicas: Annotated[
        int | None, Field(description="Maximum number of replicas of executing artifact.", gt=0)
    ] = None
    min_replicas: Annotated[
        int | None, Field(description="Minimum number of replicas of executing artifact.", ge=0)
    ] = None
