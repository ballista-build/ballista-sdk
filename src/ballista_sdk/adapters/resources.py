from typing import Protocol

from ballista_sdk.api.v1 import ArtifactReference, Environment, ResourceRequirement
from ballista_sdk.api.v1.resources import ResourceProviderStatus, ResourceStatus


class ResourceProviderTransport(Protocol):
    pass


class RESTResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via REST API."""

    pass


class GRPCResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via GRPC."""

    pass


class TCPResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via TCP socket."""

    pass


class ResourceProvider(Protocol):
    """ResourceProvider interface. 1:1 match for each registered Resource."""

    def get_status(self, environment: Environment) -> ResourceProviderStatus:
        """Get the status of the ResourceProvider itself."""
        ...

    def get_resource_status(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> ResourceStatus:
        """Get the status of a specific Resource."""
        ...

    def provision_resource(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        """Provisions a new resuorce. Grants ownership."""
        ...

    def update_resource(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        """Resource needs a minor update."""
        ...

    def copy_resource(
        self,
        artifact: ArtifactReference,
        resource_requirement: ResourceRequirement,
        environment: Environment,
        dest_environment: Environment,
    ):
        """Copy existing Resource to a destination Environment."""
        ...

    def destroy_resource(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ): ...

    def get_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        """Get access level to resource."""
        ...

    def add_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        """Add access to resource."""
        ...

    def remove_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        """Remove access to resource."""
        ...
