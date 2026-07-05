from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

import yaml

from ballista_sdk.adapters.exceptions import ArtifactNotFound, ResourceProviderNotFound, ServiceProviderNotFound
from ballista_sdk.adapters.resources.transports import (
    ResourceProviderTransport,
    RESTResourceProviderTransport,
)
from ballista_sdk.api.v1 import (
    Artifact,
    ArtifactReference,
    ArtifactType,
    Bolt,
    BoundSetting,
    Environment,
    ExecutableArtifact,
    ExecutionParameters,
    Project,
    ProvidedResourceWithArtifactReference,
    ProvidedServiceWithArtifactReference,
    ResourceProviderReference,
    ResourceRequirement,
    ResourceStatus,
    ServiceProviderReference,
    ServiceRequirement,
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
        artifact_resources: list[tuple[ArtifactReference, ResourceRequirement, Environment]] = []
        for artifact in artifacts:
            if artifact.execution and artifact.execution.requires.resources:
                artifact_reference = ArtifactReference(
                    project_name=bolt.project, artifact_name=artifact.name, version=bolt.version
                )
                artifact_resources.extend(
                    [(artifact_reference, r, environment) for r in artifact.execution.requires.resources]
                )

        if artifact_resources:
            for artifact, project_resource_requirement, environment in artifact_resources:
                provided_resource_with_artifact = self.resolve_resource_requirement(
                    environment, project_resource_requirement
                )
                requirement_model = provided_resource_with_artifact.provided_resource.get_requirements_model(
                    provided_resource_with_artifact.project_name
                )
                resource_requirement_data = project_resource_requirement.resource_requirement

                resource_requirement = requirement_model.model_validate(resource_requirement_data)

                await self._create_or_update_resource(
                    environment, artifact, provided_resource_with_artifact, resource_requirement
                )

        if True:
            commands = ["up", "--build", "--watch", "--remove-orphans"]
        else:
            commands = ["up", "--remove-orphans"]
        print(docker_compose_project.model_dump_json(indent=4, exclude_none=True, exclude_unset=True))
        self._call_compose(docker_compose_project, commands)

    def _destroy_resources(self, artifact: ArtifactReference, environment: Environment):
        pass

    async def _create_or_update_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        provided_resource_with_artifact: ProvidedResourceWithArtifactReference,
        resource_requirement,
    ):
        transport = self.resolve_resource_provider_transport(environment, provided_resource_with_artifact)
        if transport is None:
            return

        provided_resource = provided_resource_with_artifact.provided_resource
        resource_provider = provided_resource_with_artifact.resource_provider_reference

        # TODO: This should be universal
        resource_status = await transport.get_resource_status(environment, artifact, resource_requirement)
        if resource_status == ResourceStatus.NOT_FOUND:
            configs, secrets = await transport.provision_resource(environment, artifact, resource_requirement)
            setting_needed = True

        else:
            configs, secrets = await transport.update_resource(environment, artifact, resource_requirement)
            setting_needed = False

        # I'm sure these can be written with more clever code
        for config in provided_resource.configs:
            if config.name not in configs:
                if setting_needed:
                    raise Exception("NEEDED")
                else:
                    continue

            self.configs_adapter.write(
                environment,
                BoundSetting(config, artifact=artifact, resource_provider=resource_provider),
                configs[config.name],
            )

        for secret in provided_resource.secrets:
            if secret.name not in secrets:
                if setting_needed:
                    raise Exception("NEEDED")
                else:
                    continue

            self.secrets_adapter.write(
                environment,
                BoundSetting(secret, artifact=artifact, resource_provider=resource_provider),
                secrets[secret.name],
            )

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

    def list_resources(self, environment: Environment) -> list[ProvidedResourceWithArtifactReference]:
        """List available Resources with a providing ArtifactReference in the specified Environment."""

        references = []
        for bolt in self._bolts:
            references.extend(
                [
                    ProvidedResourceWithArtifactReference(resource, bolt.project, artifact.name, bolt.version)
                    for artifact in bolt.executable_artifacts
                    if artifact.execution.provides
                    for resource in artifact.execution.provides.resources
                ]
            )

        return references

    def list_services(self, environment: Environment) -> list[ProvidedServiceWithArtifactReference]:
        """List available Services with a providing ArtifactReference in the specified Environment."""

        references = []
        for bolt in self._bolts:
            references.extend(
                [
                    ProvidedServiceWithArtifactReference(service, bolt.project, artifact.name, bolt.version)
                    for artifact in bolt.executable_artifacts
                    if artifact.execution.provides
                    for service in artifact.execution.provides.services
                ]
            )

        return references

    def resolve_artifact_reference(
        self, environment: Environment, artifact_reference: ArtifactReference
    ) -> tuple[Bolt, Artifact]:
        for bolt in self._bolts:
            for artifact in bolt.artifacts:
                if (
                    artifact_reference.artifact_name == artifact.name
                    and artifact_reference.version == bolt.version
                    and artifact_reference.project_name == bolt.project
                ):
                    return bolt, artifact

        raise ArtifactNotFound(artifact_reference)

    def resolve_resource_provider_transport(
        self, environment: Environment, provided_resource_with_artifact: ProvidedResourceWithArtifactReference
    ) -> ResourceProviderTransport:
        resource = provided_resource_with_artifact.provided_resource

        if resource.transport:
            artifact_reference = provided_resource_with_artifact.artifact_reference
            bolt, artifact = self.resolve_artifact_reference(environment, artifact_reference)

            if rest_transport := resource.transport.rest:
                port = None

                if artifact.execution and artifact.execution.provides:
                    for service in artifact.execution.provides.services:
                        if service.name == rest_transport.service and service.http:
                            port = service.http
                            break

                if port is None:
                    raise ValueError("BAD SERVICE REFERENCE")

                ref_name = f"{artifact_reference.project_name}-{artifact_reference.artifact_name}"

                return RESTResourceProviderTransport(
                    ResourceProviderReference(artifact_reference.project_name, resource.name),
                    f"{ref_name}:{port}{rest_transport.path}",
                )

        raise ValueError()

    def resolve_resource_requirement(
        self, environment: Environment, resource_requirement: ResourceRequirement
    ) -> ProvidedResourceWithArtifactReference:
        # Get the project_name of the requirement points to and compare our resources
        requirement_project_name = resource_requirement.project_name
        requirement_resource_name = resource_requirement.resource_name

        for resource_provider_artifact_reference in self.list_resources(environment=environment):
            if (
                resource_provider_artifact_reference.project_name == requirement_project_name
                and resource_provider_artifact_reference.resource_provider_reference.resource_name
                == requirement_resource_name
            ):
                return resource_provider_artifact_reference

        raise ResourceProviderNotFound(
            ResourceProviderReference(project_name=requirement_project_name, resource_name=requirement_resource_name)
        )

    def resolve_service_requirement(
        self, environment: Environment, service_requirement: ServiceRequirement
    ) -> ProvidedServiceWithArtifactReference:
        # Get the project_name of the requirement points to and compare our services
        requirement_project_name = service_requirement.project_name
        requirement_service_name = service_requirement.service_name

        for service_provider_artifact_reference in self.list_services(environment=environment):
            if (
                service_provider_artifact_reference.project_name == requirement_project_name
                and service_provider_artifact_reference.service_provider_reference.service_name
                == requirement_service_name
            ):
                return service_provider_artifact_reference

        raise ServiceProviderNotFound(
            ServiceProviderReference(
                project_name=requirement_project_name,
                artifact_name=service_requirement.artifact_name,
                service_name=requirement_service_name,
            )
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
