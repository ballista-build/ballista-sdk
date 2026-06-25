try:
    from fastapi import APIRouter, Depends, Path

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from typing import Annotated

from ballista_sdk.api.v1 import ArtifactReference, Environment, EnvironmentTier

from .provider import ResourceProvider, ResourceProviderStatus, ResourceStatus


def _get_environment(environment_tier: EnvironmentTier, environment_name: str) -> Environment:
    return Environment(name=environment_name, tier=environment_tier)


DepEnvironment = Annotated[Environment, Depends(_get_environment)]


def _get_artifact_reference(artifact_project_name: str, artifact_name: str, artifact_version: str) -> ArtifactReference:
    return ArtifactReference(project_name=artifact_project_name, artifact_name=artifact_name, version=artifact_version)


DepArtifact = Annotated[ArtifactReference, Depends(_get_artifact_reference)]


# Map a ResourceProvider to a FastAPI APIRouter implementing the Ballista Resource Provider REST API
def resource_provider_to_apirouter(resource_name: str, resource_provider: ResourceProvider) -> APIRouter:
    # Base router for resource name plus environment info.
    provider_router = APIRouter(
        prefix=f"/{resource_name}" + "/{environment_tier}/{environment_name}", tags=[resource_name]
    )

    @provider_router.get("/")
    async def get_provider_status(environment: DepEnvironment) -> ResourceProviderStatus:
        return await resource_provider.get_status(environment)

    # Resource router
    resource_router = APIRouter(prefix="/{artifact_project_name}/{artifact_name}/{artifact_version}")

    @resource_router.get("/")
    async def get_resource_status(environment: DepEnvironment, artifact: DepArtifact) -> ResourceStatus:
        requirement = {}

        return await resource_provider.get_resource_status(artifact, resource, environment)

    @resource_router.post("/")
    async def provision_resource(environment: DepEnvironment, artifact: DepArtifact):
        pass

    @resource_router.put("/")
    async def update_resource(environment: DepEnvironment, artifact: DepArtifact):
        pass

    @resource_router.delete("/")
    async def destroy_resource(environment: DepEnvironment, artifact: DepArtifact):
        pass

    @resource_router.post("/copy/")
    async def copy_resource(environment: DepEnvironment, artifact: DepArtifact):
        pass

    # Resource Access
    access_router = APIRouter(prefix="/access")

    @access_router.get("/")
    async def get_resource_access(environment: DepEnvironment, artifact: DepArtifact):
        pass

    @access_router.post("/")
    async def grant_resource_access(environment: DepEnvironment, artifact: DepArtifact):
        pass

    @access_router.delete("/")
    async def revoke_resource_access(environment: DepEnvironment, artifact: DepArtifact):
        pass

    resource_router.include_router(access_router)
    provider_router.include_router(resource_router)

    return provider_router
