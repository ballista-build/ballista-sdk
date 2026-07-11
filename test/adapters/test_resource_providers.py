from dataclasses import dataclass, field

import pytest

from ballista_sdk.adapters import ResourceProvider
from ballista_sdk.adapters.resources.exceptions import ResourceAlreadyExists, ResourceNotFound
from ballista_sdk.api.v1 import (
    ArtifactReference,
    Environment,
    EnvironmentTier,
    ResourceAccess,
    ResourceProviderStatus,
    ResourceRequirement,
    ResourceStatus,
)

pytestmark = pytest.mark.unit


@dataclass
class MockResourceProvider(ResourceProvider):
    project_name: str
    resource_name: str

    _resources: dict[tuple[str, str, str], ResourceStatus] = field(default_factory=dict, init=False)

    def _get_key(self, artifact: ArtifactReference, environment: Environment) -> tuple[str, str, str]:
        return environment.name, artifact.project_name, artifact.artifact_name

    async def get_status(self, environment: Environment) -> tuple[ResourceProviderStatus, str | None]:
        return ResourceProviderStatus.AVAILABLE, None

    async def get_resource_status(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ) -> tuple[ResourceStatus, str | None]:
        key = self._get_key(artifact, environment)

        return self._resources.get(key, ResourceStatus.NOT_FOUND), None

    async def provision_resource(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ):
        key = self._get_key(artifact, environment)

        if key in self._resources:
            raise ResourceAlreadyExists(
                self.project_name, self.resource_name, artifact.project_name, artifact.artifact_name, artifact.version
            )

        self._resources[key] = ResourceStatus.PROVISIONING

    async def update_resource(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ):
        key = self._get_key(artifact, environment)

        if key not in self._resources:
            raise ResourceNotFound(
                self.project_name, self.resource_name, artifact.project_name, artifact.artifact_name, artifact.version
            )

    async def triggers_reprovision(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ) -> bool:
        return False

    async def destroy_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource_requirement: ResourceRequirement,
        *,
        force: bool = False,
    ):
        key = self._get_key(artifact, environment)

        if key not in self._resources:
            raise ResourceNotFound(
                self.project_name, self.resource_name, artifact.project_name, artifact.artifact_name, artifact.version
            )

        self._resources[key] = ResourceStatus.DESTROYING

    async def copy_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource_requirement: ResourceRequirement,
        dest_environment: Environment,
        *,
        overwrite: bool = False,
    ):
        key = self._get_key(artifact, environment)

        if key not in self._resources:
            raise ResourceNotFound(
                self.project_name, self.resource_name, artifact.project_name, artifact.artifact_name, artifact.version
            )

        new_key = self._get_key(artifact, dest_environment)

        if new_key in self._resources and not overwrite:
            raise ResourceAlreadyExists(
                self.project_name, self.resource_name, artifact.project_name, artifact.artifact_name, artifact.version
            )

        self._resources[new_key] = ResourceStatus.PROVISIONING

    # Resource Access
    async def get_resource_access(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ) -> ResourceAccess | None:
        pass

    async def grant_resource_access(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ):
        pass

    async def revoke_resource_access(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ):
        pass

    def _shim_finish_provision(
        self, environment: Environment, artifact_reference: ArtifactReference, resource_requirement: ResourceRequirement
    ):
        key = self._get_key(artifact_reference, environment)

        if key in self._resources and self._resources[key] == ResourceStatus.PROVISIONING:
            self._resources[key] = ResourceStatus.AVAILABLE

    def _shim_finish_destroy(
        self, environment: Environment, artifact_reference: ArtifactReference, resource_requirement: ResourceRequirement
    ):
        key = self._get_key(artifact_reference, environment)

        if key in self._resources and self._resources[key] == ResourceStatus.DESTROYING:
            del self._resources[key]


@pytest.fixture(scope="session")
def resource_requirement() -> ResourceRequirement:
    return ResourceRequirement()


@pytest.fixture
def test_resource_provider() -> ResourceProvider:
    return MockResourceProvider("mock", "resource")


