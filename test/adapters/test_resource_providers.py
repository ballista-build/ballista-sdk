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
    _resources: dict[tuple[str, str, str], ResourceStatus] = field(default_factory=dict, init=False)

    def _get_key(self, artifact: ArtifactReference, environment: Environment) -> tuple[str, str, str]:
        return environment.name, artifact.project_name, artifact.artifact_name

    def add_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        pass

    def remove_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        pass

    def get_status(self, environment: Environment) -> ResourceProviderStatus:
        return ResourceProviderStatus.AVAILABLE

    def get_resource_access(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> ResourceAccess | None:
        pass

    def get_resource_status(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> ResourceStatus:
        key = self._get_key(artifact, environment)

        return self._resources.get(key, ResourceStatus.NOT_FOUND)

    def provision_resource(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        key = self._get_key(artifact, environment)

        if key in self._resources:
            raise ResourceAlreadyExists()

        self._resources[key] = ResourceStatus.PROVISIONING

    def update_resource(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        key = self._get_key(artifact, environment)

        if key not in self._resources:
            raise ResourceNotFound()

    def triggers_reprovision(
        self, artifact: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ) -> bool:
        return False

    def destroy_resource(
        self,
        artifact: ArtifactReference,
        resource_requirement: ResourceRequirement,
        environment: Environment,
        *,
        force: bool = False,
    ):
        key = self._get_key(artifact, environment)

        if key not in self._resources:
            raise ResourceNotFound()

        self._resources[key] = ResourceStatus.DESTROYING

    def copy_resource(
        self,
        artifact: ArtifactReference,
        resource_requirement: ResourceRequirement,
        environment: Environment,
        dest_environment: Environment,
        *,
        overwrite: bool = False,
    ):
        key = self._get_key(artifact, environment)

        if key not in self._resources:
            raise ResourceNotFound(
                artifact,
            )

        new_key = self._get_key(artifact, dest_environment)

        if new_key in self._resources and not overwrite:
            raise ResourceAlreadyExists()

        self._resources[new_key] = ResourceStatus.PROVISIONING

    def _shim_finish_provision(
        self, artifact_reference: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        key = self._get_key(artifact_reference, environment)

        if key in self._resources and self._resources[key] == ResourceStatus.PROVISIONING:
            self._resources[key] = ResourceStatus.AVAILABLE

    def _shim_finish_destroy(
        self, artifact_reference: ArtifactReference, resource_requirement: ResourceRequirement, environment: Environment
    ):
        key = self._get_key(artifact_reference, environment)

        if key in self._resources and self._resources[key] == ResourceStatus.DESTROYING:
            del self._resources[key]


@pytest.fixture(scope="session")
def resource_requirement() -> ResourceRequirement:
    return ResourceRequirement()


@pytest.fixture
def test_resource_provider() -> ResourceProvider:
    return MockResourceProvider()


def test_resource_provision(
    artifact_reference: ArtifactReference,
    resource_requirement: ResourceRequirement,
    environment: Environment,
    test_resource_provider: MockResourceProvider,
):
    # Doesn't exist yet; should return NOT_FOUND.
    status = test_resource_provider.get_resource_status(artifact_reference, resource_requirement, environment)
    assert status == ResourceStatus.NOT_FOUND

    # Provision resource
    test_resource_provider.provision_resource(artifact_reference, resource_requirement, environment)

    # Resource should report as PROVISIONING until complete
    status = test_resource_provider.get_resource_status(artifact_reference, resource_requirement, environment)
    assert status == ResourceStatus.PROVISIONING

    # sneaky; finish provisioning
    test_resource_provider._shim_finish_provision(artifact_reference, resource_requirement, environment)

    status = test_resource_provider.get_resource_status(artifact_reference, resource_requirement, environment)
    assert status == ResourceStatus.AVAILABLE

    # Attempting to provision again errors
    with pytest.raises(ResourceAlreadyExists):
        test_resource_provider.provision_resource(artifact_reference, resource_requirement, environment)


def test_resource_update(
    artifact_reference: ArtifactReference,
    resource_requirement: ResourceRequirement,
    environment: Environment,
    test_resource_provider: MockResourceProvider,
):
    # Doesn't exist, can't update
    with pytest.raises(ResourceNotFound):
        test_resource_provider.update_resource(artifact_reference, resource_requirement, environment)

    test_resource_provider.provision_resource(artifact_reference, resource_requirement, environment)
    test_resource_provider._shim_finish_provision(artifact_reference, resource_requirement, environment)

    test_resource_provider.update_resource(artifact_reference, resource_requirement, environment)


def test_resource_copy(
    artifact_reference: ArtifactReference,
    resource_requirement: ResourceRequirement,
    environment: Environment,
    test_resource_provider: MockResourceProvider,
):
    provisioned_resource = artifact_reference, resource_requirement, environment

    dest_environment = Environment(name="other", title="Other Environment", tier=EnvironmentTier.DEVELOPMENT)
    copied_resource = artifact_reference, resource_requirement, dest_environment

    # Doesn't exist, can't copy
    with pytest.raises(ResourceNotFound):
        test_resource_provider.copy_resource(artifact_reference, resource_requirement, environment, dest_environment)

    test_resource_provider.provision_resource(*provisioned_resource)
    test_resource_provider._shim_finish_provision(*provisioned_resource)

    test_resource_provider.copy_resource(*provisioned_resource, dest_environment)
    status = test_resource_provider.get_resource_status(*copied_resource)
    assert status == ResourceStatus.PROVISIONING

    test_resource_provider._shim_finish_provision(*copied_resource)
    status = test_resource_provider.get_resource_status(*copied_resource)
    assert status == ResourceStatus.AVAILABLE

    # Copying again without overwrite
    with pytest.raises(ResourceAlreadyExists):
        test_resource_provider.copy_resource(*provisioned_resource, dest_environment)

    # Copying again WITH overwrite
    test_resource_provider.copy_resource(*provisioned_resource, dest_environment, overwrite=True)
    status = test_resource_provider.get_resource_status(*copied_resource)
    assert status == ResourceStatus.PROVISIONING


def test_resource_destroy(
    artifact_reference: ArtifactReference,
    resource_requirement: ResourceRequirement,
    environment: Environment,
    test_resource_provider: MockResourceProvider,
):
    with pytest.raises(ResourceNotFound):
        test_resource_provider.destroy_resource(artifact_reference, resource_requirement, environment)

    test_resource_provider.provision_resource(artifact_reference, resource_requirement, environment)

    test_resource_provider.destroy_resource(artifact_reference, resource_requirement, environment)

    status = test_resource_provider.get_resource_status(artifact_reference, resource_requirement, environment)
    assert status == ResourceStatus.DESTROYING

    # sneaky; finish destroying
    test_resource_provider._shim_finish_destroy(artifact_reference, resource_requirement, environment)

    status = test_resource_provider.get_resource_status(artifact_reference, resource_requirement, environment)
    assert status == ResourceStatus.NOT_FOUND
