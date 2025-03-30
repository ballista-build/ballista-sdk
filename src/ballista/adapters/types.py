from __future__ import annotations

from dataclasses import dataclass
from typing import Collection, Mapping, Protocol

from ballista.types import BallistaArtifact, BallistaExecutableArtifact, BallistaArtifactType, BallistaPlatformResource


@dataclass
class ExecutionEnvironment:
    """An environment that can execute artifacts."""

    adapter: ExecutionEnvironmentAdapter
    """EnvironmentAdapter used for the environment."""
    hostname: str
    """Name of the environment host. Typically used for cluster name, server name, etc."""
    name: str
    """Unique name."""
    title: str
    """Human-readable name of environment."""


class ExecutionEnvironmentAdapter(Protocol):
    """Environment that can execute artifacts."""
    def deploy_artifact(self, environment: ExecutionEnvironment, artifact: BallistaExecutableArtifact): ...

    def fulfill_platform_resource_dependency(self, environment: ExecutionEnvironment, artifact: BallistaExecutableArtifact):
        """Fulfills an artifact's dependency on a Platform Resource."""
        ...

    def list_artifact_types(self, environment: ExecutionEnvironment) -> Collection[BallistaArtifactType]:
        """List executable ArtifactTypes."""
        ...

    def list_platform_resources(
        self, environment: ExecutionEnvironment
    ) -> Collection[BallistaPlatformResource]:
        """List platform resources."""
        ...

    def list_services(self, environment: ExecutionEnvironment) -> Collection[BallistaExecutableArtifact]:
        """List deployed executable services."""
        ...
