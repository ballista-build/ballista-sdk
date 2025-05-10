from __future__ import annotations

from typing import Collection, Protocol

from ballista.types import ArtifactType, Bolt, ExecutableArtifact, PlatformResource


class ExecutionEnvironment(Protocol):
    """An environment that can execute artifacts."""

    hostname: str
    """Name of the environment host. Typically used for cluster name, server name, etc."""
    id: str
    """Unique identifier."""
    name: str
    """Human-readable name of environment."""


class ExecutionEnvironmentAdapter(Protocol):
    """Environment that can execute artifacts."""

    def deploy(
        self,
        bolt: Bolt,
        artifacts: Collection[ExecutableArtifact],
        environment: ExecutionEnvironment,
    ):
        """Deploy a Bolt and collection of ExecutableArtifacts in the specified ExecutionEnvironment."""
        ...

    def fulfill_platform_resource_dependency(self, environment: ExecutionEnvironment, artifact: ExecutableArtifact):
        """Fulfills an artifact's dependency on a Platform Resource."""
        ...

    def list_artifact_types(self, environment: ExecutionEnvironment) -> Collection[ArtifactType]:
        """List executable ArtifactTypes available in environment."""
        ...

    def list_platform_resources(self, environment: ExecutionEnvironment) -> Collection[PlatformResource]:
        """List platform resources."""
        ...

    def list_services(self, environment: ExecutionEnvironment) -> Collection[ExecutableArtifact]:
        """List deployed executable services."""
        ...


ExecutionEnvironmentWithAdapter = tuple[ExecutionEnvironmentAdapter, ExecutionEnvironment]
