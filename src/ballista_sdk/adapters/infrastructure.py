from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from ballista_sdk.api.v1 import (
    Artifact,
    ArtifactType,
    Bolt,
    Environment,
    ExecutableArtifact,
    ExecutionParameters,
    Project,
    ResourceRequirement,
    ResourceStatus,
    ServiceRequirement,
    ServiceType,
)

from .exceptions import ArtifactNotFound, ProvidedResourceNotFound, ProvidedServiceNotFound
from .primitives import (
    ArtifactReference,
    ProvidedResourceReference,
    ProvidedResourceWithArtifactReference,
    ProvidedServiceReference,
    ProvidedServiceWithArtifactReference,
)
from .resources.transports import ResourceProviderTransport
from .settings import SettingsAdapter


class InfrastructureAdapter(Protocol):
    """Infastructure adapter for executing Artifacts in Environments."""

    @property
    def configs_adapter(self) -> SettingsAdapter:
        """Settings adapter specifically to manage Configs."""
        ...

    @property
    def name(self) -> str:
        """Unique name of the adapter."""
        ...

    @property
    def secrets_adapter(self) -> SettingsAdapter:
        """Settings adapter specifically to manage Secrets."""
        ...

    async def deploy(self, bolt: Bolt, environment: Environment):
        """Deploy a Bolt to the specified Environment."""
        ...

    async def get_execution_parameters(self, bolt: Bolt, environment: Environment) -> ExecutionParameters:
        """Returns the ExecutionParameters that is used when deploying a specified Bolt and Environment."""
        ...

    async def interact(self, bolt: Bolt, environment: Environment):
        """Start an interactive development session that automatically builds, deploys, and tears down the Bolt."""
        raise Exception("Not implemented.")

    async def list_artifact_types(self, environments: Sequence[Environment]) -> Sequence[ArtifactType]:
        """List available ArtifactTypes in the specified Environment."""
        ...

    async def list_executable_artifacts(
        self,
        environments: Sequence[Environment],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
    ) -> Sequence[ArtifactReference]:
        """List ExecutableArtifacts in the specified sequence of Environments."""
        ...

    async def list_projects(
        self, environments: Sequence[Environment], *, project_names: Sequence[str] | None = None
    ) -> Sequence[Project]:
        """List Projects that exist in the specified sequence of Environments."""
        ...

    async def list_bolts(
        self, environments: Sequence[Environment], *, project_names: Sequence[str] | None = None
    ) -> Sequence[Bolt]:
        """List Bolts in the specified sequence of Environments."""
        ...

    async def list_provided_resources(
        self,
        environments: Sequence[Environment],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        resource_names: Sequence[str] | None = None,
    ) -> Iterable[ProvidedResourceWithArtifactReference]:
        """List available Resources with the providing ArtifactReference in the specified sequence of Environments."""
        ...

    async def list_provided_services(
        self,
        environments: Sequence[Environment],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        service_names: Sequence[str] | None = None,
        service_types: Sequence[ServiceType] | None = None,
    ) -> Iterable[ProvidedServiceWithArtifactReference]:
        """List Services in the specified sequence of Environments."""
        ...

    async def list_resources(
        self,
        environments: Sequence[Environment],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        resource_names: Sequence[str] | None = None,
        resource_statuses: Sequence[ResourceStatus] | None = None,
    ) -> Iterable[tuple[ArtifactReference, ProvidedResourceReference, ResourceStatus]]:
        """List Resources in-use by other Artifacts in the specified sequence of Environments."""
        ...

    async def list_services(
        self,
        environments: Sequence[Environment],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        service_names: Sequence[str] | None = None,
        service_types: Sequence[ServiceType] | None = None,
    ) -> Iterable[tuple[ArtifactReference, ProvidedServiceReference, str]]:
        """List Services in-use by other Artifacts in the specified sequence of Environments."""
        ...

    async def resolve_artifact_reference(
        self, environment: Environment, artifact_reference: ArtifactReference
    ) -> tuple[Bolt, Artifact]:
        """Resolves a reference to an Artifact in the specified Environment, returning the Artifact and the Bolt it was from. Raises UnknownArtifact if it cannot be found."""
        ...

    async def resolve_resource_requirement(
        self, environment: Environment, resource_requirement: ResourceRequirement
    ) -> ProvidedResourceWithArtifactReference:
        """Resolves a `ResourceRequirement` fulfilled in the specified `Environment`, returning a `ProvidedResource` with an ArtifactReference. Raises UnknownResource if dependency cannot be met."""
        ...

    async def resolve_service_requirement(
        self, environment: Environment, service_requirement: ServiceRequirement
    ) -> ProvidedServiceWithArtifactReference:
        """Resolves a `ServiceRequirement` fulfilled in the specified `Environment`, returning a `ProvidedService` with an ArtifactReference. Raises UnknownService if dependency cannot be met."""
        ...

    async def teardown(self, bolt: Bolt, environment: Environment):
        """Teardown a running Bolt executing in the specified Environment."""
        ...

    async def transport_resource_provider(
        self, environment: Environment, provided_resource_with_artifact: ProvidedResourceWithArtifactReference
    ) -> ResourceProviderTransport:
        """Transports a Resource Provider communication that is accessible to the adapter."""
        ...


