from enum import StrEnum, auto
from typing import Annotated, NamedTuple

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


class ResourceRequirementSchema(Schema, frozen=True):
    """Schema defining a ResourceRequirement."""

    pass


class ResourceRequirement(BaseModel):
    """Requirement data for a Resource."""

    model_config = {"extra": "forbid"}


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
    prefix: Annotated[str, Field(description="Default prefix of values received by Artifact.")]
    requirements: Annotated[
        ResourceRequirementSchema,
        Field(
            alias="requirements",
            default_factory=ResourceRequirementSchema,
            description="OpenAPI Schema representing requirements for a resource.",
        ),
    ]
    secrets: Annotated[list[ResourceSecret], Field(description="Secrets that are received by Artifact")] = []

    def get_requirements_model(self, project_title: str) -> type[ResourceRequirement]:
        return _schema_to_model(self.requirements, f"{project_title}{self.name}ResourceRequirement")


DATATYPE_MAP = {DataType.BOOLEAN: bool, DataType.INTEGER: int, DataType.NUMBER: float, DataType.STRING: str}


def _schema_to_model(schema: Schema, model_name: str) -> type[ResourceRequirement]:
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

        return create_model(model_name, **fields, __base__=ResourceRequirement)

    else:
        raise ValueError("NYI")


class ResourceReference(NamedTuple):
    """Reference to a Resource by its name and the Project's name its in."""

    project_name: str
    resource_name: str


class ResourceStatus(StrEnum):
    UNKNOWN = auto()
    """Resource status is unknown."""
    NOT_FOUND = auto()
    """Resource not found."""
    PROVISIONING = auto()
    """Resource is being created."""
    AVAILABLE = auto()
    """Resource is ready to be used."""
    UNHEALTHY = auto()
    """Resource exists but is not healthy."""
    DESTROYING = auto()
    """Resource is being destroyed."""


class ResourceProviderStatus(StrEnum):
    UNKNOWN = auto()
    """Resource Provider status is unknown."""
    STARTING = auto()
    """Resource Provider is starting and not yet able to process requests."""
    AVAILABLE = auto()
    """Resource Provider is available to process requests."""
    TERMINATING = auto()
    """Resource Provider is not longer processing requests and terminating."""


class ResourceAccess(StrEnum):
    READ = auto()
    READ_WRITE = auto()
    OWNER = auto()
