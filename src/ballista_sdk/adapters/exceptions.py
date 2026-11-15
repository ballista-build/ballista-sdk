from dataclasses import dataclass

from ballista_sdk.api.v1 import ResourceInstance

from .primitives import ArtifactReference, BoltReference, ProvidedResourceReference, ProvidedServiceReference


@dataclass
class BoltException(Exception):
    """Base for Bolt exceptions."""

    bolt: BoltReference


class BoltNotFound(BoltException):
    """Bolt referenced was not found."""

    pass


class BoltArtifactTypesUnavailable(BoltException):
    """Bolt could not be deployed because none of its Artifacts had fulfilled ArtifactTypes."""

    pass


@dataclass
class ArtifactException(Exception):
    """Base for Artifact exceptions."""

    artifact: ArtifactReference


class ArtifactNotFound(ArtifactException):
    """Artifact referenced was not found."""

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
class ResourceException[R: ResourceInstance = ResourceInstance](ProvidedResourceException):
    """Exceptions for Resources."""

    resource: R


class ResourceAlreadyExists[R: ResourceInstance = ResourceInstance](ResourceException[R]):
    """Resource already exists."""

    pass


class ResourceNotFound[R: ResourceInstance = ResourceInstance](ResourceException[R]):
    """Resource not found."""

    pass


class SettingMissing(ValueError):
    pass
