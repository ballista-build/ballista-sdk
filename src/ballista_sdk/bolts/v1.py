from dataclasses import dataclass

from pydantic import Field, create_model

from ballista_sdk.adapters.infrastructure import InfrastructureAdapter
from ballista_sdk.api.v1 import (
    Artifact,
    Bolt,
    Environment,
    ExecutionRequirements,
    ProjectResourceRequirement,
    ResourceRequirement,
)


@dataclass
class BoltV1Factory:
    """Factory to create v1 Bolts that are valid to execute in specified Environment with specified InfrastructureAdapter."""

    environment: Environment
    adapter: InfrastructureAdapter

    def create_bolt(self, project: str, version: str) -> Bolt:
        bolt_class = self.generate_bolt_class()

        return bolt_class(artifacts=[], project=project, version=version)

    def generate_bolt_class(self) -> type[Bolt]:
        # Gather all resources and arrange them under their projects
        project_resource_requirement_fields = {}

        for resource, project, _, _ in self.adapter.list_resources(self.environment):
            if project not in project_resource_requirement_fields:
                project_resource_requirement_fields[project] = {}

            requirements_model = resource.get_requirements_model(project)
            field = (
                requirements_model | None,
                Field(default=None, description=resource.description),
            )
            project_resource_requirement_fields[project][resource.name] = field

        # TODO: Add service connector resources

        project_resource_needs_fields = {}
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
                Field(
                    default=None,
                    description=f"Resource requirement for a resource in {project}.",
                ),
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

    def get_bolt(self, data) -> Bolt:
        bolt_class = self.generate_bolt_class()

        return bolt_class.model_validate(data)
