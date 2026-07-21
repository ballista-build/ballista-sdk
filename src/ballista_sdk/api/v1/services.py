from enum import StrEnum
from typing import Annotated

from pydantic import Field

from .common import BaseNamedModel


class ProvidedService(BaseNamedModel):
    """A network-connected port with unique identifier that is provided by an Artifact."""

    grpc: Annotated[int | None, Field(description="GRPC service available on specified port.")] = None
    http: Annotated[int | None, Field()] = None
    tcp: Annotated[int | None, Field()] = None


class ServiceType(StrEnum):
    grpc = "grpc"
    http = "http"
    tcp = "tcp"
