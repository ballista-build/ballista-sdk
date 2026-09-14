from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Literal

import yaml

from ballista_sdk.adapters.exceptions import (
    ProvidedResourceNotFound,
    ProvidedResourceReference,
    ProvidedServiceNotFound,
    ProvidedServiceReference,
)
from ballista_sdk.adapters.infrastructure import (
    BoltInspector,
    InfrastructureAdapter,
    resolve_artifact_requirements,
)
from ballista_sdk.adapters.primitives import (
    ArtifactReference,
    BoltReference,
    BoundSetting,
    ProjectReference,
    ResolvedProvidedResource,
    ResolvedProvidedService,
)
from ballista_sdk.adapters.resources.transports import (
    ResourceProviderTransport,
    RESTResourceProviderTransport,
)
from ballista_sdk.api.v1 import (
    Artifact,
    ArtifactType,
    Bolt,
    Environment,
    EnvironmentTier,
    ExecutionParameters,
    ResourceRequirement,
    ResourceStatus,
    ServiceRequirement,
    ServiceType,
)

from .generation import DockerComposeInfrastructureGenerator, DockerComposeProject
from .settings import DockerComposeSettingsAdapter


@dataclass
class DockerComposeInfrastructureAdapter(InfrastructureAdapter, DockerComposeInfrastructureGenerator):
    execution_parameters: ExecutionParameters = field(default_factory=ExecutionParameters)
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

    def _call_compose(self, docker_compose_project: DockerComposeProject, commands: list[str]):
        """Call docker compose."""
        # Create a temporary file filled with docker compose YAML and use that to call docker compose commands
        with tempfile.NamedTemporaryFile() as f:
            docker_compose_dict = docker_compose_project.model_dump(exclude_none=True, exclude_unset=True)
            yaml.dump(docker_compose_dict, stream=f, encoding="utf-8", indent=2)

            args = ["docker", "compose", "--project-directory", os.getcwd(), "--file", f.name, *commands]
            subprocess.run(args)

    async def deploy(self, bolt: Bolt, environment: Environment):
        resource_providers, service_providers = await resolve_artifact_requirements(self, environment, bolt)

        execution_parameters = await self.get_execution_parameters(bolt, environment)

        docker_compose_project = self.generate_docker_compose_project_from_bolt(
            environment=environment,
            bolt=bolt,
            execution_parameters=execution_parameters,
            resource_providers=resource_providers,
            service_providers=service_providers,
        )

        commands = ["up", "--detach", "--remove-orphans"]

        self._call_compose(docker_compose_project, commands)

    async def get_execution_parameters(self, bolt: Bolt, environment: Environment) -> ExecutionParameters:
        return self.execution_parameters

    def get_development_environment(self, name: str, title: str) -> Environment:
        return Environment(name=name, tier=EnvironmentTier.DEVELOPMENT, title=title)

    async def interact(self, bolt: Bolt, environment: Environment):
        resource_providers, service_providers = await resolve_artifact_requirements(self, environment, bolt)

        execution_parameters = await self.get_execution_parameters(bolt, environment)

        docker_compose_project = self.generate_docker_compose_project_from_bolt(
            environment=environment,
            bolt=bolt,
            execution_parameters=execution_parameters,
            resource_providers=resource_providers,
            service_providers=service_providers,
        )

        commands = ["up", "--build", "--watch", "--remove-orphans"]

        self._call_compose(docker_compose_project, commands)

    def _destroy_resources(self, artifact: ArtifactReference, environment: Environment):
        pass

    async def _create_or_update_resource(
        self,
        environment: Environment,
        artifact: ArtifactReference,
        provided_resource_with_artifact: ResolvedProvidedResource,
        resource_requirement,
    ):
        try:
            transport = await self.transport_resource_provider(environment, provided_resource_with_artifact)
        except Exception:
            raise

        provided_resource = provided_resource_with_artifact.provided_resource
        provided_resource_reference = provided_resource_with_artifact.provided_resource_reference

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
                BoundSetting(config, artifact=artifact, provided_resource=provided_resource_reference),
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
                BoundSetting(secret, artifact=artifact, provided_resource=provided_resource_reference),
                secrets[secret.name],
            )

    async def list_artifacts(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        buildable: bool | None = None,
        executable: bool | None = None,
    ) -> list[ArtifactReference]:
        return BoltInspector.list_artifacts(
            self._bolts,
            project_names=project_names,
            artifact_names=artifact_names,
            buildable=buildable,
            executable=executable,
        )

    async def list_artifact_types(self, environments: Collection[Environment]) -> list[ArtifactType]:
        return [ArtifactType(name="docker_image", title="Docker Image")]

    async def list_bolts(
        self, environments: Collection[Environment], *, project_names: Collection[str] | None = None
    ) -> list[BoltReference]:
        return BoltInspector.list_bolts(self._bolts, project_names=project_names)

    async def list_projects(
        self, environments: Collection[Environment], *, project_names: Collection[str] | None = None
    ) -> list[ProjectReference]:
        return BoltInspector.list_projects(self._bolts, project_names=project_names)

    async def list_provided_resources(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        resource_names: Collection[str] | None = None,
    ) -> list[ResolvedProvidedResource]:
        """List Provided Resources with a providing ArtifactReference in the specified Environment."""

        return BoltInspector.list_provided_resources(
            self._bolts, project_names=project_names, artifact_names=artifact_names, resource_names=resource_names
        )

    async def list_provided_services(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        service_names: Collection[str] | None = None,
        service_types: Collection[ServiceType] | None = None,
    ) -> list[ResolvedProvidedService]:
        """List Provided Services with a providing ArtifactReference in the specified Environment."""

        return BoltInspector.list_provided_services(
            self._bolts, project_names=project_names, artifact_names=artifact_names, service_names=service_names
        )

    async def list_resource_requirements(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        resource_project_names: Collection[str] | None = None,
        resource_names: Collection[str] | None = None,
        resource_statuses: Collection[ResourceStatus] | None = None,
    ) -> list[tuple[ArtifactReference, ProvidedResourceReference, ResourceStatus]]:
        """List Resources in specified Environment."""
        return BoltInspector.list_resource_requirements(
            self._bolts,
            project_names=project_names,
            artifact_names=artifact_names,
            resource_project_names=resource_project_names,
            resource_names=resource_names,
            resource_statuses=resource_statuses,
        )

    async def list_service_requirements(
        self,
        environments: Collection[Environment],
        *,
        project_names: Collection[str] | None = None,
        artifact_names: Collection[str] | None = None,
        service_project_names: Collection[str] | None = None,
        service_artifact_names: Collection[str] | None = None,
        service_names: Collection[str] | None = None,
        service_types: Collection[ServiceType] | None = None,
    ) -> list[tuple[ArtifactReference, ProvidedServiceReference]]:
        return BoltInspector.list_service_requirements(
            self._bolts,
            project_names=project_names,
            artifact_names=artifact_names,
            service_project_names=service_project_names,
            service_artifact_names=service_artifact_names,
            service_names=service_names,
            service_types=service_types,
        )

    async def resolve_artifact_reference(
        self, environment: Environment, artifact_reference: ArtifactReference
    ) -> Artifact:
        return BoltInspector.resolve_artifact_reference(self._bolts, artifact_reference)

    async def resolve_resource_requirement(
        self, environment: Environment, resource_requirement: ResourceRequirement
    ) -> ResolvedProvidedResource:
        # Get the project_name of the requirement points to and compare our resources
        requirement_project_name = resource_requirement.project_name
        requirement_resource_name = resource_requirement.resource_name

        provided_resources = await self.list_provided_resources(
            [environment], project_names=[requirement_project_name], resource_names=[requirement_resource_name]
        )
        for resolved_provided_resource in provided_resources:
            return resolved_provided_resource

        raise ProvidedResourceNotFound(
            ProvidedResourceReference(project_name=requirement_project_name, resource_name=requirement_resource_name)
        )

    async def resolve_service_requirement(
        self, environment: Environment, service_requirement: ServiceRequirement
    ) -> ResolvedProvidedService:
        # Get the project_name of the requirement points to and compare our services
        requirement_project_name = service_requirement.project_name
        requirement_artifact_name = service_requirement.artifact_name
        requirement_service_name = service_requirement.service_name

        provided_services = await self.list_provided_services(
            [environment],
            project_names=[requirement_project_name],
            artifact_names=[requirement_artifact_name],
            service_names=[requirement_service_name],
        )
        for resolved_provided_service in provided_services:
            return resolved_provided_service

        raise ProvidedServiceNotFound(
            ProvidedServiceReference(
                project_name=requirement_project_name,
                artifact_name=requirement_artifact_name,
                service_name=requirement_service_name,
            )
        )

    async def remove(self, bolt: Bolt, environment: Environment):
        resource_providers, service_providers = await resolve_artifact_requirements(self, environment, bolt)

        execution_parameters = await self.get_execution_parameters(bolt, environment)
        docker_compose_project = self.generate_docker_compose_project_from_bolt(
            environment=environment,
            bolt=bolt,
            execution_parameters=execution_parameters,
            resource_providers=resource_providers,
            service_providers=service_providers,
        )

        self._call_compose(docker_compose_project, ["down"])

    async def transport_resource_provider(
        self, environment: Environment, resolved_provided_resource: ResolvedProvidedResource
    ) -> ResourceProviderTransport:
        resource = resolved_provided_resource.provided_resource

        if resource.transport:
            artifact_reference = resolved_provided_resource.artifact_reference
            artifact = await self.resolve_artifact_reference(environment, artifact_reference)

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
                    ProvidedResourceReference(artifact_reference.project_name, resource.name),
                    f"http://{ref_name}:{port}{rest_transport.path}",
                )

        raise ValueError()
