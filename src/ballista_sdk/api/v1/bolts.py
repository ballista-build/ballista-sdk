from typing import Annotated, Literal, NamedTuple, Sequence, cast

from pydantic import BaseModel, Field

from .artifacts import Artifact, ArtifactReference, BuildableArtifact, ExecutableArtifact
from .common import BaseNamedModel
from .resources import Resource, ResourceReference
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


class ResourceProviderReference(NamedTuple):
    """Resource with reference to the providing Project and Artifact, if present."""

    resource: Resource
    project_name: str
    artifact_name: str | None
    version: str | None

    @property
    def artifact_reference(self) -> ArtifactReference | None:
        if self.artifact_name and self.version:
            return ArtifactReference(
                project_name=self.project_name, artifact_name=self.artifact_name, version=self.version
            )

    @property
    def resource_reference(self) -> ResourceReference:
        return ResourceReference(project_name=self.project_name, resource_name=self.resource.name)


class BoundSetting(NamedTuple):
    """A Setting bound to an owner."""

    setting: Setting
    artifact: ArtifactReference | None = None
    """Artifact setting exists in."""
    resource: ResourceReference | None = None
    """Resource setting exists in."""
    resource_instance: Sequence[str] | None = None
