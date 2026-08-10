from __future__ import annotations

from collections.abc import Collection, Iterable
from typing import Protocol

from ballista_sdk.api.v1 import (
    Artifact,
    Bolt,
    Environment,
    ExecutionParameters,
    ResourceRequirement,
    ResourceStatus,
    ServiceRequirement,
    ServiceType,
)

from .exceptions import ArtifactNotFound, BoltNotFound, ProvidedResourceNotFound, ProvidedServiceNotFound
from .primitives import (
    ArtifactReference,
    BoltReference,
    ProjectReference,
    ProvidedResourceReference,
    ProvidedResourceWithArtifactReference,
    ProvidedServiceReference,
    ProvidedServiceWithArtifactReference,
)
from .repository import BoltRepository
from .resources.transports import ResourceProviderTransport
from .settings import SettingsAdapter


class InfrastructureAdapter(BoltRepository, Protocol):
    """Infastructure adapter for executing Artifacts in Environments.

    InfrastructureAdapters encapsulate the following capabilities:
    - Bolt repository.
    - Executing supported types of Artifacts.
    """

    @property
    def configs_adapter(self) -> SettingsAdapter:
        """Settings adapter specifically to manage Configs."""
        ...

    @property
    def secrets_adapter(self) -> SettingsAdapter:
        """Settings adapter specifically to manage Secrets."""
        ...

    async def get_execution_parameters(self, bolt: Bolt, environment: Environment) -> ExecutionParameters:
        """Returns the ExecutionParameters used when deploying a specified Bolt and Environment."""
        ...

    async def interact(self, bolt: Bolt, environment: Environment):
        """Start an interactive development session that automatically builds, deploys, and tears down the Bolt."""
        ...

    async def list_provided_resources(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        resource_names: Collection[str] | None = None,
    ) -> Iterable[ProvidedResourceWithArtifactReference]:
        """List available Resources with the providing ArtifactReference in the specified Environments."""
        ...

    async def list_provided_services(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        service_names: Collection[str] | None = None,
        service_types: Collection[ServiceType] | None = None,
    ) -> Iterable[ProvidedServiceWithArtifactReference]:
        """List Services in the specified Environments."""
        ...

    async def list_resources(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        resource_project_names: Collection[str] | None = None,
        resource_names: Collection[str] | None = None,
        resource_statuses: Collection[ResourceStatus] | None = None,
    ) -> Iterable[tuple[ArtifactReference, ProvidedResourceReference, ResourceStatus]]:
        """List Resources in-use by other Artifacts in the specified Environments."""
        ...

    async def list_services(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        service_project_names: Collection[str] | None = None,
        service_artifact_names: Collection[str] | None = None,
        service_names: Collection[str] | None = None,
        service_types: Collection[ServiceType] | None = None,
    ) -> Iterable[tuple[ArtifactReference, ProvidedServiceReference, str]]:
        """List Services in-use by other Artifacts in the specified Environments."""
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

    async def transport_resource_provider(
        self, environment: Environment, provided_resource_with_artifact: ProvidedResourceWithArtifactReference
    ) -> ResourceProviderTransport:
        """Transports a Resource Provider communication that is accessible to the adapter."""
        ...


