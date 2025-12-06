from abc import ABC
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class BaseOneOfModel(BaseModel, json_schema_extra={"maxProperties": 1, "minProperties": 1}):
    def which(self) -> Any:
        for f in self.model_fields_set:
            return f


# TODO: Make a "OneOfField"???


class BaseNamedModel(ABC, BaseModel):
    name: Annotated[str, Field(description="Unique name of object.")]
    description: Annotated[str, Field(description="Human-readable description of object.")] = ""
    title: str | None = Field(default_factory=lambda data: data["name"], description="Human-readable title of object.")

    model_config = ConfigDict(frozen=True)
