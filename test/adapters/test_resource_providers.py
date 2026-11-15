from dataclasses import dataclass, field

import pytest

from ballista_sdk.adapters import ResourceProvider
from ballista_sdk.adapters.exceptions import ResourceAlreadyExists, ResourceNotFound
from ballista_sdk.adapters.infrastructure import ArtifactReference
from ballista_sdk.adapters.primitives import ProvidedResourceReference
from ballista_sdk.api.v1 import (
    Environment,
    ResourceAccess,
    ResourceInstance,
    ResourceProviderStatus,
    ResourceStatus,
    SettingValue,
)

pytestmark = pytest.mark.unit


_VALID_RESOURCE_ACCESS = {ResourceAccess.READ, ResourceAccess.WRITE, ResourceAccess.OWNER}
_DESTROYABLE_STATUS = {ResourceStatus.PROVISIONING, ResourceStatus.AVAILABLE, ResourceStatus.UNHEALTHY}


@dataclass
class MockResourceProvider(ResourceProvider):
    project_name: str
    resource_name: str

    _resources: dict[tuple[str, str, str], tuple[ResourceStatus, ResourceAccess]] = field(
        default_factory=dict, init=False
    )

    def _get_key(
        self, environment: Environment, artifact: ArtifactReference, resource: ResourceInstance
    ) -> tuple[str, str, str]:
        return environment.name, artifact.project_name, artifact.artifact_name

    async def get_status(self, environment: Environment) -> tuple[ResourceProviderStatus, str | None]:
        return ResourceProviderStatus.AVAILABLE, None

    async def get_resource_status(
        self, environment: Environment, artifact: ArtifactReference, resource: ResourceInstance
    ) -> tuple[ResourceStatus, ResourceAccess, str | None]:
        key = self._get_key(environment, artifact, resource)

        status, access = self._resources.get(key, (ResourceStatus.NOT_FOUND, ResourceAccess.NONE))
        return status, access, None

    async def list_resources(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        *,
        page_number: int,
        page_size: int,
        resource: ResourceInstance | None = None,
        minimum_access: ResourceAccess = ResourceAccess.NONE,
    ):
        for (environment_name, artifact_project_name, artifact_name), (status, access) in self._resources.items():
            if (
                environment_name == environment.name
                and artifact_project_name == artifact.project_name
                and artifact_name == artifact.artifact_name
            ):
                yield ResourceInstance(), status, access, None

    async def provision_resource(
        self, environment: Environment, artifact: ArtifactReference, resource: ResourceInstance
    ) -> tuple[ResourceAccess, dict[str, SettingValue], dict[str, SettingValue]]:
        key = self._get_key(environment, artifact, resource)
        if key in self._resources:
            raise ResourceAlreadyExists(ProvidedResourceReference(self.project_name, self.resource_name), resource)

        access = ResourceAccess.OWNER
        self._resources[key] = (ResourceStatus.PROVISIONING, access)

        return access, {}, {}

    async def update_resource(
        self, environment: Environment, artifact: ArtifactReference, resource: ResourceInstance
    ) -> tuple[ResourceAccess, dict[str, SettingValue], dict[str, SettingValue]]:
        key = self._get_key(environment, artifact, resource)

        if found_resource := self._resources.get(key):
            return found_resource[1], {}, {}

        raise ResourceNotFound(ProvidedResourceReference(self.project_name, self.resource_name), resource)

    async def triggers_reprovision(
        self, environment: Environment, artifact: ArtifactReference, resource: ResourceInstance
    ) -> bool:
        return False

    async def destroy_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource: ResourceInstance,
        *,
        force: bool = False,
    ):
        key = self._get_key(environment, artifact, resource)
        if not (found_resource := self._resources.get(key)):
            raise ResourceNotFound(ProvidedResourceReference(self.project_name, self.resource_name), resource)

        status, access = found_resource
        if status not in _DESTROYABLE_STATUS:
            raise ValueError()

        self._resources[key] = (ResourceStatus.DESTROYING, access)

    def _shim_finish_provision(
        self, environment: Environment, artifact_reference: ArtifactReference, resource: ResourceInstance
    ):
        key = self._get_key(environment, artifact_reference, resource)
        if not (found_resource := self._resources.get(key)):
            return

        status, access = found_resource
        if status == ResourceStatus.PROVISIONING:
            self._resources[key] = (ResourceStatus.AVAILABLE, access)

    def _shim_finish_destroy(
        self, environment: Environment, artifact_reference: ArtifactReference, resource: ResourceInstance
    ):
        key = self._get_key(environment, artifact_reference, resource)
        if not (found_resource := self._resources.get(key)):
            return

        if found_resource[0] == ResourceStatus.DESTROYING:
            del self._resources[key]


@pytest.fixture(scope="session")
def resource() -> ResourceInstance:
    return ResourceInstance.model_validate({})


@pytest.fixture
def test_resource_provider() -> ResourceProvider[ResourceInstance]:
    return MockResourceProvider("mock", "resource")


