from typing import Annotated, Literal, NamedTuple, Sequence, cast

from pydantic import BaseModel, Field

from .artifacts import Artifact, ArtifactReference, BuildableArtifact, ExecutableArtifact, ProvidedService
from .common import BaseNamedModel
from .resources import ProvidedResource, ResourceProviderReference
from .services import ServiceProviderReference
from .settings import Setting


class Bolt(BaseModel, frozen=True):
    """A deployable bundle of artifact definitions."""

    # TODO: Fix the versioning thing
    api_version: Annotated[
        Literal["v1"], Field(description="API version the Bolt is adhering to.", title="API Version")
    ] = "v1"
    artifacts: Annotated[list[Artifact], Field(description="List of artifacts.")]
    project: Annotated[str, Field(description="Project name.")]
    # provides: Annotated[list | None, Field(description="Resources provided by Bolt that are not tied to Artifacts.")] = []
    version: Annotated[str, Field(description="Version of Bolt.")]

    @property
    def buildable_artifacts(self) -> list[BuildableArtifact]:
        return [cast(BuildableArtifact, a) for a in self.artifacts if a.build]

    @property
    def executable_artifacts(self) -> list[ExecutableArtifact]:
        return [cast(ExecutableArtifact, a) for a in self.artifacts if a.execution]


class Project(BaseNamedModel, frozen=True):
    pass


class ProvidedResourceWithArtifactReference(NamedTuple):
    """Provided Resource with reference to the providing Artifact."""

    provided_resource: ProvidedResource
    project_name: str
    """Project name of Resource Provider."""
    artifact_name: str
    """Artifact name of Resource Provider."""
    version: str
    """Version of Artifact for the Resource Provider."""

    @property
    def artifact_reference(self) -> ArtifactReference:
        return ArtifactReference(project_name=self.project_name, artifact_name=self.artifact_name, version=self.version)

    @property
    def resource_provider_reference(self) -> ResourceProviderReference:
        return ResourceProviderReference(project_name=self.project_name, resource_name=self.provided_resource.name)


class ProvidedServiceWithArtifactReference(NamedTuple):
    """Provided Service with reference to the providing Artifact."""

    provided_service: ProvidedService
    project_name: str
    """Project name of Service Provider."""
    artifact_name: str
    """Artifact name of Service Provider."""
    version: str
    """Version of Artifact for the Service Provider."""

    @property
    def artifact_reference(self) -> ArtifactReference:
        return ArtifactReference(project_name=self.project_name, artifact_name=self.artifact_name, version=self.version)

    @property
    def service_provider_reference(self) -> ServiceProviderReference:
        return ServiceProviderReference(
            project_name=self.project_name, artifact_name=self.artifact_name, service_name=self.provided_service.name
        )


class BoundSetting(NamedTuple):
    """A Setting bound to an owner."""

    setting: Setting
    artifact: ArtifactReference | None = None
    """Artifact setting exists in."""
    resource_provider: ResourceProviderReference | None = None
    """Resource setting exists in."""
    resource_instance: Sequence[str] | None = None
