from pydantic import BaseModel

from ...api.v1 import (
    ResourceAccess,
    ResourceInstance,
    ResourceProviderStatus,
    ResourceStatus,
    SettingValue,
)


class ResourceProviderStatusResponse(BaseModel):
    status: ResourceProviderStatus
    detail: str | None


class ListResourcesResponseItem[R: ResourceInstance](BaseModel):
    """Individual Resource entry from REST API ListResources."""

    resource: R
    status: ResourceStatus
    access: ResourceAccess
    detail: str | None


class ResourceStatusResponse(BaseModel):
    status: ResourceStatus
    access: ResourceAccess
    detail: str | None


class WriteResourceResponse(BaseModel):
    access: ResourceAccess
    configs: dict[str, SettingValue] = {}
    secrets: dict[str, SettingValue] = {}
