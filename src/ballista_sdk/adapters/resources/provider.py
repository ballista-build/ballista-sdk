from collections.abc import Iterable
from typing import Protocol

from ballista_sdk.adapters.primitives import ArtifactReference
from ballista_sdk.api.v1 import (
    Environment,
    ResourceAccess,
    ResourceProviderStatus,
    ResourceRequirement,
    ResourceStatus,
    SettingValue,
)


class ResourceProvider[ResourceProviderResourceRequirement: ResourceRequirement](Protocol):
    """ResourceProvider interface.

    Resources provided by Python code should use this. A ResourceProviderTransport will communicate with it."""

    async def get_status(self, environment: Environment) -> tuple[ResourceProviderStatus, str | None]:
        """Get the status and optional explanation of the ResourceProvider itself."""
        ...

    async def list_resources(self, environment: Environment, artifact: ArtifactReference) -> Iterable:
        """List the Resources for an artifact."""
        ...

    async def get_resource_status(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource_requirement: ResourceProviderResourceRequirement,
    ) -> tuple[ResourceStatus, str | None]:
        """Get the status and optional explanation of a specific Resource."""
        ...

    async def provision_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource_requirement: ResourceProviderResourceRequirement,
    ) -> tuple[dict[str, SettingValue], dict[str, SettingValue]]:
        """Provisions a new resource. Grants ownership access to the referenced Artifact + Environment.

        Data returned is saved as Configs and Secrets.

        :raises ArtifactResourceAlreadyExists: Resource already exists and can't be provisioned.
        :raises ResourceProviderException: Resource could not be provisioned.
        """
        ...

    async def update_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource_requirement: ResourceProviderResourceRequirement,
    ) -> tuple[dict[str, SettingValue], dict[str, SettingValue]]:
        """Updates an existing resource. If the requirement changes are substantial, triggers a re-provisioning.

        Resource can be updated while it is `PROVISIONING`, `AVAILABLE`, or `UNHEALTHY`.

        :raises ArtifactResourceNotFound: Resource could not be found to update.
        :raises ResourceProviderException: Resource could not be updated."""
        ...

    async def triggers_reprovision(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource_requirement: ResourceProviderResourceRequirement,
    ) -> bool:
        """Returns if a resource requirement update would trigger a reprovision."""
        ...

    async def backup_resource(self):
        pass

    async def restore_resource(self):
        pass

    async def copy_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource_requirement: ResourceProviderResourceRequirement,
        dest_environment: Environment,
        *,
        overwrite: bool = False,
    ):
        """Copy existing Resource to a destination Environment. Grants ownership to new resource.

        If resource exists in destination environment, `overwrite` determines if the resource copy should be overwritten or raise an exception.

        :raises ArtifactResourceNotFound: Resource could not be found to copy.
        :raises ArtifactResourceAlreadyExists: Resource already exists in destination environment.
        :raises ResourceProviderException: Resource could not be copied.
        """
        ...

    async def destroy_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource_requirement: ResourceProviderResourceRequirement,
        *,
        force: bool = False,
    ):
        """Destroys an existing resource.

        Resource can be destroyed while it is `PROVISIONING`, `AVAILABLE`, or `UNHEALTHY`.

        :raises ArtifactResourceNotFound: Resource could not be found to destroy.
        :raises ResourceHasDependencies: Resource has dependencies and can not be destroyed."""
        ...

    async def get_resource_access(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource_requirement: ResourceProviderResourceRequirement,
    ) -> ResourceAccess:
        """Get artifact's access level to resource. If no access, returns `None`.

        :raises ResourceNotFound: Resource could not be found to check access.
        """
        ...

    async def grant_resource_access(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource_requirement: ResourceProviderResourceRequirement,
    ):
        """Grant artifact access to resource.

        :raises ResourceNotFound: Resource could not be found to grant access."""
        ...

    async def revoke_resource_access(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource_requirement: ResourceProviderResourceRequirement,
    ):
        """Revoke artifact access to resource.

        :raises ResourceNotFound: Resource could not be found to revoke access."""
        ...
