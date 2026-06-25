from dataclasses import dataclass, field
from typing import Protocol

import aiohttp

from ballista_sdk.adapters.exceptions import ResourceException
from ballista_sdk.api.v1.resources import Resource, ResourceReference

from .exceptions import ResourceAlreadyExists, ResourceNotFound
from .provider import (
    ArtifactReference,
    Environment,
    ResourceAccess,
    ResourceProvider,
    ResourceProviderStatus,
    ResourceRequirement,
    ResourceStatus,
)


@dataclass
class ResourceProviderTransport(ResourceProvider, Protocol):
    """Message transport to a ResourceProvider implementation."""

    resource_project_name: str
    """Project name of ResourceProvider."""
    resource_name: str
    """Name of Resource."""


@dataclass
class ExecResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via command execution."""

    pass


@dataclass
class MemoryResourceProviderTransport(ResourceProviderTransport):
    _resources: dict[Environment, dict[ArtifactReference, list[ResourceRequirement]]] = field(
        default_factory=dict, init=False
    )

    async def get_status(self, environment: Environment) -> ResourceProviderStatus:
        return ResourceProviderStatus.AVAILABLE

    # Resource
    async def list_resources(self, artifact: ArtifactReference, environment: Environment) -> list:
        return self._resources.get(environment, {}).get(artifact, [])

    async def get_resource_status(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> ResourceStatus:
        if resource_requirement in self._resources.get(environment, {}).get(artifact, []):
            return ResourceStatus.AVAILABLE
        else:
            return ResourceStatus.NOT_FOUND

    async def provision_resource(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        if resource_requirement in self._resources.get(environment, {}).get(artifact, []):
            raise ResourceAlreadyExists(
                resource_project_name=self.resource_project_name,
                resource_name=self.resource_name,
                artifact_project_name=artifact.project_name,
                artifact_name=artifact.artifact_name,
                artifact_version=artifact.version,
            )

        self._resources.setdefault(environment, {}).setdefault(artifact, []).append(resource_requirement)

    async def update_resource(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        if resource_requirement not in self._resources.get(environment, {}).get(artifact, []):
            raise ResourceNotFound(
                resource_project_name=self.resource_project_name,
                resource_name=self.resource_name,
                artifact_project_name=artifact.project_name,
                artifact_name=artifact.artifact_name,
                artifact_version=artifact.version,
            )

    # Resource Access
    async def get_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> ResourceAccess | None:
        pass

    async def grant_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        pass

    async def revoke_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        pass


@dataclass
class RESTResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via REST API."""

    api_url: str
    """URL to implementation of REST API."""

    # TODO: It will probably make sense to have a shared instance of this for maximum pooling.
    _aiohttp_session: aiohttp.ClientSession = field(default_factory=aiohttp.ClientSession)

    def _request_headers(self):
        # TODO: Auth and more
        pass

    # Provider
    async def get_status(self, environment: Environment) -> ResourceProviderStatus:
        async with self._aiohttp_session.get(f"{environment.tier}/{environment.name}/") as response:
            return ResourceProviderStatus(response.json())

    # Resource
    async def list_resources(self, artifact: ArtifactReference, environment: Environment) -> list:
        async with self._aiohttp_session.get("") as response:
            pass
        return []

    async def get_resource_status(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> ResourceStatus:
        async with self._aiohttp_session.get(
            f"{environment.tier}/{environment.name}/{artifact.project_name}/{artifact.artifact_name}/{artifact.version}/"
        ) as response:
            return ResourceStatus(response.json())

    async def provision_resource(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        raise ResourceException(ResourceReference(self.resource_project_name, self.resource_name))

    async def update_resource(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        raise ResourceException(ResourceReference(self.resource_project_name, self.resource_name))

    # Resource Access
    async def get_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> ResourceAccess | None:
        raise ResourceException(ResourceReference(self.resource_project_name, self.resource_name))

    async def grant_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        raise ResourceException(ResourceReference(self.resource_project_name, self.resource_name))

    async def revoke_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        raise ResourceException(ResourceReference(self.resource_project_name, self.resource_name))


class GRPCResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via GRPC."""

    pass


class TCPResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via TCP socket."""

    pass


class QueueResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via message queue."""

    pass


def transport_resource_provider(project_name: str, resource: Resource) -> ResourceProviderTransport:
    """Transport a Resource's provider via the designated method."""
    if resource.transport.rest:
        # TODO: Get artifact service URL
        service_url = ""
        return RESTResourceProviderTransport(
            resource_project_name=project_name,
            resource_name=resource.name,
            api_url=f"{service_url}/{resource.transport.rest.path}",
        )

    raise ResourceException("BLAH")
