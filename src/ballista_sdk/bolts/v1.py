from dataclasses import dataclass

from ballista_sdk.api.v1 import Bolt


@dataclass
class BoltV1Factory:
    """Factory to create v1 Bolts that are valid to execute in specified Environment with specified InfrastructureAdapter."""

    def create_bolt(self, project: str, version: str) -> Bolt:
        return Bolt(artifacts=[], project=project, version=version)

    # def generate_bolt_class(self) -> type[Bolt]:
    #     # Gather all resources and arrange them under their projects
    #     resource_name_requirement_fields = {}

    #     # Create the requirements/configuration model for Provided Resources
    #     for resource, project_name, _, _ in self.adapter.list_resources(self.environment):
    #         requirements_model = resource.get_requirements_model(project_name)
    #         field = (
    #             requirements_model | None,
    #             Field(default=None, description=resource.description),
    #         )
    #         resource_name_requirement_fields.setdefault(project_name, {})
    #         resource_name_requirement_fields[project_name][resource.name] = field

    #     # TODO: Add service connector resources

    #     # Create a container for each Project's provided resources
    #     project_resource_needs_fields = {}
    #     for (
    #         project,
    #         resource_requirement_fields,
    #     ) in resource_name_requirement_fields.items():
    #         resource_fields = {
    #             resource_name: resource_field for resource_name, resource_field in resource_requirement_fields.items()
    #         }

    #         model = create_model(
    #             f"{project}ResourceRequirementName",
    #             **resource_fields,
    #             __base__=BaseProjectResourceRequirementName,
    #         )

    #         # Store this project to add to the system's provided resources
    #         project_resource_needs_fields[project] = (
    #             model | None,
    #             Field(
    #                 default=None,
    #                 description=f"Resource requirement for a resource in {project}.",
    #             ),
    #         )

    #     # Create top-level resource container, holding the project name
    #     dynamic_project_resource_requirement = create_model(
    #         ResourceRequirementProject.__name__,
    #         **{
    #             project: project_resource_need_field
    #             for project, project_resource_need_field in project_resource_needs_fields.items()
    #         },
    #         __base__=ResourceRequirementProject,
    #     )

    #     dynamic_execution_requirements = create_model(
    #         "ExecutionRequirements",
    #         resources=(list[dynamic_project_resource_requirement], Field(default=[])),
    #         __base__=ExecutionRequirements,
    #     )

    #     dynamic_artifact = create_model(
    #         Artifact.__name__,
    #         execution=(
    #             dynamic_execution_requirements | None,
    #             Field(default=None, description="DYNAMIC EXECUTION"),
    #         ),
    #         __base__=Artifact,
    #     )

    #     dynamic_bolt = create_model(
    #         Bolt.__name__,
    #         artifacts=(
    #             list[dynamic_artifact],
    #             Field(description="DYNAMIC List of artifacts.", min_length=1),
    #         ),
    #         __base__=Bolt,
    #     )

    #     return dynamic_bolt

    def get_bolt(self, data) -> Bolt:
        return Bolt.model_validate(data)
