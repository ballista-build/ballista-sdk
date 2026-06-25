from collections.abc import Iterable
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

    async def get_status(self, environment: Environment) -> ResourceProviderStatus:
        """Get the status of the ResourceProvider itself."""
        ...

    async def list_resources(self, artifact: ArtifactReference, environment: Environment) -> Iterable:
        """List the Resources for an artifact."""
        ...

    async def get_resource_status(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> ResourceStatus:
        """Get the status of a specific Resource."""
        ...

    async def provision_resource(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        """Provisions a new resource. Grants ownership access to the referenced Artifact + Environment.

        :raises ResourceAlreadyExists: Resource already exists and can't be provisioned.
        :raises ResourceProviderException: Resource could not be provisioned.
        """
        ...

    async def update_resource(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        """Updates an existing resource. If the requirement changes are substantial, triggers a re-provisioning.

        Resource can be updated while it is `PROVISIONING`, `AVAILABLE`, or `UNHEALTHY`.

        :raises ResourceNotFound: Resource could not be found to update.
        :raises ResourceProviderException: Resource could not be updated."""
        ...

    async def triggers_reprovision(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> bool:
        """Returns if a resource requirement update would trigger a reprovision."""
        ...

    async def backup_resource(self):
        pass

    async def restore_resource(self):
        pass

    async def copy_resource(
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

    async def destroy_resource(
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

    async def get_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> ResourceAccess | None:
        """Get artifact's access level to resource. If no access, returns `None`.

        :raises ResourceNotFound: Resource could not be found to check access.
        """
        ...

    async def grant_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        """Grant artifact access to resource.

        :raises ResourceNotFound: Resource could not be found to grant access."""
        ...

    async def revoke_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        """Revoke artifact access to resource.

        :raises ResourceNotFound: Resource could not be found to revoke access."""
        ...