async def test_resource_provision(
    artifact_reference: ArtifactReference,
    resource: ResourceInstance,
    environment: Environment,
    test_resource_provider: MockResourceProvider,
):
    # Doesn't exist yet; status should be NOT_FOUND and access should be NONE
    status, access, message = await test_resource_provider.get_resource_status(
        environment, artifact_reference, resource
    )
    assert status == ResourceStatus.NOT_FOUND, "Resource status before provision should be NOT_FOUND"
    assert access == ResourceAccess.NONE, "Resource access before provision should be NONE"

    # Should not appear in the list of resources for an Artifact
    resources = test_resource_provider.list_resources(environment, artifact_reference, page_number=1, page_size=10)
    async for entry in resources:
        assert False

    # Provision resource
    provisioned_access, _, _ = await test_resource_provider.provision_resource(
        environment, artifact_reference, resource
    )
    assert provisioned_access in _VALID_RESOURCE_ACCESS, "Provisioned resource access should not be NONE"

    # Resource status should be PROVISIONING and access should not be NONE
    status, access, message = await test_resource_provider.get_resource_status(
        environment, artifact_reference, resource
    )
    assert status == ResourceStatus.PROVISIONING, "Resource status immediately after provision should be PROVISIONING"
    assert access in _VALID_RESOURCE_ACCESS, "Resource access immediately after provision should not be NONE"
    assert access == provisioned_access, "Resource accesss immediately after provision should match provisioned access"

    # sneaky; finish provisioning
    # TODO: This shouldn't be needed because this test should properly async calls to check statuses
    test_resource_provider._shim_finish_provision(environment, artifact_reference, resource)

    # Resource status should be AVAILABLE
    status, access, status_message = await test_resource_provider.get_resource_status(
        environment, artifact_reference, resource
    )
    assert status == ResourceStatus.AVAILABLE, "Resource status after provision not AVAILABLE"
    assert access in _VALID_RESOURCE_ACCESS, "Resource status after provision is NONE"
    assert access == provisioned_access, "Resource status after provision doesn't match provisioned access"

    # Resource should be in the list once
    resources = test_resource_provider.list_resources(
        environment, artifact_reference, page_number=1, page_size=10, resource=resource
    )
    list_match_count = len([r async for r in resources])
    assert list_match_count < 2, "Resource listed more than once"
    assert list_match_count > 0, "Resource not listed"

    # Attempting to provision again errors
    with pytest.raises(ResourceAlreadyExists):
        await test_resource_provider.provision_resource(environment, artifact_reference, resource)


async def test_list_resources(
    artifact_reference: ArtifactReference,
    resource: ResourceInstance,
    environment: Environment,
    test_resource_provider: MockResourceProvider,
):
    resources = test_resource_provider.list_resources(environment, artifact_reference, page_number=1, page_size=10)
    orig_list_count = len([r async for r in resources])

    await test_resource_provider.provision_resource(environment, artifact_reference, resource)
    resources = test_resource_provider.list_resources(environment, artifact_reference, page_number=1, page_size=10)
    assert len([r async for r in resources]) > orig_list_count, "Resource not in list after provision"


async def test_resource_update(
    artifact_reference: ArtifactReference,
    resource: ResourceInstance,
    environment: Environment,
    test_resource_provider: MockResourceProvider,
):
    # Doesn't exist, can't update
    with pytest.raises(ResourceNotFound):
        await test_resource_provider.update_resource(environment, artifact_reference, resource)

    await test_resource_provider.provision_resource(environment, artifact_reference, resource)
    test_resource_provider._shim_finish_provision(environment, artifact_reference, resource)

    await test_resource_provider.update_resource(environment, artifact_reference, resource)


async def test_resource_destroy(
    artifact_reference: ArtifactReference,
    resource: ResourceInstance,
    environment: Environment,
    test_resource_provider: MockResourceProvider,
):
    with pytest.raises(ResourceNotFound):
        await test_resource_provider.destroy_resource(environment, artifact_reference, resource)

    provisioned_access, _, _ = await test_resource_provider.provision_resource(
        environment, artifact_reference, resource
    )
    await test_resource_provider.destroy_resource(environment, artifact_reference, resource)

    # While resource is being destroyed, status should be DESTROYING and access should not be NONE
    status, access, message = await test_resource_provider.get_resource_status(
        environment, artifact_reference, resource
    )
    assert status == ResourceStatus.DESTROYING, "Resource status immediately after destroy should be DESTROYING"
    assert access in _VALID_RESOURCE_ACCESS, "Resource access immediately after destroy should not be NONE"
    assert access == provisioned_access, "Resource access immediately after destroy should match provisioned access"

    # sneaky; finish destroying
    test_resource_provider._shim_finish_destroy(environment, artifact_reference, resource)

    # After destruction, status should be NOT_FOUND and access should be NONE
    status, access, status_message = await test_resource_provider.get_resource_status(
        environment, artifact_reference, resource
    )
    assert status == ResourceStatus.NOT_FOUND, "Resource status after destroy should be NOT_FOUND"
    assert access == ResourceAccess.NONE, "Resource access after destroy should be NONE"

    resource_list = test_resource_provider.list_resources(environment, artifact_reference, page_number=1, page_size=10)
    async for list_resource, _, _, _ in resource_list:
        assert list_resource != resource


def test_transport_resource_provider():
    pass
