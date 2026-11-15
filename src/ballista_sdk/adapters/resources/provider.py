"""Interface for Resource Providers."""

from collections.abc import AsyncIterable
from typing import Protocol

from ballista_sdk.adapters.primitives import ArtifactReference
from ballista_sdk.api.v1 import (
    Environment,
    ResourceAccess,
    ResourceInstance,
    ResourceProviderStatus,
    ResourceStatus,
    SettingValue,
)


class ResourceProvider[R: ResourceInstance = ResourceInstance](Protocol):
    """ResourceProvider interface.

    Resources provided by Python code should use this. A ResourceProviderTransport will communicate with it.
    """

    async def get_status(self, environment: Environment) -> tuple[ResourceProviderStatus, str | None]:
        """Get the status and optional explanation of the ResourceProvider itself."""

    def list_resources(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        *,
        page_number: int,
        page_size: int,
        resource: R | None = None,
        minimum_access: ResourceAccess = ResourceAccess.NONE,
    ) -> AsyncIterable[tuple[R, ResourceStatus, ResourceAccess, str | None]]:
        """List the Resources an Artifact has access to. By default, all Resources available to the Artifact are listed.

        - Resource Instance
        - Status
        - Access
        - Status message
        """

    async def get_resource_status(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource: R,
    ) -> tuple[ResourceStatus, ResourceAccess, str | None]:
        """Get the status, access level, and optional status explanation of a specific Resource.

        Raises:
            ResourceNotFound: Resource not found.
        """

    async def provision_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource: R,
    ) -> tuple[ResourceAccess, dict[str, SettingValue], dict[str, SettingValue]]:
        """Provisions a resource for use by the specified Artifact.

        Access is expected to be `OWNER`, `WRITE`, or `READ`.

        Returns:
            A tuple containing the `ResourceAccess` granted to the artifact, a dict of configs, and a dict of secrets.

        Raises:
            ResourceAlreadyExists: Resource already exists and can't be provisioned.
            ProvidedResourceException: Resource could not be provisioned.
        """

    async def update_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource: R,
    ) -> tuple[ResourceAccess, dict[str, SettingValue], dict[str, SettingValue]]:
        """Updates an existing resource. If the requirement changes are substantial, triggers a re-provisioning. `triggers_reprovision` returns if such an update would cause a reprovision.

        Resource can be updated while it is `PROVISIONING`, `AVAILABLE`, or `UNHEALTHY`.

        Raises:
            ResourceNotFound: Resource could not be found to update.
            ProvidedResourceException: Resource could not be updated.
        """

    async def triggers_reprovision(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource: R,
    ) -> bool:
        """Returns if a resource requirement update would trigger a reprovision."""

    # TODO: These need to be implemented and defined before a true cross Environment replication is possible.
    #     async def backup_resource(self):
    #         pass
    #
    #     async def restore_resource(self):
    #         pass

    async def destroy_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource: R,
        *,
        force: bool = False,
    ):
        """Destroys an existing resource.

        Resource can be destroyed while it is `PROVISIONING`, `AVAILABLE`, or `UNHEALTHY`.

        Raises:
            ResourceNotFound: Resource could not be found to destroy.
            ResourceHasDependencies: Resource has dependencies and can not be destroyed.
        """
