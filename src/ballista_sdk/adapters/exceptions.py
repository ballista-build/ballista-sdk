from dataclasses import dataclass

from ballista_sdk.api.v1 import ArtifactReference, ResourceProviderReference


@dataclass
class ArtifactException(Exception):
    artifact: ArtifactReference


class ArtifactNotFound(ArtifactException):
    """Artifact referenced is unknown."""

    pass


@dataclass
class ResourceProviderException(Exception):
    resource_provider: ResourceProviderReference


class ResourceProviderNotFound(ResourceProviderException):
    """Resource referenced is unknown."""

    pass


@dataclass
class ArtifactResourceException(ResourceProviderException, ArtifactException):
    """Exceptions for Artifact Resources."""

    pass


class ArtifactResourceAlreadyExists(ArtifactResourceException):
    """Artifact Resource already exists."""

    pass


class ArtifactResourceNotFound(ArtifactResourceException):
    pass


class SettingMissing(ValueError):
    pass