async def test_resource_provision(
    artifact_reference: ArtifactReference,
    resource_requirement: ResourceRequirement,
    environment: Environment,
    test_resource_provider: MockResourceProvider,
):
    # Doesn't exist yet; should return NOT_FOUND.
    status, message = await test_resource_provider.get_resource_status(
        environment, artifact_reference, resource_requirement
    )
    assert status == ResourceStatus.NOT_FOUND

    # Provision resource and wait for status changes
    await test_resource_provider.provision_resource(environment, artifact_reference, resource_requirement)

    # Resource should report as PROVISIONING immediately
    status, message = await test_resource_provider.get_resource_status(
        environment, artifact_reference, resource_requirement
    )
    assert status == ResourceStatus.PROVISIONING

    # sneaky; finish provisioning
    # TODO: This shouldn't be needed because this test should properly async calls to check statuses
    test_resource_provider._shim_finish_provision(environment, artifact_reference, resource_requirement)

    status, message = await test_resource_provider.get_resource_status(
        environment, artifact_reference, resource_requirement
    )
    assert status == ResourceStatus.AVAILABLE

    # Attempting to provision again errors
    with pytest.raises(ResourceAlreadyExists):
        await test_resource_provider.provision_resource(environment, artifact_reference, resource_requirement)


async def test_resource_update(
    artifact_reference: ArtifactReference,
    resource_requirement: ResourceRequirement,
    environment: Environment,
    test_resource_provider: MockResourceProvider,
):
    # Doesn't exist, can't update
    with pytest.raises(ResourceNotFound):
        await test_resource_provider.update_resource(environment, artifact_reference, resource_requirement)

    await test_resource_provider.provision_resource(environment, artifact_reference, resource_requirement)
    test_resource_provider._shim_finish_provision(environment, artifact_reference, resource_requirement)

    await test_resource_provider.update_resource(environment, artifact_reference, resource_requirement)


async def test_resource_copy(
    artifact_reference: ArtifactReference,
    resource_requirement: ResourceRequirement,
    environment: Environment,
    test_resource_provider: MockResourceProvider,
):
    provisioned_resource = environment, artifact_reference, resource_requirement

    dest_environment = Environment(name="other", title="Other Environment", tier=EnvironmentTier.DEVELOPMENT)
    copied_resource = dest_environment, artifact_reference, resource_requirement

    # Doesn't exist, can't copy
    with pytest.raises(ResourceNotFound):
        await test_resource_provider.copy_resource(
            environment, artifact_reference, resource_requirement, dest_environment
        )

    await test_resource_provider.provision_resource(*provisioned_resource)
    test_resource_provider._shim_finish_provision(*provisioned_resource)

    await test_resource_provider.copy_resource(*provisioned_resource, dest_environment)
    status, message = await test_resource_provider.get_resource_status(*copied_resource)
    assert status == ResourceStatus.PROVISIONING

    test_resource_provider._shim_finish_provision(*copied_resource)
    status, message = await test_resource_provider.get_resource_status(*copied_resource)
    assert status == ResourceStatus.AVAILABLE

    # Copying again without overwrite
    with pytest.raises(ResourceAlreadyExists):
        await test_resource_provider.copy_resource(*provisioned_resource, dest_environment)

    # Copying again WITH overwrite
    await test_resource_provider.copy_resource(*provisioned_resource, dest_environment, overwrite=True)
    status, message = await test_resource_provider.get_resource_status(*copied_resource)
    assert status == ResourceStatus.PROVISIONING


async def test_resource_destroy(
    artifact_reference: ArtifactReference,
    resource_requirement: ResourceRequirement,
    environment: Environment,
    test_resource_provider: MockResourceProvider,
):
    with pytest.raises(ResourceNotFound):
        await test_resource_provider.destroy_resource(environment, artifact_reference, resource_requirement)

    await test_resource_provider.provision_resource(environment, artifact_reference, resource_requirement)

    await test_resource_provider.destroy_resource(environment, artifact_reference, resource_requirement)

    status, message = await test_resource_provider.get_resource_status(
        environment, artifact_reference, resource_requirement
    )
    assert status == ResourceStatus.DESTROYING

    # sneaky; finish destroying
    test_resource_provider._shim_finish_destroy(environment, artifact_reference, resource_requirement)

    status, message = await test_resource_provider.get_resource_status(
        environment, artifact_reference, resource_requirement
    )
    assert status == ResourceStatus.NOT_FOUND


def test_transport_resource_provider():
    pass
