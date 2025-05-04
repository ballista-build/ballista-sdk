from typing import Annotated, Any, Callable

from pydantic import BaseModel, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema
from semver import Version


# Create a Pydantic annotation for parsing semver
# Reference: https://python-semver.readthedocs.io/en/latest/advanced/combine-pydantic-and-semver.html
class _VersionPydanticAnnotation:
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Callable[[Any], core_schema.CoreSchema],
    ) -> core_schema.CoreSchema:
        def validate_from_str(value: str) -> Version:
            return Version.parse(value)

        from_str_schema = core_schema.chain_schema(
            [
                core_schema.str_schema(),
                core_schema.no_info_plain_validator_function(validate_from_str),
            ]
        )

        return core_schema.json_or_python_schema(
            json_schema=from_str_schema,
            python_schema=core_schema.union_schema(
                [
                    core_schema.is_instance_schema(Version),
                    from_str_schema,
                ]
            ),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return handler(core_schema.str_schema())


class PydanticArtifactType(BaseModel):
    id: str
    name: str


class PydanticProject(BaseModel):
    id: str
    name: str


class PydanticArtifactLocalResourceNeeds(BaseModel):
    """High-level execution resource requirements. Pretty sure all computers have these in some fashion."""

    max_cpu: float | None = None
    max_memory: float | None = None
    min_cpu: float | None = None
    min_memory: float | None = None


class PydanticArtifactExecution(BaseModel):
    local_resources: PydanticArtifactLocalResourceNeeds | None = None
    platform_resources: None = None


class PydanticArtifact(BaseModel):
    dockerfile: str | None = None
    dockerfile_stage: str | None = None
    execution: PydanticArtifactExecution | None = None
    id: str
    type: PydanticArtifactType


class PydanticBolt(BaseModel):
    artifacts: list[PydanticArtifact]
    project: PydanticProject
    version: Annotated[Version, _VersionPydanticAnnotation]

    @property
    def executable_artifacts(self) -> list[PydanticArtifact]:
        return [a for a in self.artifacts if a.execution]

    def to_dict(self) -> dict:
        return self.model_dump()


class PydanticExecutionEnvironment(BaseModel):
    hostname: str
    """Name of the environment host. Typically used for cluster name, server name, etc."""
    id: str
    """Unique identifier."""
    name: str
