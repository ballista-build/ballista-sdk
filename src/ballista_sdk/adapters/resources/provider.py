from typing import Protocol

from ballista_sdk.api.v1 import (
    ArtifactReference,
    Environment,
    ResourceAccess,
    ResourceProviderStatus,
    ResourceRequirement,
    ResourceStatus,
)


class ResourceProvider(Protocol):
    """ResourceProvider interface.

    Resources provided by Python code should use this. A ResourceProviderTransport will communicate with it."""

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
        """Provisions a new resource. Grants ownership.

        :raises ResourceAlreadyExists: Resource already exists and can't be provisioned.
        :raises ResourceProviderException: Resource could not be provisioned.
        """
        ...

    def update_resource(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        """Updates an existing resource. If the requirement changes are substantial, triggers a re-provisioning.

        Resource can be updated while it is `PROVISIONING`, `AVAILABLE`, or `UNHEALTHY`.

        :raises ResourceNotFound: Resource could not be found to update.
        :raises ResourceProviderException: Resource could not be updated."""
        ...

    def triggers_reprovision(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> bool:
        """Returns if a resource requirement update would trigger a reprovision."""
        ...

    def copy_resource(
        self,
        artifact: ArtifactReference,
        resource_requirement: ResourceRequirement,
        environment: Environment,
        dest_environment: Environment,
        *,
        overwrite: bool = False,
    ):
        """Copy existing Resource to a destination Environment. Grants ownership to new resource.

        If resource exists in destination environment, `overwrite` determines if the resource copy should be overwritten or raise an exception.

        :raises ResourceNotFound: Resource could not be found to copy.
        :raises ResourceAlreadyExists: Resource already exists in destination environment.
        :raises ResourceProviderException: Resource could not be copied.
        """
        ...

    def destroy_resource(
        self,
        artifact: ArtifactReference,
        resource_requirement: ResourceRequirement,
        environment: Environment,
        *,
        force: bool = False,
    ):
        """Destroys an existing resource.

        Resource can be destroyed while it is `PROVISIONING`, `AVAILABLE`, or `UNHEALTHY`.

        :raises ResourceNotFound: Resource could not be found to destroy.
        :raises ResourceHasDependencies: Resource has dependencies and can not be destroyed."""
        ...

    def get_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> ResourceAccess | None:
        """Get artifact's access level to resource."""
        ...

    def add_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        """Add artifact access to resource."""
        ...

    def remove_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        """Remove artifact access to resource."""
        ...
