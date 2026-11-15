try:
    from fastapi import APIRouter, Depends, Query, Response
    from fastapi import exceptions as fastapi_exceptions
    from fastapi import status as fastapi_status

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from typing import Annotated, AsyncGenerator

from ballista_sdk.adapters.primitives import ArtifactReference
from ballista_sdk.api.v1 import Environment, EnvironmentTier, ResourceInstance

from ..exceptions import ResourceAlreadyExists, ResourceNotFound
from .provider import (
    ResourceAccess,
    ResourceProvider,
    ResourceProviderStatus,
    ResourceStatus,
)
from .pydantic import ListResourcesResponseItem, ResourceProviderStatusResponse, ResourceStatusResponse


def _get_environment(environment_tier: EnvironmentTier, environment_name: str) -> Environment:
    return Environment(name=environment_name, tier=environment_tier)


DepEnvironment = Annotated[Environment, Depends(_get_environment)]


def _get_artifact_reference(artifact_project_name: str, artifact_name: str, artifact_version: str) -> ArtifactReference:
    return ArtifactReference(
        project_name=artifact_project_name,
        artifact_name=artifact_name,
        version=artifact_version,
    )


DepArtifact = Annotated[ArtifactReference, Depends(_get_artifact_reference)]


# Map a ResourceProvider to a FastAPI APIRouter implementing the Ballista Resource Provider REST API
# TODO: Update this to use PEP 747 TypeForm!
def resource_provider_to_apirouter[R: ResourceInstance](
    resource_name: str,
    resource_instance_type: type[R],
    resource_provider: ResourceProvider[R],
) -> APIRouter:
    """Creates a FastAPI APIRouter that is bound to a specific Ballista ResourceProvider."""
    # Base router for resource name plus environment info.
    provider_router = APIRouter(
        prefix=f"/{resource_name}" + "/{environment_tier}/{environment_name}",
        tags=[resource_name],
    )

    # TODO: AUTH

    @provider_router.get("")
    async def get_status(environment: DepEnvironment, response: Response) -> ResourceProviderStatusResponse:
        """Get the status of the Resource Provider APIs."""
        status, message = await resource_provider.get_status(environment)

        if status != ResourceProviderStatus.AVAILABLE:
            response.status_code = fastapi_status.HTTP_503_SERVICE_UNAVAILABLE

        return ResourceProviderStatusResponse(status=status, detail=message)

    # Resource router
    resource_router = APIRouter(prefix="/{artifact_project_name}/{artifact_name}/{artifact_version}")

    @resource_router.get("/resources")
    async def list_resources(
        environment: DepEnvironment,
        artifact: DepArtifact,
        page_number: int = 1,
        page_size: int = 20,
    ) -> AsyncGenerator[ListResourcesResponseItem[resource_instance_type]]:
        result = resource_provider.list_resources(
            environment,
            artifact,
            page_number=page_number,
            page_size=page_size,
            minimum_access=ResourceAccess.OWNER,
        )

        async for list_resource, list_status, list_access, list_detail in result:
            yield ListResourcesResponseItem(
                resource=list_resource,
                status=list_status,
                access=list_access,
                detail=list_detail,
            )

    @resource_router.get("")
    async def get_resource_status(
        environment: DepEnvironment,
        artifact: DepArtifact,
        resource: Annotated[resource_instance_type, Query()],
        response: Response,
    ) -> ResourceStatusResponse:
        status, access, message = await resource_provider.get_resource_status(environment, artifact, resource)

        if status == ResourceStatus.NOT_FOUND:
            response.status_code = fastapi_status.HTTP_404_NOT_FOUND
        elif status != ResourceStatus.AVAILABLE:
            response.status_code = fastapi_status.HTTP_503_SERVICE_UNAVAILABLE

        return ResourceStatusResponse(status=status, access=access, detail=message)

    @resource_router.post("")
    async def provision_resource(environment: DepEnvironment, artifact: DepArtifact, resource: R):
        """Provisions a new resource."""
        try:
            await resource_provider.provision_resource(environment, artifact, resource)

        except ResourceAlreadyExists[R] as e:
            raise fastapi_exceptions.HTTPException(status_code=fastapi_status.HTTP_409_CONFLICT, detail=str(e))

        except Exception as e:
            pass

    @resource_router.put("")
    async def update_resource(environment: DepEnvironment, artifact: DepArtifact, resource: resource_instance_type):
        try:
            await resource_provider.update_resource(environment, artifact, resource)

        except ResourceNotFound[R] as e:
            raise fastapi_exceptions.HTTPException(status_code=fastapi_status.HTTP_404_NOT_FOUND, detail=str(e))

    @resource_router.delete("")
    async def destroy_resource(environment: DepEnvironment, artifact: DepArtifact, resource: resource_instance_type):
        pass

    provider_router.include_router(resource_router)

    return provider_router
