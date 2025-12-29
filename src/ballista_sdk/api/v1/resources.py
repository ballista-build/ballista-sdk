from typing import Annotated

from openapi_pydantic import DataType, Schema
from pydantic import BaseModel, Field, create_model

from .common import BaseNamedModel
from .settings import Config, Secret


class BaseResourceSetting(BaseModel):
    shared: Annotated[bool, Field(description="Indicates if value is shared across artifacts.")]


class ResourceConfig(BaseResourceSetting, Config):
    pass


class ResourceSecret(BaseResourceSetting, Secret):
    pass


ResourceSetting = ResourceConfig | ResourceSecret


class ResourceRequirementParameters(Schema, frozen=True):
    pass


class Resource(BaseNamedModel):
    """Resource available to use as an artifact requirement."""

    configs: Annotated[list[ResourceConfig], Field(description="Configs that are received by Artifact.")] = []
    instance_id_fields: Annotated[
        list[str],
        Field(
            description="List of field names from Requirements schema that determine resource uniqueness.",
            title="instance_id Fields",
        ),
    ] = []
    prefix: Annotated[str, Field(description="Default prefix of injected values.")]
    requirements: Annotated[
        ResourceRequirementParameters,
        Field(
            alias="requirements",
            default_factory=ResourceRequirementParameters,
            description="OpenAPI Schema representing requirements for a resource.",
        ),
    ]
    secrets: Annotated[list[ResourceSecret], Field(description="Secrets that are received by Artifact")] = []

    def get_requirements_model(self, project_title: str) -> type[BaseModel]:
        return _schema_to_model(self.requirements, f"{project_title}{self.name}ResourceRequirement")


DATATYPE_MAP = {DataType.BOOLEAN: bool, DataType.INTEGER: int, DataType.NUMBER: float, DataType.STRING: str}


def _schema_to_model(schema: Schema, model_name: str) -> type[BaseModel]:
    type = schema.type or DataType.OBJECT
    if type == DataType.NULL:
        raise ValueError()

    if type == DataType.OBJECT:
        fields = {}
        required = schema.required or []
        properties = schema.properties or {}
        for prop_name, prop in properties.items():
            if not isinstance(prop, Schema):
                continue

            if prop.type == DataType.OBJECT:
                raise ValueError("NYI")
                # pt = _schema_to_model(prop, "")
            else:
                pt = DATATYPE_MAP.get(prop.type)

            field = Field(description=prop.description, title=prop.title)
            if pt is not None and prop_name not in required:
                pt |= None
                field.default = None

            fields[prop_name] = Annotated[pt, field]

        return create_model(model_name, **fields, __base__=BaseModel)

    else:
        raise ValueError("NYI")
