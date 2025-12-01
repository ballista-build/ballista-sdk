from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from ballista_sdk.adapters.settings import SettingsAdapter
from ballista_sdk.api.v1 import (
    ArtifactReference,
    ArtifactType,
    Bolt,
    Environment,
    ExecutableArtifact,
    ExecutionParameters,
    Project,
    ProjectResourceRequirement,
    ResourceProviderArtifactReference,
)


class InfrastructureAdapter(Protocol):
    """Infastructure adapter for executing Artifacts in Environments."""

    @property
    def configs_adapter(self) -> SettingsAdapter: ...

    @property
    def name(self) -> str:
        """Name of the adapter."""
        ...

    @property
    def secrets_adapter(self) -> SettingsAdapter: ...

    def deploy(
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

    def list_projects(self) -> Sequence[Project]:
        """List Projects."""
        ...

    def list_project_bolts(self, project: Project) -> Sequence[Bolt]:
        """List Bolts associated with a Project."""
        ...

    def list_resources(self, environment: Environment) -> Sequence[ResourceProviderArtifactReference]:
        """List available Resources with the providing ArtifactReference in the specified Environment."""
        ...

    def resolve_resource_requirement(
        self, resource_requirement: ProjectResourceRequirement, environment: Environment
    ) -> ResourceProviderArtifactReference:
        """Resolves a requirement for a resource in the specified Environment, returning a Resource with the providing ArtifactReference. Raises exception if dependency cannot be met."""
        ...

    def teardown(
        self,
        bolt: Bolt,
        artifacts: Sequence[ExecutableArtifact],
        environment: Environment,
        execution_parameters: ExecutionParameters,
    ):
        """Teardown a running Bolt and sequence of ExecutableArtifacts in the specified Environment with ExecutionParameters."""
        ...


EnvironmentWithAdapter = tuple[Environment, InfrastructureAdapter]
