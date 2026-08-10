from collections.abc import Collection, Iterable
from typing import Protocol

from ballista_sdk.api.v1 import Artifact, ArtifactType, Bolt, Environment

from .primitives import ArtifactReference, BoltReference, ProjectReference


class BoltRepository(Protocol):
    """Stores Bolts and Artifacts."""

    @property
    def name(self) -> str:
        """Unique name of the adapter."""
        ...

    async def deploy(self, bolt: Bolt, environment: Environment):
        """Deploy a Bolt to the specified Environment.

        :raises BoltArtifactTypesUnavailable: No Artifacts had fulfilled ArtifactTypes.
        """
        ...

    async def list_artifacts(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        buildable: bool | None = None,
        executable: bool | None = None,
    ) -> Iterable[ArtifactReference]:
        """List Artifacts from the specified Environments."""
        ...

    async def list_artifact_types(self, environments: Collection[Environment]) -> Iterable[ArtifactType]:
        """List ArtifactTypes available in the specified Environments."""
        ...

    async def list_bolts(
        self, environments: Collection[Environment], *, project_names: Collection[str] | None = None
    ) -> Iterable[BoltReference]:
        """List BoltReferences from the specified Environments."""
        ...

    async def list_projects(
        self, environments: Collection[Environment], *, project_names: Collection[str] | None = None
    ) -> Iterable[ProjectReference]:
        """List ProjectReferences from the specified Environments."""
        ...

    async def remove(self, bolt: Bolt, environment: Environment):
        """Remove a Bolt from the specified Environment."""
        ...

    async def resolve_artifact_reference(
        self, environment: Environment, artifact_reference: ArtifactReference
    ) -> Artifact:
        """Resolves a reference to an Artifact in the specified Environment, returning the Artifact.

        :raises UnknownArtifact: Artifact cannot be found.
        """
        ...

    async def resolve_bolt_reference(self, environment: Environment, bolt_reference: BoltReference) -> Bolt:
        """Resolves a reference to a Bolt in the specified Environment, returning the Bolt.

        :raises UnknownBolt: Bolt cannot be found.
        """
        ...
