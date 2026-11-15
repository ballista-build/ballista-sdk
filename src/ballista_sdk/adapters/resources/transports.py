from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import aiohttp

from ballista_sdk.adapters.exceptions import ProvidedResourceException
from ballista_sdk.adapters.primitives import ProvidedResourceReference

from .provider import (
    ArtifactReference,
    Environment,
    ResourceAccess,
    ResourceInstance,
    ResourceProvider,
    ResourceProviderStatus,
    ResourceStatus,
    SettingValue,
)
from .pydantic import (
    ListResourcesResponseItem,
    ResourceProviderStatusResponse,
    ResourceStatusResponse,
    WriteResourceResponse,
)


@dataclass
class ResourceProviderTransport[R: ResourceInstance = ResourceInstance](ResourceProvider[R]):
    """Message transport to a remote `ResourceProvider` implementation.

    Translates the `ResourceProvider` interface into remote calls, allowing an `InfrastructureAdapter` to communicate with a `ResourceProvider`.
    """

    provided_resource_reference: ProvidedResourceReference


@dataclass
class ExecResourceProviderTransport[R: ResourceInstance = ResourceInstance](ResourceProviderTransport[R]):
    """Control resource lifecycle via command execution."""

    pass


@dataclass
class RESTResourceProviderTransport[R: ResourceInstance = ResourceInstance](ResourceProviderTransport[R]):
    """Control resource lifecycle via REST API."""

    api_url: str
    """URL to implementation of REST API."""

    # TODO: It will probably make sense to have a shared instance of this for maximum pooling.
    # _aiohttp_session: aiohttp.ClientSession = field(default_factory=aiohttp.ClientSession)

    @property
    def _aiohttp_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(headers={"Authorization": "Bearer BALLISTA"})

    def _environment_request(self, environment: Environment) -> str:
        return f"{self.api_url}{environment.tier}/{environment.name}/"

    def _artifact_request(
        self,
        environment: Environment,
        artifact: ArtifactReference,
    ) -> str:
        return f"{self._environment_request(environment)}{artifact.project_name}/{artifact.artifact_name}/{artifact.version}/"

    def _artifact_resource_request(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource: R,
    ) -> tuple[str, dict[str, Any] | None]:
        json = resource.model_dump(mode="json") or None

        return self._artifact_request(environment, artifact), json

    def _access_request(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource: R,
    ) -> str:
        return self._artifact_request(environment, artifact)

    # Provider
    async def get_status(self, environment: Environment) -> tuple[ResourceProviderStatus, str | None]:
        try:
            async with self._aiohttp_session.get(url=self._environment_request(environment)) as aiohttp_response:
                response = ResourceProviderStatusResponse.model_validate_json(await aiohttp_response.read())

                return response.status, response.detail

        except aiohttp.ClientError:
            return ResourceProviderStatus.UNAVAILABLE, None

    # Resource
    async def list_resources(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        *,
        page_number: int,
        page_size: int,
        resource: R | None = None,
        minimum_access: ResourceAccess = ResourceAccess.NONE,
    ) -> AsyncGenerator[tuple[R, ResourceStatus, ResourceAccess, str | None]]:
        url = f"{self.api_url}{environment.tier}/{environment.name}/{artifact.project_name}/{artifact.artifact_name}/{artifact.version}/"
        params = {"page_number": page_number, "page_size": page_size}

        try:
            async with self._aiohttp_session.get(
                url=self._artifact_request(environment, artifact),
                params=params,
            ) as aiohttp_response:
                while line := await aiohttp_response.content.readline():
                    response = ListResourcesResponseItem[R].model_validate_json(line)

                    yield (
                        response.resource,
                        response.status,
                        response.access,
                        response.detail,
                    )

        except aiohttp.ClientError:
            return

    async def get_resource_status(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource: R,
    ) -> tuple[ResourceStatus, ResourceAccess, str | None]:
        url, json = self._artifact_resource_request(environment, artifact, resource)

        async with self._aiohttp_session.get(url=url, json=json) as aiohttp_response:
            response = ResourceStatusResponse.model_validate_json(await aiohttp_response.read())

        return response.status, response.access, response.detail

    async def provision_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource: R,
    ) -> tuple[ResourceAccess, dict[str, SettingValue], dict[str, SettingValue]]:
        url, json = self._artifact_resource_request(environment, artifact, resource)

        async with self._aiohttp_session.post(url=url, json=json) as aiohttp_response:
            response = WriteResourceResponse.model_validate_json(await aiohttp_response.read())

        return response.access, response.configs, response.secrets

    async def update_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource: R,
    ) -> tuple[ResourceAccess, dict[str, SettingValue], dict[str, SettingValue]]:
        url, json = self._artifact_resource_request(environment, artifact, resource)

        async with self._aiohttp_session.put(url=url, json=json) as aiohttp_response:
            response = WriteResourceResponse.model_validate_json(await aiohttp_response.read())

        return response.access, response.configs, response.secrets

    async def triggers_reprovision(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource: R,
    ) -> bool:
        return False

    async def destroy_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource: R,
        *,
        force: bool = False,
    ):
        pass


class GRPCResourceProviderTransport[R: ResourceInstance](ResourceProviderTransport[R]):
    """Control resource lifecycle via GRPC."""

    pass


class TCPResourceProviderTransport[R: ResourceInstance](ResourceProviderTransport[R]):
    """Control resource lifecycle via TCP socket."""

    pass


class QueueResourceProviderTransport[R: ResourceInstance](ResourceProviderTransport[R]):
    """Control resource lifecycle via message queue."""

    pass
