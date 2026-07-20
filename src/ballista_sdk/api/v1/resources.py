from enum import StrEnum, auto
from typing import Annotated

from openapi_pydantic import DataType, Schema
from pydantic import BaseModel, Field, create_model

from .common import BaseNamedModel, BaseOneOfModel
from .settings import Config, Secret


class BaseResourceSetting(BaseModel):
    shared: Annotated[bool, Field(description="Indicates if value is shared across artifacts.")]


class ResourceConfig(BaseResourceSetting, Config):
    pass


class ResourceSecret(BaseResourceSetting, Secret):
    pass


ResourceSetting = ResourceConfig | ResourceSecret


class ProvidedResourceRequirementSchema(Schema, frozen=True):
    """Schema defining a ResourceRequirement."""

    pass


class ResourceRequirementRequirement(BaseModel):
    """Requirement data for a ResourceRequirement."""

    model_config = {"extra": "allow"}


class _BaseServiceResourceTransport(BaseModel):
    service: Annotated[str, Field(description="Unique identifier of service.", title="Service Name")]


class RESTProvidedResourceTransport(_BaseServiceResourceTransport):
    """Resource Provider communication via REST."""

    path: Annotated[str, Field(description="HTTP path.")]


class ProvidedResourceTransportMethod(BaseOneOfModel):
    # exec: Annotated[actions.ExecAction | None, Field()] = None
    # grpc: Annotated[GRPCHealthCheckAction | None, Field()] = None
    rest: Annotated[RESTProvidedResourceTransport | None, Field()] = None
    # tcp: Annotated[actions.TCPAction | None, Field()] = None


class ProvidedResource(BaseNamedModel):
    """Resource available to use as an Artifact requirement."""

    configs: Annotated[
        list[ResourceConfig],
        Field(description="Configs that are received by Artifact."),
    ] = []
    # TODO: Is this still needed?
    instance_id_fields: Annotated[
        list[str],
        Field(
            description="List of field names from Requirements schema that determine resource uniqueness.",
            title="instance_id Fields",
        ),
    ] = []
    prefix: Annotated[str, Field(description="Default prefix of values received by Artifact.")]
    requirements: Annotated[
        ProvidedResourceRequirementSchema,
        Field(
            alias="requirements",
            default_factory=ProvidedResourceRequirementSchema,
            description="OpenAPI Schema representing requirements for a resource.",
        ),
    ]
    secrets: Annotated[list[ResourceSecret], Field(description="Secrets that are received by Artifact")] = []
    transport: Annotated[
        ProvidedResourceTransportMethod | None,
        Field(
            description="Transport method for communication with Resource Provider. If not specified, resource lifecycle is managed externally."
        ),
    ] = None

    def get_requirements_model(self, project_title: str) -> type[ResourceRequirementRequirement]:
        return _schema_to_model(
            self.prefix,
            self.requirements,
            self.configs + self.secrets,
            f"{project_title}{self.name}ResourceRequirement",
        )


DATATYPE_MAP = {
    DataType.BOOLEAN: bool,
    DataType.INTEGER: int,
    DataType.NUMBER: float,
    DataType.NULL: None,
    DataType.STRING: str,
}


def _schema_to_model(
    prefix: str, schema: Schema, settings: list[ResourceSetting], model_name: str
) -> type[ResourceRequirementRequirement]:
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
            elif isinstance(prop.type, list):
                # No idea what to do here
                pt = None
            else:
                pt = DATATYPE_MAP.get(prop.type)

            field = Field(description=prop.description, title=prop.title)
            if pt is not None and prop_name not in required:
                pt |= None
                field.default = None

            fields[prop_name] = Annotated[pt, field]

        for setting in settings:
            # Create alias field for each setting to change its injected name.
            alias_name = setting.name + "-alias"
            fields[alias_name] = Annotated[
                str | None, Field(description=f'Alias the "{setting.name}" envvar.', default=None)
            ]

        return create_model(model_name, **fields, __base__=ResourceRequirementRequirement)

    else:
        raise ValueError("NYI")


class ResourceProviderStatus(StrEnum):
    """Statuses for a Resource Provider."""

    UNKNOWN = auto()
    """Resource Provider status is unknown."""
    UNAVAILABLE = auto()
    """Resource Provider is unavailable."""
    STARTING = auto()
    """Resource Provider is starting and not yet able to process requests."""
    AVAILABLE = auto()
    """Resource Provider is available to process requests."""
    TERMINATING = auto()
    """Resource Provider is not longer processing requests and terminating."""


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


class ResourceAccess(StrEnum):
    READ = auto()
    """Resource can only be read from."""
    READ_WRITE = auto()
    """Resource can be read from and written to."""
    OWNER = auto()
    """Resource can be read from, written to, and modified."""
