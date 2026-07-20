from abc import ABC
from typing import Annotated

from pydantic import BaseModel, Field

from .common import BaseOneOfModel


class ExecHealthCheckAction(BaseModel, frozen=True):
    """Action that executes commands inside a container."""

    commands: Annotated[list[str], Field(description="List of commands executed.")]
    shell: Annotated[bool, Field(description="Indicates commands need to be ran as a shell command.")] = False


class _BasePortAction(BaseOneOfModel, ABC, frozen=True):
    port: Annotated[int | None, Field()] = None
    service: Annotated[
        str | None, Field(description="Unique identifier of service instead of a numbered port.", title="Service Name")
    ] = None


class GRPCHealthCheckAction(_BasePortAction):
    """Healthcheck action that uses the GRPC Health Checking v1 Protocol."""

    pass


class HTTPHealthCheckAction(_BasePortAction):
    """Healthcheck action that uses an HTTP GET request."""

    path: Annotated[str, Field(description="HTTP path.")]


class TCPHealthCheckAction(_BasePortAction):
    """Healthcheck action that uses a TCP socket connection."""

    pass


class HealthcheckProbe(BaseOneOfModel):
    exec: Annotated[ExecHealthCheckAction | None, Field()] = None
    grpc: Annotated[GRPCHealthCheckAction | None, Field()] = None
    http: Annotated[HTTPHealthCheckAction | None, Field()] = None
    tcp: Annotated[TCPHealthCheckAction | None, Field()] = None


class ProvidedHealthchecks(BaseModel):
    """Healthchecks that are provided by an Artifact."""

    alive: HealthcheckProbe | None = None
    ready: HealthcheckProbe | None = None
    started: HealthcheckProbe | None = None
