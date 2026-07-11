from abc import ABC
from typing import Annotated

from pydantic import BaseModel, Field


class ExecAction(BaseModel, frozen=True):
    """Action that executes commands inside a container."""

    commands: Annotated[list[str], Field(description="List of commands executed.")]
    shell: Annotated[bool, Field(description="Indicates commands need to be ran as a shell command.")] = False


class BasePortAction(BaseModel, ABC, frozen=True):
    service: Annotated[
        str, Field(description="Unique identifier of service instead of a numbered port.", title="Service Name")
    ]


class GRPCAction(BasePortAction):
    """Action that uses a GRPC service and method."""

    pass


class HTTPGETAction(BasePortAction):
    """Action that uses an HTTP GET request."""

    path: Annotated[str, Field(description="HTTP path.")]


class TCPAction(BasePortAction):
    """Action that uses a TCP socket connection."""

    pass
