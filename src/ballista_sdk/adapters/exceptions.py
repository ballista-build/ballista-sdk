from dataclasses import dataclass

from .primitives import ArtifactReference, ProvidedResourceReference, ProvidedServiceReference


@dataclass
class ArtifactException(Exception):
    artifact: ArtifactReference


class ArtifactNotFound(ArtifactException):
    """Artifact referenced is unknown."""

    pass


@dataclass
class ProvidedResourceException(Exception):
    provided_resource: ProvidedResourceReference


class ProvidedResourceNotFound(ProvidedResourceException):
    """Resource referenced is unknown."""

    pass


@dataclass
class ProvidedServiceException(Exception):
    provided_service: ProvidedServiceReference


class ProvidedServiceNotFound(ProvidedServiceException):
    """Service referenced is not found."""

    pass


@dataclass
class ArtifactResourceException(ProvidedResourceException, ArtifactException):
    """Exceptions for Artifact Resources."""

    pass


class ArtifactResourceAlreadyExists(ArtifactResourceException):
    """Artifact Resource already exists."""

    pass


class ArtifactResourceNotFound(ArtifactResourceException):
    pass


class SettingMissing(ValueError):
    pass
