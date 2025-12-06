from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, create_model
from pydantic.fields import FieldInfo

from ballista_sdk.adapters import ExecutableArtifactSetting, InfrastructureAdapter
from ballista_sdk.api.v1 import (
    Artifact,
    Bolt,
    Environment,
    ExecutableArtifact,
    ExecutionParameters,
    ExecutionRequirements,
    ProjectResourceRequirement,
    ResourceProviderArtifactReference,
    ResourceRequirement,
)

RequirementField = tuple[type[BaseModel] | None, Any]
ProjectResourceRequirements = dict[str, RequirementField]


@dataclass
class BoltService:
    resources: Collection[ResourceProviderArtifactReference]

    def generate_bolt_class(self) -> type[Bolt]:
        # Gather all resources and arrange them under their projects
        project_resource_requirement_fields: dict[str, ProjectResourceRequirements] = {}

        for resource, artifact_reference in self.resources:
            project = artifact_reference.project
            if project not in project_resource_requirement_fields:
                project_resource_requirement_fields[project] = {}

            requirements_model = resource.get_requirements_model(project)
            field: RequirementField = (
                requirements_model | None,
                Field(default=None, description=resource.description),
            )
            project_resource_requirement_fields[project][resource.name] = field

        # TODO: Add service connector resources

        project_resource_needs_fields: ProjectResourceRequirements = {}
        for (
            project,
            resource_requirement_fields,
        ) in project_resource_requirement_fields.items():
            resource_fields = {
                resource_name: resource_field for resource_name, resource_field in resource_requirement_fields.items()
            }

            model = create_model(
                f"{project}ResourceRequirement",
                **resource_fields,
                __base__=ResourceRequirement,
            )
            project_resource_needs_fields[project] = (
                model | None,
                Field(default=None, description=f"Resource requirement for a resource in {project}."),
            )

        dynamic_project_resource_requirement = create_model(
            ProjectResourceRequirement.__name__,
            **{
                project: project_resource_need_field
                for project, project_resource_need_field in project_resource_needs_fields.items()
            },
            __base__=ProjectResourceRequirement,
        )

        dynamic_execution_requirements = create_model(
            "ExecutionRequirements",
            resources=(list[dynamic_project_resource_requirement], Field(default=[])),
            __base__=ExecutionRequirements,
        )

        dynamic_artifact = create_model(
            Artifact.__name__,
            execution=(
                dynamic_execution_requirements | None,
                Field(default=None, description="DYNAMIC EXECUTION"),
            ),
            __base__=Artifact,
        )

        dynamic_bolt = create_model(
            Bolt.__name__,
            artifacts=(
                list[dynamic_artifact],
                Field(description="DYNAMIC List of artifacts.", min_length=1),
            ),
            __base__=Bolt,
        )

        return dynamic_bolt

    def create_bolt(self, project: str, version: str) -> Bolt:
        bolt_cls = self.generate_bolt_class()
        return bolt_cls(api_version="v1", artifacts=[], project=project, version=version)

    def get_bolt(self, bolt_data: dict[str, Any]) -> Bolt:
        bolt_cls = self.generate_bolt_class()
        return bolt_cls.model_validate(bolt_data)

    def get_artifact_settings(
        self,
        adapter: InfrastructureAdapter,
        environment: Environment,
        artifact: ExecutableArtifact,
    ) -> tuple[list, list]:
        if not artifact.execution:
            return [], []

        configs = [
            ExecutableArtifactSetting(
                environment=environment,
                project=1,
                artifact=artifact,
                setting=config,
                instance_ids=[],
            )
            for config in artifact.execution.configs
        ]

        secrets = [
            ExecutableArtifactSetting(
                environment=environment,
                project=1,
                artifact=artifact,
                setting=secret,
                instance_ids=[],
            )
            for secret in artifact.execution.secrets
        ]

        for resource_requirement in artifact.execution.resources:
            resource, provider_artifact_reference = adapter.resolve_resource_requirement(
                resource_requirement, environment
            )

        return configs, secrets

    def deploy(
        self,
        environment: Environment,
        adapter: InfrastructureAdapter,
        bolt: Bolt,
        execution_parameters: ExecutionParameters,
    ):
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
