from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from pydantic import Field, create_model

from ballista_sdk.adapters import InfrastructureAdapter
from ballista_sdk.api.v1 import (
    Artifact,
    Bolt,
    Environment,
    ExecutionProjectResourceNeed,
    ExecutionRequirements,
    ExecutionResourceNeed,
    ResourceProviderArtifactReference,
)


@dataclass
class BoltService:
    resources: Collection[ResourceProviderArtifactReference]

    def generate_bolt_class(self) -> type[Bolt]:
        # Gather all resources and arrange them under their projects
        project_resources = {}
        for resource, artifact_reference in self.resources:
            project = artifact_reference.project
            if project not in project_resources:
                project_resources[project] = {}

            requirements_model = resource.get_requirements_model(project)
            project_resources[project][resource.name] = (
                requirements_model,
                Field(default=None, description=resource.description),
            )

        # TODO: Add service connector resources

        project_resource_needs_fields = {}
        for project, resource_needs in project_resources:
            project_resource_need = create_model(
                f"Execution{project}ResourceNeed",
                **{resource_name: resource_field for resource_name, resource_field in resource_needs},
                __base__=ExecutionProjectResourceNeed,
            )
            project_resource_needs_fields[project] = (
                project_resource_need,
                Field(description="Resource need for a resource in PROJECT."),
            )

        dynamic_resource_need = create_model(
            ExecutionResourceNeed.__name__,
            **{
                project: project_resource_need_field
                for project, project_resource_need_field in project_resource_needs_fields
            },
            __base__=ExecutionResourceNeed,
        )

        dynamic_execution_requirements = create_model(
            "ExecutionRequirements",
            needs=(list[dynamic_resource_need], Field(default=[])),
            __base__=ExecutionRequirements,
        )

        dynamic_artifact = create_model(
            Artifact.__name__,
            execution=(dynamic_execution_requirements | None, Field(default=None, description="DYNAMIC EXECUTION")),
            __base__=Artifact,
        )

        dynamic_bolt = create_model(
            Bolt.__name__,
            artifacts=(list[dynamic_artifact], Field(description="DYNAMIC List of artifacts.", min_length=1)),
            __base__=Bolt,
        )

        return dynamic_bolt

    def create_bolt(self, project: str, version: str) -> Bolt:
        bolt_cls = self.generate_bolt_class()
        return bolt_cls(api_version="v1", artifacts=[], project=project, version=version)

    def get_bolt(self, bolt_data: dict[str, Any]) -> Bolt:
        bolt_cls = self.generate_bolt_class()
        return bolt_cls.model_validate(bolt_data)

    def deploy(self, environment: Environment, adapter: InfrastructureAdapter, bolt: Bolt, execution_parameters):
        # Environment checks

        # Make the deployment
        adapter.deploy(
            bolt=bolt,
            artifacts=bolt.executable_artifacts,
            environment=environment,
            execution_parameters=execution_parameters,
        )

    def create_resources(self):
        pass
