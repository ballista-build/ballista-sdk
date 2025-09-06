from __future__ import annotations

import inspect
from collections.abc import Collection
from typing import Annotated, Any

from pydantic import Field, create_model

from ballista_sdk.api.v1 import models

from ..types import BoltService as BaseBoltService
from ..types import Resource, ResourceWithArtifactProvider


class BoltService(BaseBoltService):
    resources: Collection[ResourceWithArtifactProvider]

    def __init__(self, resources: Collection[ResourceWithArtifactProvider]):
        self.resources = resources

    def generate_bolt_class(self) -> type[models.Bolt]:
        resource_fields = {
            resource.id: Annotated[
                _create_resource_dependency_model(resource),
                Field(default=None, description=f'Dependency on a "{resource.name}" resource.'),
            ]
            for resource, _ in self.resources
        }

        # Resources
        dynamic_resource_dependency = create_model(
            models.ArtifactExecutionResourceDependency.__name__,
            __base__=models.ArtifactExecutionResourceDependency,
            **resource_fields,
        )

        dynamic_artifact_execution_requirements = create_model(
            models.ArtifactExecutionRequirements.__name__,
            resources=Annotated[
                list[dynamic_resource_dependency] | None,
                Field(default=None, description="List of Resources required for execution."),
            ],
            __base__=models.ArtifactExecutionRequirements,
        )

        dynamic_artifact = create_model(
            models.Artifact.__name__,
            execution=Annotated[
                dynamic_artifact_execution_requirements | None, Field(default=None, description="DYNAMIC EXECUTION")
            ],
            __base__=models.Artifact,
        )

        dynamic_bolt = create_model(
            models.Bolt.__name__,
            artifacts=Annotated[list[dynamic_artifact], Field(description="DYNAMIC List of artifacts.", min_length=1)],
            __base__=models.Bolt,
        )

        return dynamic_bolt

    def create_bolt(self, project_id: str) -> models.Bolt:
        bolt_cls = self.generate_bolt_class()
        return bolt_cls(artifacts=[], project_id=project_id, version="0.1.0")

    def get_bolt(self, bolt_data: dict[str, Any]) -> models.Bolt:
        bolt_cls = self.generate_bolt_class()
        return bolt_cls.model_validate(bolt_data)


def _create_resource_dependency_model(resource: Resource) -> type[models.ArtifactExecutionResourceDependency]:
    # TODO: THIS IS REAL JANK
    annotations = inspect.get_annotations(resource.requirements)
    requirement_fields = {}

    for prop, annotation in annotations.items():
        field = Field(description="DESCRIPTION")
        if hasattr(resource.requirements, prop):
            field.default = getattr(resource.requirements, prop)

        requirement_fields[prop] = Annotated[annotation, field]

    return create_model(
        f"ArtifactExecution{resource.name}Resource", **requirement_fields, __base__=models.BaseArtifactExecutionResource
    )