class BoltInspector:
    """Lists and resolves against Bolts."""

    @staticmethod
    def list_artifacts(
        bolts: Iterable[Bolt],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        buildable: bool | None = None,
        executable: bool | None = None,
    ) -> list[ArtifactReference]:
        """List Artifacts in the specified Bolts."""

        return [
            ArtifactReference(
                project_name=bolt.project,
                artifact_name=artifact.name,
                version=bolt.version,
            )
            for bolt in bolts
            if not project_names or bolt.project in project_names
            for artifact in bolt.artifacts
            if (not artifact_names or artifact.name in artifact_names)
            and (buildable is None or bool(artifact.build) == buildable)
            and (executable is None or bool(artifact.execution) == executable)
        ]

    @staticmethod
    def list_bolts(bolts: Iterable[Bolt], *, project_names: Collection[str] | None = None) -> list[BoltReference]:
        """List BoltReferences in the specified Bolts."""
        return [
            BoltReference(project_name=bolt.project, version=bolt.version)
            for bolt in bolts
            if not project_names or bolt.project in project_names
        ]

    @staticmethod
    def list_projects(bolts: Iterable[Bolt], *, project_names: Collection[str] | None = None) -> list[ProjectReference]:
        return [
            ProjectReference(project_name=bolt.project)
            for bolt in bolts
            if not project_names or bolt.project in project_names
        ]

    @classmethod
    def list_provided_resources(
        cls,
        bolts: Iterable[Bolt],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        resource_names: Collection[str] | None = None,
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
            for artifact in bolt.artifacts
            if artifact.execution
            and artifact.execution.provides
            and (not artifact_names or artifact.name in artifact_names)
            for resource in artifact.execution.provides.resources
            if not resource_names or resource.name in resource_names
        ]

    @staticmethod
    def list_provided_services(
        bolts: Iterable[Bolt],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        service_names: Collection[str] | None = None,
        service_types: Collection[ServiceType] | None = None,
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
            for artifact in bolt.artifacts
            if artifact.execution
            and artifact.execution.provides
            and (not artifact_names or artifact.name in artifact_names)
            for service in artifact.execution.provides.services
            if not service_names or service.name in service_names
        ]

    @staticmethod
    def list_resources(
        bolts: Iterable[Bolt],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        resource_project_names: Collection[str] | None = None,
        resource_names: Collection[str] | None = None,
        resource_statuses: Collection[ResourceStatus] | None = None,
    ) -> list[tuple[ArtifactReference, ProvidedResourceReference, ResourceStatus]]:
        """List Resources with the providing ArtifactReference in the specified Bolts."""
        return [
            (
                ArtifactReference(project_name=bolt.project, artifact_name=artifact.name, version=bolt.version),
                ProvidedResourceReference(
                    project_name=resource_requirement.project_name,
                    resource_name=resource_requirement.resource_name,
                ),
                ResourceStatus.UNKNOWN,
            )
            for bolt in bolts
            if not project_names or bolt.project in project_names
            for artifact in bolt.artifacts
            if artifact.execution
            and artifact.execution.requires
            and (not artifact_names or artifact.name in artifact_names)
            for resource_requirement in artifact.execution.requires.resources
            if (not resource_project_names or resource_requirement.project_name in resource_project_names)
            and (not resource_names or resource_requirement.resource_name in resource_names)
        ]

    @staticmethod
    def list_services(
        bolts: Iterable[Bolt],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        service_project_names: Collection[str] | None = None,
        service_artifact_names: Collection[str] | None = None,
        service_names: Collection[str] | None = None,
        service_types: Collection[ServiceType] | None = None,
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
            for artifact in bolt.artifacts
            if artifact.execution
            and artifact.execution.requires
            and (not artifact_names or artifact.name in artifact_names)
            for service_requirement in artifact.execution.requires.services
            if (not service_project_names or service_requirement.project_name in service_project_names)
            and (not service_artifact_names or service_requirement.artifact_name in service_artifact_names)
            and (not service_names or service_requirement.service_name in service_names)
        ]

    @classmethod
    def resolve_artifact_reference(cls, bolts: Iterable[Bolt], artifact_reference: ArtifactReference) -> Artifact:
        """Resolves a reference to an Artifact in the specified Environment, returning the Artifact it was from. Raises UnknownArtifact if it cannot be found."""
        for bolt in bolts:
            if bolt.project != artifact_reference.project_name or bolt.version != artifact_reference.version:
                continue

            for artifact in bolt.artifacts:
                if artifact.name == artifact_reference.artifact_name:
                    return artifact

        raise ArtifactNotFound(artifact_reference)

    @classmethod
    def resolve_bolt_reference(cls, bolts: Iterable[Bolt], bolt_reference: BoltReference) -> Bolt:
        for bolt in bolts:
            if bolt.project == bolt_reference.project_name and bolt.version == bolt_reference.version:
                return bolt

        raise BoltNotFound(bolt_reference)

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
    adapter: InfrastructureAdapter, environment: Environment, bolt: Bolt
) -> tuple[
    dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference],
    dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference],
]:
    resource_providers: dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference] = {}
    service_providers: dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference] = {}

    for artifact in bolt.artifacts:
        if not artifact.execution:
            continue

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
