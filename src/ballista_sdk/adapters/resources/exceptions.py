from dataclasses import dataclass


@dataclass
class ResourceProviderException(Exception):
    resource_project_name: str
    resource_name: str


@dataclass
class ArtifactResourceException(ResourceProviderException):
    artifact_project_name: str
    artifact_name: str
    artifact_version: str


class ResourceNotFound(ArtifactResourceException):
    """Resource not found."""

    pass


class ResourceAlreadyExists(ArtifactResourceException):
    """Resource already exists."""

    pass


class ResourceHasDependencies(ArtifactResourceException):
    """Resource has dependencies."""

    pass
