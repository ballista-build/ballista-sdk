from collections.abc import Sequence
from typing import NamedTuple

from ballista_sdk.api.v1 import ProvidedResource, ProvidedService, Setting


class ProjectReference(NamedTuple):
    project_name: str


class BoltReference(NamedTuple):
    """Reference to a Bolt by its name and version."""

    project_name: str
    version: str


class ArtifactReference(NamedTuple):
    """Reference to an Artifact by its name, a version, and the Project's name its in."""

    project_name: str
    artifact_name: str
    version: str


class ProvidedResourceReference(NamedTuple):
    """Reference to a Provided Resource by its name and the Project's name its in."""

    project_name: str
    resource_name: str


class ProvidedServiceReference(NamedTuple):
    project_name: str
    artifact_name: str
    service_name: str


class ProvidedResourceWithArtifactReference(NamedTuple):
    """Provided Resource with reference to the providing Artifact."""

    provided_resource: ProvidedResource
    artifact_reference: ArtifactReference

    @property
    def provided_resource_reference(self) -> ProvidedResourceReference:
        return ProvidedResourceReference(
            project_name=self.artifact_reference.project_name, resource_name=self.provided_resource.name
        )


class ProvidedServiceWithArtifactReference(NamedTuple):
    """Provided Service with reference to the providing Artifact."""

    provided_service: ProvidedService
    artifact_reference: ArtifactReference

    @property
    def provided_service_reference(self) -> ProvidedServiceReference:
        return ProvidedServiceReference(
            project_name=self.artifact_reference.project_name,
            artifact_name=self.artifact_reference.artifact_name,
            service_name=self.provided_service.name,
        )


class BoundSetting(NamedTuple):
    """A Setting bound to an owner."""

    setting: Setting
    artifact: ArtifactReference | None = None
    """Artifact setting exists in."""
    provided_resource: ProvidedResourceReference | None = None
    """Resource setting exists in."""
    resource_instance: Sequence[str] | None = None
