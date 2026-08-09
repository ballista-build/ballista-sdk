import pytest

from ballista_sdk.adapters import InfrastructureAdapter
from ballista_sdk.adapters.exceptions import ArtifactNotFound, ProvidedResourceNotFound, ProvidedServiceNotFound
from ballista_sdk.adapters.infrastructure import ArtifactReference, ProvidedResourceWithArtifactReference
from ballista_sdk.adapters.resources.transports import RESTResourceProviderTransport
from ballista_sdk.api.v1 import Bolt, Environment, ResourceRequirement, ServiceRequirement


async def test_transport_resource_provider(
    environment: Environment,
    infrastructure_adapter: InfrastructureAdapter,
    provided_resource_with_artifact: ProvidedResourceWithArtifactReference,
):
    transport = await infrastructure_adapter.transport_resource_provider(environment, provided_resource_with_artifact)

    assert isinstance(transport, RESTResourceProviderTransport)


async def test_resolve_artifact(
    environment: Environment, infrastructure_adapter: InfrastructureAdapter, postgres_bolt: Bolt
):
    resolved_artifact = await infrastructure_adapter.resolve_artifact_reference(
        environment, ArtifactReference(project_name="postgres", artifact_name="server", version="18.1")
    )

    assert resolved_artifact in postgres_bolt.artifacts


async def test_resolve_artifact_not_found(
    environment: Environment, infrastructure_adapter: InfrastructureAdapter, subtests: pytest.Subtests
):
    for artifact_reference in [
        ArtifactReference(project_name="other_project", artifact_name="server", version="18.1"),
        ArtifactReference(project_name="postgres", artifact_name="not_the_server", version="18.1"),
        ArtifactReference(project_name="postgres", artifact_name="server", version="18.0"),
    ]:
        with subtests.test(artifact_reference=artifact_reference), pytest.raises(ArtifactNotFound):
            await infrastructure_adapter.resolve_artifact_reference(environment, artifact_reference)


async def test_resolve_resource(environment: Environment, infrastructure_adapter: InfrastructureAdapter):
    requirement = ResourceRequirement.model_validate({"postgres": {"database": {"name": "my_database"}}})
    resolved = await infrastructure_adapter.resolve_resource_requirement(environment, requirement)

    assert resolved.provided_resource.name == "database"
    assert resolved.artifact_reference == ArtifactReference(
        project_name="postgres", artifact_name="resource-providers", version="18.1"
    )


async def test_resolve_resource_not_found(
    environment: Environment,
    infrastructure_adapter: InfrastructureAdapter,
    subtests: pytest.Subtests,
):
    for requirement in [
        ResourceRequirement.model_validate({"mysql": {"database": {"name": "my_database"}}}),
        ResourceRequirement.model_validate({"postgres": {"name": {"database": "my_name"}}}),
    ]:
        with subtests.test(requirement=requirement), pytest.raises(ProvidedResourceNotFound):
            await infrastructure_adapter.resolve_resource_requirement(environment, requirement)


async def test_resolve_service(
    environment: Environment, infrastructure_adapter: InfrastructureAdapter, subtests: pytest.Subtests
):
    requirement = ServiceRequirement.model_validate({"postgres": {"server": "postgres"}})
    resolved = await infrastructure_adapter.resolve_service_requirement(environment, requirement)

    assert resolved.provided_service.name == "postgres"
    assert resolved.artifact_reference == ArtifactReference(
        project_name="postgres", artifact_name="server", version="18.1"
    )

    for requirement in [
        ServiceRequirement.model_validate({"mysql": {"server": "postgres"}}),
        ServiceRequirement.model_validate({"postgres": {"daemon": "postgres"}}),
        ServiceRequirement.model_validate({"postgres": {"server": "mysql"}}),
    ]:
        with subtests.test(requirement=requirement), pytest.raises(ProvidedServiceNotFound):
            await infrastructure_adapter.resolve_service_requirement(environment, requirement)


async def test_resolve_service_not_found(
    environment: Environment, infrastructure_adapter: InfrastructureAdapter, subtests: pytest.Subtests
):
    for requirement in [
        ServiceRequirement.model_validate({"mysql": {"server": "postgres"}}),
        ServiceRequirement.model_validate({"postgres": {"daemon": "postgres"}}),
        ServiceRequirement.model_validate({"postgres": {"server": "mysql"}}),
    ]:
        with subtests.test(requirement=requirement), pytest.raises(ProvidedServiceNotFound):
            await infrastructure_adapter.resolve_service_requirement(environment, requirement)


async def test_list_artifacts(environment: Environment, infrastructure_adapter: InfrastructureAdapter):
    artifacts = list(await infrastructure_adapter.list_artifacts([environment]))

    assert artifacts


async def test_list_bolts(environment: Environment, infrastructure_adapter: InfrastructureAdapter):
    bolts = list(await infrastructure_adapter.list_bolts([environment]))

    assert bolts


async def test_list_projects(environment: Environment, infrastructure_adapter: InfrastructureAdapter):
    projects = list(await infrastructure_adapter.list_projects([environment], project_names=["postgres"]))

    assert projects

    for project in projects:
        assert project is not None
        assert project.project_name == "postgres"


async def test_list_provided_resources(environment: Environment, infrastructure_adapter: InfrastructureAdapter):
    provided_resources = list(
        await infrastructure_adapter.list_provided_resources([environment], project_names=["postgres"])
    )

    assert provided_resources

    for provided_resource in provided_resources:
        assert provided_resource is not None
        assert provided_resource.artifact_reference.project_name == "postgres"
        assert provided_resource.artifact_reference.artifact_name in {"server", "resource-providers"}
        assert provided_resource.artifact_reference.version == "18.1"


async def test_list_provided_services(environment: Environment, infrastructure_adapter: InfrastructureAdapter):
    provided_services = list(
        await infrastructure_adapter.list_provided_services([environment], project_names=["postgres"])
    )

    assert provided_services

    for provided_service in provided_services:
        assert provided_service is not None
        assert provided_service.artifact_reference.project_name == "postgres"
        assert provided_service.artifact_reference.artifact_name in {"server", "resource-providers"}
        assert provided_service.artifact_reference.version == "18.1"


async def test_list_services(environment: Environment, infrastructure_adapter: InfrastructureAdapter):
    services = list(await infrastructure_adapter.list_services([environment], project_names=["postgres"]))

    assert services

    for (
        artifact_reference,
        provided_service_reference,
        service_type,
    ) in services:
        assert artifact_reference and provided_service_reference and service_type
        assert artifact_reference.project_name in {"postgres"}
        assert artifact_reference.artifact_name in {"resource-providers"}
        assert artifact_reference.version == "18.1"

        assert provided_service_reference.project_name in {"postgres"}
        assert provided_service_reference.artifact_name in {"server"}
        assert provided_service_reference.service_name in {"postgres"}
