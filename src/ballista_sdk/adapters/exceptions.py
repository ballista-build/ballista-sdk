from dataclasses import dataclass

from ballista_sdk.api.v1 import ArtifactReference, ResourceReference


@dataclass
class ArtifactException(Exception):
    artifact: ArtifactReference


@dataclass
class ResourceException(Exception):
    resource: ResourceReference


class UnknownArtifact(ArtifactException):
    """Artifact referenced is unknown."""

    pass


class UnknownResource(ResourceException):
    """Resource referenced is unknown."""

    pass


class SettingMissing(ValueError):
    pass
