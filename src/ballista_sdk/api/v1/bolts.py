from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .artifacts import Artifact
from .common import BaseNamedModel


class Bolt(BaseModel, frozen=True):
    """A deployable bundle of artifact definitions."""

    # TODO: Fix the versioning thing
    api_version: Annotated[
        Literal["v1"], Field(description="API version the Bolt is adhering to.", title="API Version")
    ] = "v1"
    artifacts: Annotated[list[Artifact], Field(description="List of artifacts.")]
    project: Annotated[str, Field(description="Project name.")]
    version: Annotated[
        str,
        Field(
            description="Version of Bolt. When not provided, required to be given before artifacts can be built or executed."
        ),
    ]


class Project(BaseNamedModel, frozen=True):
    pass
