from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class BallistaArtifactLocalResourceNeeds(Protocol):
    max_cpu_cores: float | int | None
    max_memory_mb: int | None
    min_cpu_cores: float | int | None
    min_memory_mb: int | None


class BallistaPlatformResource(Protocol):
    pass


class BallistaArtifactExecution(Protocol):
    @property
    def local_resources(self) -> BallistaArtifactLocalResourceNeeds | None: ...

    @property
    def platform_resources(self) -> Sequence[Mapping[str, Any]] | None: ...


class BallistaArtifactType(Protocol):
    name: str
    key: str


class BallistaArtifact(Protocol):
    dockerfile: str | None
    dockerfile_stage: str | None

    @property
    def execution(self) -> BallistaArtifactExecution | None: ...

    name: str
    type: dict[str, Any]


class BallistaProject(Protocol):
    key: str
    name: str


class BallistaBolt(Protocol):
    api_version: str

    @property
    def artifacts(self) -> Sequence[BallistaArtifact]: ...

    project: str
    version: str

    def to_dict(self) -> dict[str, Any]:
        """Get Bolt data in dictionary form."""
        ...


class BoltService(Protocol):
    def create_bolt(self, project: str) -> BallistaBolt:
        """Create a new project with an empty Bolt."""
        ...

    def get_bolt(self, bolt_data: dict[str, Any]) -> BallistaBolt:
        """Get a validated Bolt from bolt_data."""
        ...
