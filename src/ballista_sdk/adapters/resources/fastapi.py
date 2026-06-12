try:
    from fastapi import APIRouter, Path

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from typing import Annotated

from pydantic import BaseModel, Field

from ballista_sdk.api.v1 import ArtifactReference, Environment, EnvironmentTier

from .provider import ResourceProvider, ResourceStatus


class EnvironmentArtifactResource(BaseModel):
    environment_name: Annotated[str, Field(description="Unique name of an existing Environment.")]
    environment_tier: Annotated[EnvironmentTier, Field()]
    artifact_project_name: Annotated[str, Field(description="Unique name of an existing Project the Artifact resides.")]
    artifact_name: Annotated[str, Field(description="Unique name of an existing Artifact.")]
    artifact_version: Annotated[str, Field(description="Version of an existing Artifact.")]

    @property
    def environment(self) -> Environment:
        return Environment(name=self.environment_name, tier=self.environment_tier)

    @property
    def artifact(self) -> ArtifactReference:
        return ArtifactReference(
            project_name=self.artifact_project_name, artifact_name=self.artifact_name, version=self.artifact_version
        )


# Map a ResourceProvider to a FastAPI APIRouter implementing the Ballista Resource Provider REST API
def resource_provider_to_apirouter(resource_name: str, resource_provider: ResourceProvider) -> APIRouter:
    provider_router = APIRouter(prefix=f"/{resource_name}")

    @provider_router.get("")
    async def get_provider_status():
        pass

    # Resource router
    resource_router = APIRouter(prefix="/{environment_name}/{artifact_project_name}/{artifact_name}/{artifact_version}")

    @resource_router.get("")
    async def get_resource_status(params: Annotated[EnvironmentArtifactResource, Path]) -> ResourceStatus:
        environment = params.environment
        artifact = params.artifact
        requirement = {}

        return await resource_provider.get_resource_status(artifact, resource, environment)

    @resource_router.post("")
    async def provision_resource(params: Annotated[EnvironmentArtifactResource, Path]):
        pass

    @resource_router.put("")
    async def update_resource(params: Annotated[EnvironmentArtifactResource, Path]):
        pass

    @resource_router.delete("")
    async def destroy_resource(params: Annotated[EnvironmentArtifactResource, Path]):
        pass

    @resource_router.post("/copy")
    async def copy_resource(params: Annotated[EnvironmentArtifactResource, Path]):
        pass

    # Resource Access
    access_router = APIRouter(prefix="/access")

    @access_router.get("")
    async def get_resource_access(params: Annotated[EnvironmentArtifactResource, Path]):
        pass

    @access_router.post("")
    async def grant_resource_access(params: Annotated[EnvironmentArtifactResource, Path]):
        pass

    @access_router.delete("")
    async def revoke_resource_access(params: Annotated[EnvironmentArtifactResource, Path]):
        pass

    resource_router.include_router(access_router)
    provider_router.include_router(resource_router)

    return provider_router
