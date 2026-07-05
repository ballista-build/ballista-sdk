from abc import ABC
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class BaseOneOfModel(BaseModel, json_schema_extra={"maxProperties": 1, "minProperties": 1}):
    def which(self) -> str:
        for f in self.model_fields_set:
            return f

        if self.__pydantic_extra__:
            for f in self.__pydantic_extra__:
                return f

        raise Exception("BAD")


# TODO: Make a "OneOfField"???


class BaseNamedModel(ABC, BaseModel):
    name: Annotated[str, Field(description="Unique name of object.")]  # TODO: Put a pattern on here
    description: Annotated[str | None, Field(description="Human-readable description of object.")] = None
    title: str | None = Field(
        default_factory=lambda data: data.get("name"), description="Human-readable title of object."
    )

    model_config = ConfigDict(frozen=True)
