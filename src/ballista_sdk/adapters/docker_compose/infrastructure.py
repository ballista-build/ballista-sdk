from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

import yaml

from ballista_sdk.adapters.exceptions import UnknownArtifact, UnknownResource
from ballista_sdk.adapters.resources.transports import (
    ResourceProviderTransport,
    RESTResourceProviderTransport,
)
from ballista_sdk.api.v1 import (
    Artifact,
    ArtifactReference,
    ArtifactType,
    Bolt,
    Environment,
    ExecutableArtifact,
    ExecutionParameters,
    Project,
    ResourceProviderReference,
    ResourceReference,
    ResourceRequirement,
    ResourceRequirementProject,
    ResourceStatus,
)

from .generation import BaseDockerComposeInfrastructureAdapter, DockerComposeProject
from .settings import DockerComposeSettingsAdapter


@dataclass
class DockerComposeInfrastructureAdapter(BaseDockerComposeInfrastructureAdapter):
    _bolts: list[Bolt] = field(default_factory=list)
    _settings_adapter: DockerComposeSettingsAdapter = field(default_factory=DockerComposeSettingsAdapter, init=False)

    @property
    def name(self) -> Literal["docker-compose"]:
        return "docker-compose"

    @property
    def configs_adapter(self) -> DockerComposeSettingsAdapter:
        return self._settings_adapter

    @property
    def secrets_adapter(self) -> DockerComposeSettingsAdapter:
        return self._settings_adapter

    def _call_compose(self, docker_compose_project: DockerComposeProject, commands: Sequence[str]):
        """Call docker compose."""
        # Create a temporary file filled with docker compose YAML and use that to call docker compose commands
        with tempfile.NamedTemporaryFile() as f:
            docker_compose_dict = docker_compose_project.model_dump(exclude_none=True, exclude_unset=True)
            yaml.dump(docker_compose_dict, stream=f, encoding="utf-8")

            args = ["docker", "compose", "--project-directory", os.getcwd(), "--file", f.name, *commands]
            subprocess.run(args)

    async def deploy(
        self,
        bolt: Bolt,
        artifacts: Sequence[ExecutableArtifact],
        environment: Environment,
        execution_parameters: ExecutionParameters,
    ):
        docker_compose_project = self.generate_docker_compose_project_from_bolt(
            environment=environment,
            bolt=bolt,
            artifacts=artifacts,
            execution_parameters=execution_parameters,
        )

        # Do some resource shit
        artifact_resources = []
        for artifact in artifacts:
            if artifact.execution and artifact.execution.resources:
                artifact_reference = ArtifactReference(
                    project_name=bolt.project, artifact_name=artifact.name, version=bolt.version
                )
                artifact_resources.extend([(artifact_reference, r, environment) for r in artifact.execution.resources])

        if artifact_resources:
            for artifact, project_resource_requirement, environment in artifact_resources:
                resource_provider_reference = self.resolve_resource_requirement(
                    project_resource_requirement, environment
                )
                await self._create_or_update_resource(
                    artifact,
                    resource_provider_reference,
                    project_resource_requirement.resource_requirement,
                    environment,
                )

        if True:
            commands = ["up", "--build", "--watch", "--remove-orphans"]
        else:
            commands = ["up", "--remove-orphans"]
        print(docker_compose_project.model_dump_json(indent=4, exclude_none=True, exclude_unset=True))
        self._call_compose(docker_compose_project, commands)

    def _get_resource_provider_transport(
        self, resource_provider: ResourceProviderReference
    ) -> ResourceProviderTransport | None:
        resource = resource_provider.resource

        if resource.transport:
            if rest_transport := resource.transport.rest:
                port = rest_transport.port
                if rest_transport.service:
                    # Lookup port
                    pass

                ref_name = f"{resource_provider.project_name}-{resource_provider.artifact_name}"

                return RESTResourceProviderTransport(
                    resource_provider.project_name, resource.name, f"{ref_name}:{port}{rest_transport.path}"
                )

    def _destroy_resources(self, artifact: ArtifactReference, environment: Environment):
        pass

    async def _create_or_update_resource(
        self,
        artifact: ArtifactReference,
        resource_provider: ResourceProviderReference,
        resource_requirement: ResourceRequirement,
        environment: Environment,
    ):
        transport = self._get_resource_provider_transport(resource_provider)
        if transport is None:
            return

        resource_status = await transport.get_resource_status(artifact, resource_requirement, environment)
        if resource_status == ResourceStatus.NOT_FOUND:
            await transport.provision_resource(artifact, resource_requirement, environment)
        else:
            await transport.update_resource(artifact, resource_requirement, environment)

    def list_artifact_types(self, environment: Environment) -> list[ArtifactType]:
        return [ArtifactType(name="docker_image", title="Docker Image")]

    def list_executable_artifacts(self, environment: Environment) -> list[ArtifactReference]:
        references = []

        for bolt in self._bolts:
            references.extend(
                [ArtifactReference(bolt.project, artifact.name, bolt.version) for artifact in bolt.executable_artifacts]
            )

        return references

    def list_projects(self, environments: Sequence[Environment]) -> list[Project]:
        return []

    def list_project_bolts(self, project: Project, environments: Sequence[Environment]) -> list[Bolt]:
        return []

    def list_resources(self, environment: Environment) -> list[ResourceProviderReference]:
        """List available Resources with a providing ArtifactReference in the specified Environment."""

        references = []
        for bolt in self._bolts:
            references.extend(
                [
                    ResourceProviderReference(resource, bolt.project, artifact.name, bolt.version)
                    for artifact in bolt.executable_artifacts
                    for resource in artifact.provides
                ]
            )

        return references

    def resolve_artifact_reference(
        self, artifact_reference: ArtifactReference, environment: Environment
    ) -> tuple[Bolt, Artifact]:
        for bolt in self._bolts:
            for artifact in bolt.artifacts:
                if (
                    artifact_reference.artifact_name == artifact.name
                    and artifact_reference.version == bolt.version
                    and artifact_reference.project_name == bolt.project
                ):
                    return bolt, artifact

        raise UnknownArtifact(artifact_reference)

    def resolve_resource_requirement(
        self, resource_requirement: ResourceRequirementProject, environment: Environment
    ) -> ResourceProviderReference:
        # Get the project_name of the requirement points to and compare our resources
        requirement_project_name = resource_requirement.which()
        requirement_resource_name = resource_requirement.resource_name

        for resource_provider_artifact_reference in self.list_resources(environment=environment):
            if (
                resource_provider_artifact_reference.project_name == requirement_project_name
                and resource_provider_artifact_reference.resource.name == requirement_resource_name
            ):
                return resource_provider_artifact_reference

        raise UnknownResource(
            ResourceReference(project_name=requirement_project_name, resource_name=requirement_resource_name)
        )

    async def teardown(
        self,
        bolt: Bolt,
        artifacts: Sequence[ExecutableArtifact],
        environment: Environment,
        execution_parameters: ExecutionParameters,
    ):
        docker_compose_project = self.generate_docker_compose_project_from_bolt(
            environment=environment,
            bolt=bolt,
            artifacts=artifacts,
            execution_parameters=execution_parameters,
        )

        self._call_compose(docker_compose_project, ["down"])
