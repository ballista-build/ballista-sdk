from abc import ABC
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class BaseOneOfModel(BaseModel, json_schema_extra={"maxProperties": 1, "minProperties": 1}):
    def which(self) -> str:
        for field_name in self.model_fields_set:
            return field_name

        if self.__pydantic_extra__:
            for field_name in self.__pydantic_extra__:
                return field_name

        raise Exception("BAD")


# TODO: Make a "OneOfField"???


class BaseNamedModel(ABC, BaseModel):
    name: Annotated[str, Field(description="Unique name of object.", pattern=r"^[a-z0-9-]+$", min_length=1)]
    description: Annotated[str | None, Field(description="Human-readable description of object.")] = None
    title: str | None = Field(
        default_factory=lambda data: data.get("name"), description="Human-readable title of object."
    )

    model_config = ConfigDict(frozen=True)
