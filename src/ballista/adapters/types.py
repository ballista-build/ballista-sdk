from __future__ import annotations

from typing import Collection, Protocol

from ballista.types import ArtifactType, BaseSetting, Bolt, ExecutableArtifact, ExecutionEnvironment, PlatformResource


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


class SettingsAdapter(Protocol):
    def create_setting(self, bolt: Bolt, artifact: ExecutableArtifact, setting: BaseSetting): ...

    def does_setting_exist(self, bolt: Bolt, artifact: ExecutableArtifact, setting: BaseSetting) -> bool: ...

    def update_setting(self): ...


class ConfigsAdapter(SettingsAdapter, Protocol):
    pass


class SecretsAdapter(SettingsAdapter, Protocol):
    pass


# TODO: This should probably be something better than a tuple
ExecutionEnvironmentWithAdapter = tuple[
    ExecutionEnvironment, ExecutionEnvironmentAdapter, ConfigsAdapter, SecretsAdapter
]
"""An ExecutionEnvironment bundled with the needed adapters."""
