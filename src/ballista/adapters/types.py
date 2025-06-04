from __future__ import annotations

from typing import Collection, Protocol

from ballista.types import (
    ArtifactType,
    Bolt,
    Environment,
    EnvironmentArtifactExecutionParameters,
    ExecutableArtifact,
    Resource,
)


class EnvironmentExecutionAdapter(Protocol):
    """Adapter for executing artifacts in an environment."""

    def deploy(
        self,
        bolt: Bolt,
        artifacts: Collection[ExecutableArtifact],
        environment: Environment,
        execution_parameters: EnvironmentArtifactExecutionParameters,
    ):
        """Deploy a Bolt and collection of ExecutableArtifacts in the specified Environment with ArtifactExecutionParameters."""
        ...

    def fulfill_platform_resource_dependency(self, environment: Environment, artifact: ExecutableArtifact):
        """Fulfills an artifact's dependency on a Platform Resource."""
        ...

    def list_artifact_types(self, environment: Environment) -> Collection[ArtifactType]:
        """List executable ArtifactTypes available in environment."""
        ...

    def list_platform_resources(self, environment: Environment) -> Collection[Resource]:
        """List platform resources."""
        ...

    def list_services(self, environment: Environment) -> Collection[ExecutableArtifact]:
        """List deployed executable services."""
        ...


EnvironmentWithExecutionAdapter = tuple[EnvironmentExecutionAdapter, Environment]