class BoltInspector:
    """Lists and resolves against Bolts."""

    @staticmethod
    def list_bolts(bolts: Iterable[Bolt], *, project_names: Sequence[str] | None = None) -> list[Bolt]:
        """List Bolts in the specified sequence of Bolts."""
        return [bolt for bolt in bolts if not project_names or bolt.project in project_names]

    @staticmethod
    def list_executable_artifacts(
        bolts: Iterable[Bolt],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
    ) -> list[ArtifactReference]:
        """List ExecutableArtifacts in the specified Bolts."""

        return [
            ArtifactReference(
                project_name=bolt.project,
                artifact_name=artifact.name,
                version=bolt.version,
            )
            for bolt in bolts
            if not project_names or bolt.project in project_names
            for artifact in bolt.executable_artifacts
            if not artifact_names or artifact.name in artifact_names
        ]

    @staticmethod
    def list_projects(bolts: Iterable[Bolt], *, project_names: Sequence[str] | None = None) -> list[Project]:
        return [Project(name=bolt.project) for bolt in bolts]

    @staticmethod
    def list_provided_resources(
        bolts: Iterable[Bolt],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        resource_names: Sequence[str] | None = None,
    ) -> list[ProvidedResourceWithArtifactReference]:
        """List ProvidedResources with the providing ArtifactReference in the specified Bolts."""
        return [
            ProvidedResourceWithArtifactReference(
                provided_resource=resource,
                artifact_reference=ArtifactReference(
                    project_name=bolt.project,
                    artifact_name=artifact.name,
                    version=bolt.version,
                ),
            )
            for bolt in bolts
            if not project_names or bolt.project in project_names
            for artifact in bolt.executable_artifacts
            if artifact.execution.provides and (not artifact_names or artifact.name in artifact_names)
            for resource in artifact.execution.provides.resources
            if not resource_names or resource.name in resource_names
        ]

    @staticmethod
    def list_provided_services(
        bolts: Iterable[Bolt],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        service_names: Sequence[str] | None = None,
        service_types: Sequence[ServiceType] | None = None,
    ) -> list[ProvidedServiceWithArtifactReference]:
        """List ProvidedServices with the providing ArtifactReference in the specified Bolts."""
        return [
            ProvidedServiceWithArtifactReference(
                provided_service=service,
                artifact_reference=ArtifactReference(
                    project_name=bolt.project,
                    artifact_name=artifact.name,
                    version=bolt.version,
                ),
            )
            for bolt in bolts
            if not project_names or bolt.project in project_names
            for artifact in bolt.executable_artifacts
            if artifact.execution.provides and (not artifact_names or artifact.name in artifact_names)
            for service in artifact.execution.provides.services
            if not service_names or service.name in service_names
        ]

    @staticmethod
    def list_resources(
        bolts: Iterable[Bolt],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        resource_names: Sequence[str] | None = None,
        resource_statuses: Sequence[ResourceStatus] | None = None,
    ) -> list[tuple[ArtifactReference, ProvidedResourceReference, ResourceStatus]]:
        """List ProvidedServices with the providing ArtifactReference in the specified Bolts."""
        return [
            (
                ArtifactReference(project_name=bolt.project, artifact_name=artifact.name, version=bolt.version),
                ProvidedResourceReference(
                    project_name=resource_requirement.project_name,
                    resource_name=resource_requirement.resource_name,
                ),
                ResourceStatus.AVAILABLE,
            )
            for bolt in bolts
            if not project_names or bolt.project in project_names
            for artifact in bolt.executable_artifacts
            if artifact.execution.requires and (not artifact_names or artifact.name in artifact_names)
            for resource_requirement in artifact.execution.requires.resources
            if not resource_names or resource_requirement.resource_name in resource_names
        ]

    @staticmethod
    def list_services(
        bolts: Iterable[Bolt],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        service_names: Sequence[str] | None = None,
        service_types: Sequence[ServiceType] | None = None,
    ) -> list[tuple[ArtifactReference, ProvidedServiceReference, ServiceType]]:
        """List ProvidedServices with the providing ArtifactReference in the specified Bolts."""
        return [
            (
                ArtifactReference(project_name=bolt.project, artifact_name=artifact.name, version=bolt.version),
                ProvidedServiceReference(
                    project_name=service_requirement.project_name,
                    artifact_name=service_requirement.artifact_name,
                    service_name=service_requirement.service_name,
                ),
                ServiceType.http,
            )
            for bolt in bolts
            if not project_names or bolt.project in project_names
            for artifact in bolt.executable_artifacts
            if artifact.execution.requires and (not artifact_names or artifact.name in artifact_names)
            for service_requirement in artifact.execution.requires.services
            if not service_names or service_requirement.service_name in service_names
        ]

    @classmethod
    def resolve_artifact_reference(
        cls, bolts: Iterable[Bolt], artifact_reference: ArtifactReference
    ) -> tuple[Bolt, Artifact]:
        """Resolves a reference to an Artifact in the specified Environment, returning the Artifact and the Bolt it was from. Raises UnknownArtifact if it cannot be found."""
        for bolt in bolts:
            if bolt.project != artifact_reference.project_name or bolt.version != artifact_reference.version:
                continue

            for artifact in bolt.artifacts:
                if artifact.name == artifact_reference.artifact_name:
                    return bolt, artifact

        raise ArtifactNotFound(artifact_reference)

    @classmethod
    def resolve_resource_requirement(
        cls, bolts: Iterable[Bolt], resource_requirement: ResourceRequirement
    ) -> ProvidedResourceWithArtifactReference:
        """Resolves a `ResourceRequirement` in the specified Environment, returning a Resource with the providing ArtifactReference. Raises UnknownResource if dependency cannot be met."""
        for match in cls.list_provided_resources(
            bolts,
            project_names=[resource_requirement.project_name],
            resource_names=[resource_requirement.resource_name],
        ):
            return match

        raise ProvidedResourceNotFound(
            ProvidedResourceReference(
                project_name=resource_requirement.project_name, resource_name=resource_requirement.resource_name
            )
        )

    @classmethod
    def resolve_service_requirement(
        cls, bolts: Iterable[Bolt], service_requirement: ServiceRequirement
    ) -> ProvidedServiceWithArtifactReference:
        """Resolves a `ServiceRequirement` in the specified `Environment`, returning a Service with the providing ArtifactReference. Raises UnknownService if dependency cannot be met."""
        for match in cls.list_provided_services(
            bolts,
            project_names=[service_requirement.project_name],
            artifact_names=[service_requirement.artifact_name],
            service_names=[service_requirement.service_name],
        ):
            return match

        raise ProvidedServiceNotFound(
            ProvidedServiceReference(
                project_name=service_requirement.project_name,
                artifact_name=service_requirement.artifact_name,
                service_name=service_requirement.service_name,
            )
        )


