from __future__ import annotations

from typing import Collection, Protocol

from ballista.types import BallistaArtifactType, BallistaBolt, BallistaExecutableArtifact, BallistaPlatformResource


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
        bolt: BallistaBolt,
        artifacts: Collection[BallistaExecutableArtifact],
        environment: ExecutionEnvironment,
    ):
        """Deploy a Bolt."""
        ...

    def fulfill_platform_resource_dependency(
        self, environment: ExecutionEnvironment, artifact: BallistaExecutableArtifact
    ):
        """Fulfills an artifact's dependency on a Platform Resource."""
        ...

    def list_artifact_types(self, environment: ExecutionEnvironment) -> Collection[BallistaArtifactType]:
        """List executable ArtifactTypes."""
        ...

    def list_platform_resources(self, environment: ExecutionEnvironment) -> Collection[BallistaPlatformResource]:
        """List platform resources."""
        ...

    def list_services(self, environment: ExecutionEnvironment) -> Collection[BallistaExecutableArtifact]:
        """List deployed executable services."""
        ...


ExecutionEnvironmentWithAdapter = tuple[ExecutionEnvironmentAdapter, ExecutionEnvironment]
