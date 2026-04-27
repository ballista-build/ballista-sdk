from dataclasses import dataclass, field
from typing import Protocol

import aiohttp

from ballista_sdk.adapters.exceptions import ResourceException
from ballista_sdk.api.v1.resources import Resource, ResourceReference

from .provider import (
    ArtifactReference,
    Environment,
    ResourceAccess,
    ResourceProvider,
    ResourceProviderStatus,
    ResourceRequirement,
    ResourceStatus,
)


class ResourceProviderTransport(ResourceProvider, Protocol):
    """Message transport from Ballista to a ResourceProvider implementation."""

    pass


@dataclass
class RESTResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via REST API."""

    project_name: str
    """Project name of ResourceProvider."""
    resource_name: str
    """Name of Resource."""
    api_url: str
    """URL to implementation of REST API."""

    # TODO: It will probably make sense to have a shared instance of this for maximum pooling.
    _aiohttp_session: aiohttp.ClientSession = field(default_factory=aiohttp.ClientSession)

    def _request_headers(self):
        # TODO: Auth and more
        pass

    # Provider
    async def get_provider_status(self) -> ResourceProviderStatus:
        return ResourceProviderStatus.UNKNOWN

    # Resource
    async def get_resource_status(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> ResourceStatus:
        return ResourceStatus.UNKNOWN

    async def provision_resource(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        raise ResourceException(ResourceReference(self.project_name, self.resource_name))

    async def update_resource(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        raise ResourceException(ResourceReference(self.project_name, self.resource_name))

    # Resource Access
    async def get_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> ResourceAccess | None:
        raise ResourceException(ResourceReference(self.project_name, self.resource_name))

    async def grant_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        raise ResourceException(ResourceReference(self.project_name, self.resource_name))

    async def revoke_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        raise ResourceException(ResourceReference(self.project_name, self.resource_name))


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
            project_name=project_name,
            resource_name=resource.name,
            api_url=f"{service_url}/{resource.transport.rest.path}",
        )

    raise ResourceException("BLAH")
