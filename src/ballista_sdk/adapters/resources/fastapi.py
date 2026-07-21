try:
    from fastapi import APIRouter, Depends, Query, Response
    from fastapi import exceptions as fastapi_exceptions
    from fastapi import status as fastapi_status

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from typing import Annotated

from ballista_sdk.adapters.primitives import ArtifactReference
from ballista_sdk.api.v1 import Environment, EnvironmentTier

from ..exceptions import ArtifactResourceAlreadyExists, ArtifactResourceNotFound
from .provider import (
    ResourceProvider,
    ResourceProviderStatus,
    ResourceRequirement,
    ResourceStatus,
)
from .pydantic import ResourceProviderStatusResponse, ResourceStatusResponse


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
def resource_provider_to_apirouter[Requirement: ResourceRequirement](
    resource_name: str,
    resource_requirement_type: type[Requirement],
    resource_provider: ResourceProvider,
) -> APIRouter:
    # Base router for resource name plus environment info.
    provider_router = APIRouter(
        prefix=f"/{resource_name}" + "/{environment_tier}/{environment_name}",
        tags=[resource_name],
    )

    @provider_router.get("/")
    async def get_status(environment: DepEnvironment, response: Response) -> ResourceProviderStatusResponse:
        status, message = await resource_provider.get_status(environment)

        if status != ResourceProviderStatus.AVAILABLE:
            response.status_code = fastapi_status.HTTP_503_SERVICE_UNAVAILABLE

        return ResourceProviderStatusResponse(status=status, detail=message)

    # Resource router
    resource_router = APIRouter(prefix="/{artifact_project_name}/{artifact_name}/{artifact_version}")

    @resource_router.get("/")
    async def get_resource_status(
        environment: DepEnvironment,
        artifact: DepArtifact,
        resource_requirement: Annotated[resource_requirement_type, Query()],
        response: Response,
    ) -> ResourceStatusResponse:
        status, message = await resource_provider.get_resource_status(environment, artifact, resource_requirement)

        if status == ResourceStatus.NOT_FOUND:
            response.status_code = fastapi_status.HTTP_404_NOT_FOUND
        elif status != ResourceStatus.AVAILABLE:
            response.status_code = fastapi_status.HTTP_503_SERVICE_UNAVAILABLE

        return ResourceStatusResponse(status=status, detail=message)

    @resource_router.post("/")
    async def provision_resource(
        environment: DepEnvironment, artifact: DepArtifact, resource_requirement: resource_requirement_type
    ):
        try:
            await resource_provider.provision_resource(environment, artifact, resource_requirement)

        except ArtifactResourceAlreadyExists as e:
            raise fastapi_exceptions.HTTPException(status_code=fastapi_status.HTTP_409_CONFLICT, detail=str(e))

        except Exception as e:
            pass

    @resource_router.put("/")
    async def update_resource(
        environment: DepEnvironment, artifact: DepArtifact, resource_requirement: resource_requirement_type
    ):
        try:
            await resource_provider.update_resource(environment, artifact, resource_requirement)

        except ArtifactResourceNotFound as e:
            raise fastapi_exceptions.HTTPException(status_code=fastapi_status.HTTP_404_NOT_FOUND, detail=str(e))

    @resource_router.delete("/")
    async def destroy_resource(
        environment: DepEnvironment, artifact: DepArtifact, resource_requirement: resource_requirement_type
    ):
        pass

    @resource_router.post("/copy/")
    async def copy_resource(
        environment: DepEnvironment, artifact: DepArtifact, resource_requirement: resource_requirement_type
    ):
        pass

    # Resource Access
    access_router = APIRouter(prefix="/access")

    @access_router.get("/")
    async def get_resource_access(
        environment: DepEnvironment,
        artifact: DepArtifact,
        resource_requirement: Annotated[resource_requirement_type, Query()],
    ):
        pass

    @access_router.post("/")
    async def grant_resource_access(
        environment: DepEnvironment, artifact: DepArtifact, resource_requirement: resource_requirement_type
    ):
        pass

    @access_router.delete("/")
    async def revoke_resource_access(
        environment: DepEnvironment, artifact: DepArtifact, resource_requirement: resource_requirement_type
    ):
        pass

    resource_router.include_router(access_router)
    provider_router.include_router(resource_router)

    return provider_router
