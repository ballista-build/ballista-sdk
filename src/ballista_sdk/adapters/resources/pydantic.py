from pydantic import BaseModel

from ...api.v1.resources import ResourceProviderStatus, ResourceStatus


class ResourceProviderStatusResponse(BaseModel):
    status: ResourceProviderStatus
    detail: str | None


class ResourceStatusResponse(BaseModel):
    status: ResourceStatus
    detail: str | None
