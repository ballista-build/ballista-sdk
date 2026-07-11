from dataclasses import dataclass, field
from typing import Protocol

import aiohttp

from ballista_sdk.adapters.exceptions import ResourceProviderException
from ballista_sdk.api.v1.resources import ResourceProviderReference

from ..exceptions import ArtifactResourceAlreadyExists, ArtifactResourceNotFound
from .provider import (
    ArtifactReference,
    Environment,
    ResourceAccess,
    ResourceProvider,
    ResourceProviderStatus,
    ResourceRequirement,
    ResourceStatus,
    SettingValue,
)
from .pydantic import (
    ResourceProviderStatusResponse,
    ResourceStatusResponse,
    WriteResourceResponse,
)


@dataclass
class ResourceProviderTransport(ResourceProvider, Protocol):
    """Message transport to a remote `ResourceProvider` implementation.

    Translates the `ResourceProvider` interface into remote calls, allowing an `InfrastructureAdapter` to communicate with a `ResourceProvider` elsewhere."""

    resource_provider: ResourceProviderReference


@dataclass
class ExecResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via command execution."""

    pass


@dataclass
class MemoryResourceProviderTransport(ResourceProviderTransport):
    _resources: dict[Environment, dict[ArtifactReference, list[ResourceRequirement]]] = field(
        default_factory=dict, init=False
    )

    async def get_status(self, environment: Environment) -> tuple[ResourceProviderStatus, str | None]:
        return ResourceProviderStatus.AVAILABLE, None

    # Resource
    async def list_resources(self, environment: Environment, artifact: ArtifactReference) -> list:
        return self._resources.get(environment, {}).get(artifact, [])

    async def get_resource_status(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ) -> tuple[ResourceStatus, str | None]:
        if resource_requirement in self._resources.get(environment, {}).get(artifact, []):
            return ResourceStatus.AVAILABLE, None
        else:
            return ResourceStatus.NOT_FOUND, None

    async def provision_resource(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ):
        if resource_requirement in self._resources.get(environment, {}).get(artifact, []):
            raise ArtifactResourceAlreadyExists(resource_provider=self.resource_provider, artifact=artifact)

        self._resources.setdefault(environment, {}).setdefault(artifact, []).append(resource_requirement)

    async def update_resource(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ):
        if resource_requirement not in self._resources.get(environment, {}).get(artifact, []):
            raise ArtifactResourceNotFound(resource_provider=self.resource_provider, artifact=artifact)

    # Resource Access
    async def get_resource_access(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ) -> ResourceAccess | None:
        pass

    async def grant_resource_access(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        resource_requirement: ResourceRequirement,
    ):
        pass

    async def revoke_resource_access(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ):
        pass


@dataclass
class RESTResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via REST API."""

    api_url: str
    """URL to implementation of REST API."""

    # TODO: It will probably make sense to have a shared instance of this for maximum pooling.
    # _aiohttp_session: aiohttp.ClientSession = field(default_factory=aiohttp.ClientSession)

    def _request_headers(self):
        # TODO: Auth and more
        pass

    @property
    def _aiohttp_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession()

    def _request(
        self,
        method: str,
        environment: Environment,
        artifact: ArtifactReference | None = None,
        resource_requirement: ResourceRequirement | None = None,
    ):
        if artifact:
            json = resource_requirement.model_dump(mode="json") if resource_requirement else None

            return self._aiohttp_session.request(
                method,
                f"{self.api_url}{environment.tier}/{environment.name}/{artifact.project_name}/{artifact.artifact_name}/{artifact.version}/",
                json=json,
            )

        else:
            return self._aiohttp_session.request(method, f"{environment.tier}/{environment.name}/")

    def _environment_request(self, environment: Environment) -> dict:
        return {"url": f"{environment.tier}/{environment.name}/"}

    def _artifact_request(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ) -> dict:
        json = resource_requirement.model_dump(mode="json") or None

        return {
            "url": f"{self.api_url}{environment.tier}/{environment.name}/{artifact.project_name}/{artifact.artifact_name}/{artifact.version}/",
            "json": json,
        }

    # Provider
    async def get_status(self, environment: Environment) -> tuple[ResourceProviderStatus, str | None]:
        try:
            async with self._aiohttp_session.get(**self._environment_request(environment)) as aiohttp_response:
                response = ResourceProviderStatusResponse.model_validate_json(await aiohttp_response.read())

                return response.status, response.detail

        except aiohttp.ClientError as e:
            return ResourceProviderStatus.UNAVAILABLE, None

    # Resource
    async def list_resources(self, environment: Environment, artifact: ArtifactReference) -> list:
        async with self._aiohttp_session.get("") as response:
            pass

        return []

    async def get_resource_status(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ) -> tuple[ResourceStatus, str | None]:
        async with self._aiohttp_session.get(
            **self._artifact_request(environment, artifact, resource_requirement)
        ) as aiohttp_response:
            response = ResourceStatusResponse.model_validate_json(await aiohttp_response.read())

            return response.status, response.detail

    async def provision_resource(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ) -> tuple[dict[str, SettingValue], dict[str, SettingValue]]:
        async with self._aiohttp_session.post(
            **self._artifact_request(environment, artifact, resource_requirement)
        ) as aiohttp_response:
            response = WriteResourceResponse.model_validate_json(await aiohttp_response.read())

            return response.configs, response.secrets

        raise ResourceProviderException(ResourceProviderReference(self.resource_project_name, self.resource_name))

    async def update_resource(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ) -> tuple[dict[str, SettingValue], dict[str, SettingValue]]:
        async with self._aiohttp_session.put(
            **self._artifact_request(environment, artifact, resource_requirement)
        ) as aiohttp_response:
            response = WriteResourceResponse.model_validate_json(await aiohttp_response.read())

            return response.configs, response.secrets

        raise ResourceProviderException(ResourceProviderReference(self.resource_project_name, self.resource_name))

    # Resource Access
    async def get_resource_access(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ) -> ResourceAccess | None:
        raise ResourceProviderException(self.resource_provider)

    async def grant_resource_access(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ):
        raise ResourceProviderException(self.resource_provider)

    async def revoke_resource_access(
        self, environment: Environment, artifact: ArtifactReference, resource_requirement: ResourceRequirement
    ):
        raise ResourceProviderException(self.resource_provider)


class GRPCResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via GRPC."""

    pass


class TCPResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via TCP socket."""

    pass


class QueueResourceProviderTransport(ResourceProviderTransport):
    """Control resource lifecycle via message queue."""

    pass
