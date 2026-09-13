from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field

from .common import BaseNamedModel, BaseOneOfModel


class ProvidedService(BaseNamedModel):
    """A network-connected port with unique identifier that is provided by an Artifact."""

    grpc: Annotated[int | None, Field(description="GRPC service available on specified port.")] = None
    http: Annotated[int | None, Field()] = None
    secure: Annotated[bool, Field(description="Indicates a secure connection is expected.")] = False
    tcp: Annotated[int | None, Field()] = None


class ServiceType(StrEnum):
    grpc = "grpc"
    http = "http"
    tcp = "tcp"


class VirtualProvidedService(BaseModel):
    """A static IPv4 address for a ProvidedService, pretending to be executed in an Artifact."""

    artifact: str
    ipv4_address: str
    service: ProvidedService


class ServiceRequirement(BaseOneOfModel):
    model_config = {"extra": "allow"}

    __pydantic_extra__: dict[str, dict[str, str]]
    """Project Name -> Artifact Name -> Service Name"""

    @property
    def project_name(self) -> str:
        return self.which()

    @property
    def artifact_name(self) -> str:
        if self.__pydantic_extra__:
            for f in self.__pydantic_extra__.values():
                for v in f:
                    return v

        raise Exception(self.__pydantic_extra__)

    @property
    def service_name(self) -> str:
        if self.__pydantic_extra__:
            for f in self.__pydantic_extra__.values():
                for v in f.values():
                    return v

        raise Exception(self.__pydantic_extra__)