async def resolve_artifact_requirements(
    adapter: InfrastructureAdapter, environment: Environment, bolt: Bolt, artifacts: Sequence[ExecutableArtifact]
) -> tuple[
    dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference],
    dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference],
]:
    resource_providers: dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference] = {}
    service_providers: dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference] = {}

    for artifact in artifacts:
        for resource_requirement in artifact.execution.requires.resources:
            provided_resource_reference = ProvidedResourceReference(
                project_name=resource_requirement.project_name,
                resource_name=resource_requirement.resource_name,
            )

            if provided_resource_reference not in resource_providers:
                # Attempt to resolve from the Bolt first.
                try:
                    resolution = BoltInspector.resolve_resource_requirement([bolt], resource_requirement)

                except ProvidedResourceNotFound:
                    resolution = await adapter.resolve_resource_requirement(environment, resource_requirement)

                resource_providers[provided_resource_reference] = resolution

        for service_requirement in artifact.execution.requires.services:
            provided_service_reference = ProvidedServiceReference(
                project_name=service_requirement.project_name,
                artifact_name=service_requirement.artifact_name,
                service_name=service_requirement.service_name,
            )

            if provided_service_reference not in service_providers:
                # Attempt to resolve from the Bolt first.
                try:
                    resolution = BoltInspector.resolve_service_requirement([bolt], service_requirement)

                except ProvidedServiceNotFound:
                    resolution = await adapter.resolve_service_requirement(environment, service_requirement)

                service_providers[provided_service_reference] = resolution

    return resource_providers, service_providers


EnvironmentWithAdapter = tuple[Environment, InfrastructureAdapter]
