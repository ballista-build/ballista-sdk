from typing import Annotated, Literal, cast

from pydantic import BaseModel, Field

from .artifacts import Artifact, BuildableArtifact, ExecutableArtifact
from .common import BaseNamedModel


class Bolt(BaseModel, frozen=True):
    """A deployable bundle of artifact definitions."""

    # TODO: Fix the versioning thing
    api_version: Annotated[
        Literal["v1"], Field(description="API version the Bolt is adhering to.", title="API Version")
    ] = "v1"
    artifacts: Annotated[list[Artifact], Field(description="List of artifacts.")]
    project: Annotated[str, Field(description="Project name.")]
    # provides: Annotated[list | None, Field(description="Resources provided by Bolt that are not tied to Artifacts.")] = []
    version: Annotated[str, Field(description="Version of Bolt.")]

    @property
    def buildable_artifacts(self) -> list[BuildableArtifact]:
        return [cast(BuildableArtifact, a) for a in self.artifacts if a.build]

    @property
    def executable_artifacts(self) -> list[ExecutableArtifact]:
        return [cast(ExecutableArtifact, a) for a in self.artifacts if a.execution]


class Project(BaseNamedModel, frozen=True):
    pass
