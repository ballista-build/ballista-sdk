from pydantic import BaseModel

from ...api.v1 import ResourceProviderStatus, ResourceStatus, SettingValue


class ResourceProviderStatusResponse(BaseModel):
    status: ResourceProviderStatus
    detail: str | None


class ResourceStatusResponse(BaseModel):
    status: ResourceStatus
    detail: str | None


class WriteResourceResponse(BaseModel):
    configs: dict[str, SettingValue] = {}
    secrets: dict[str, SettingValue] = {}
