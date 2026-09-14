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

    __pydantic_extra__: dict[str, dict[str, dict[str, dict[str, str]] | str]]
    """Project Name -> Artifact Name -> Service Name"""

    @property
    def project_name(self) -> str:
        return self.which()

    @property
    def artifact_name(self) -> str:
        if self.__pydantic_extra__:
            for artifacts in self.__pydantic_extra__.values():
                for artifact_name in artifacts:
                    return artifact_name

        raise ValueError(self.__pydantic_extra__)

    @property
    def service_name(self) -> str:
        if self.__pydantic_extra__:
            for artifacts in self.__pydantic_extra__.values():
                for services in artifacts.values():
                    if isinstance(services, dict):
                        for service_name in services:
                            return service_name
                        raise ValueError(self.__pydantic_extra__)

                    return services

        raise ValueError(self.__pydantic_extra__)

    @property
    def service_requirement(self) -> dict[str, str]:
        if self.__pydantic_extra__:
            for artifacts in self.__pydantic_extra__.values():
                for services in artifacts.values():
                    if isinstance(services, dict):
                        for service in services.values():
                            return service

                        raise ValueError(self.__pydantic_extra__)

                    return {}

        raise ValueError(self.__pydantic_extra__)
