from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from ballista_sdk.api.v1 import (
    Artifact,
    ArtifactReference,
    ArtifactType,
    Bolt,
    Environment,
    ExecutableArtifact,
    ExecutionParameters,
    Project,
    ProvidedResourceWithArtifactReference,
    ProvidedServiceWithArtifactReference,
    ResourceRequirement,
    ServiceRequirement,
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

    async def deploy(
        self,
        bolt: Bolt,
        artifacts: Sequence[ExecutableArtifact],
        environment: Environment,
        execution_parameters: ExecutionParameters,
    ):
        """Deploy a Bolt and sequence of ExecutableArtifacts in the specified Environment with ExecutionParameters."""
        ...

    def list_artifact_types(self, environment: Environment) -> Sequence[ArtifactType]:
        """List available ArtifactTypes in the specified Environment."""
        ...

    def list_executable_artifacts(self, environment: Environment) -> Sequence[ArtifactReference]:
        """List ExecutableArtifacts in the specified Environment."""
        ...

    def list_projects(self, environments: Sequence[Environment]) -> Sequence[Project]:
        """List Projects that exist in the specified Environments."""
        ...

    def list_project_bolts(self, project: Project, environments: Sequence[Environment]) -> Sequence[Bolt]:
        """List Bolts associated with a Project."""
        ...

    def list_resources(self, environment: Environment) -> Sequence[ProvidedResourceWithArtifactReference]:
        """List available Resources with the providing ArtifactReference in the specified Environment."""
        ...

    def list_services(self, environment: Environment) -> Sequence[ProvidedServiceWithArtifactReference]:
        """List Services in the specified Environment."""
        ...

    def resolve_artifact_reference(
        self, environment: Environment, artifact_reference: ArtifactReference
    ) -> tuple[Bolt, Artifact]:
        """Resolves a reference to an Artifact in the specified Environment, returning the Artifact and the Bolt it was from. Raises UnknownArtifact if it cannot be found."""
        ...

    def resolve_resource_provider_transport(
        self, environment: Environment, provided_resource_with_artifact: ProvidedResourceWithArtifactReference
    ) -> ResourceProviderTransport:
        """Resolves a Resource Provider into a ResourceProviderTransport that is accessible to the adapter."""
        ...

    def resolve_resource_requirement(
        self, environment: Environment, resource_requirement: ResourceRequirement
    ) -> ProvidedResourceWithArtifactReference:
        """Resolves a `ResourceRequirement` in the specified Environment, returning a Resource with the providing ArtifactReference. Raises UnknownResource if dependency cannot be met."""
        ...

    def resolve_service_requirement(
        self, environment: Environment, service_requirement: ServiceRequirement
    ) -> ProvidedServiceWithArtifactReference:
        """Resolves a `ServiceRequirement` in the specified `Environment`, returning a Service with the providing ArtifactReference. Raises UnknownService if dependency cannot be met."""
        ...

    async def teardown(
        self,
        bolt: Bolt,
        artifacts: Sequence[ExecutableArtifact],
        environment: Environment,
        execution_parameters: ExecutionParameters,
    ):
        """Teardown a running Bolt and sequence of ExecutableArtifacts in the specified Environment with ExecutionParameters."""
        ...


EnvironmentWithAdapter = tuple[Environment, InfrastructureAdapter]
