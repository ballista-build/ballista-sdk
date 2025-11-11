from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from unittest.mock import Mock

from ballista_sdk.types import (
    ArtifactExecutionResourceDependency,
    ArtifactReference,
    ArtifactType,
    Bolt,
    Environment,
    ExecutableArtifact,
    ExecutionParameters,
    ResourceWithProviderArtifact,
    Setting,
    SettingValue,
    SpecificArtifact,
)


class EnvironmentExecutionAdapter(Protocol):
    """Adapter for executing artifacts in an environment."""

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
        """Deploy a Bolt and sequence of ExecutableArtifacts in the specified Environment with ArtifactExecutionParameters."""
        ...

    def get_artifact_from_reference(
        self, artifact_reference: ArtifactReference, environment: Environment
    ) -> SpecificArtifact:
        """Get a specific Artifact version in a project in the specified Environment."""
        ...

    def list_artifact_types(self, environment: Environment) -> Sequence[ArtifactType]:
        """List available ArtifactTypes in the specified Environment."""
        ...

    def list_executable_artifacts(self, environment: Environment) -> Sequence[ArtifactReference]:
        """List ExecutableArtifacts in the specified Environment."""
        ...

    def list_project_bolts(self, project_id: str) -> Sequence[Bolt]:
        """List Bolts associated with a Project."""
        ...

    def list_resources(self, environment: Environment) -> Sequence[ResourceWithProviderArtifact]:
        """List available Resources with the providing ArtifactReference in the specified Environment."""
        ...

    def resolve_resource_dependency(
        self, resource_dependency: ArtifactExecutionResourceDependency, environment: Environment
    ) -> ResourceWithProviderArtifact:
        """Resolves a dependency for a resource in the specified Environment, returning a Resource with the providing ArtifactReference. Raises exception if dependency cannot be met."""
        ...

    def teardown(
        self,
        bolt: Bolt,
        artifacts: Sequence[ExecutableArtifact],
        environment: Environment,
        execution_parameters: ExecutionParameters,
    ):
        """Teardown a running Bolt and sequence of ExecutableArtifacts in the specified Environment with ArtifactExecutionParameters."""
        ...


EnvironmentWithExecutionAdapter = tuple[EnvironmentExecutionAdapter, Environment]


class SettingsAdapter(Protocol):
    def delete(self, setting: Setting):
        """Delete a setting."""
        ...

    def exists(self, setting: Setting) -> bool:
        """Checks if a setting exists."""
        ...

    def read(self, setting: Setting) -> SettingValue:
        """Read the value for a setting."""
        ...

    def write(self, setting: Setting, value: SettingValue):
        """Write a value for a setting."""
        ...


#
# This exists until the adapters can do this.
#
def fake_artifact_types() -> list[ArtifactType]:
    docker_type = Mock(ArtifactType, id="docker_image")
    docker_type.name = "Docker Image"

    return [docker_type]
