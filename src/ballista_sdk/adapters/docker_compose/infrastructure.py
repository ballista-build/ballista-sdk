from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Sequence
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
    BoundSetting,
    ProvidedResourceWithArtifactReference,
    ProvidedServiceWithArtifactReference,
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
    ExecutionParameters,
    Project,
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

    def _call_compose(self, docker_compose_project: DockerComposeProject, commands: Sequence[str]):
        """Call docker compose."""
        # Create a temporary file filled with docker compose YAML and use that to call docker compose commands
        with tempfile.NamedTemporaryFile() as f:
            docker_compose_dict = docker_compose_project.model_dump(exclude_none=True, exclude_unset=True)
            yaml.dump(docker_compose_dict, stream=f, encoding="utf-8")

            args = ["docker", "compose", "--project-directory", os.getcwd(), "--file", f.name, *commands]
            subprocess.run(args)

    async def deploy(self, bolt: Bolt, environment: Environment):
        executable_artifacts = bolt.executable_artifacts
        resource_providers, service_providers = await resolve_artifact_requirements(
            self, environment, bolt, executable_artifacts
        )

        execution_parameters = await self.get_execution_parameters(bolt, environment)

        docker_compose_project = self.generate_docker_compose_project_from_bolt(
            environment=environment,
            bolt=bolt,
            artifacts=executable_artifacts,
            execution_parameters=execution_parameters,
            resource_providers=resource_providers,
            service_providers=service_providers,
        )

        # TODO: Move this so it's handled entirely by docker compose
        artifact_resources: list[tuple[ArtifactReference, ResourceRequirement, Environment]] = []
        for artifact in executable_artifacts:
            artifact_reference = ArtifactReference(
                project_name=bolt.project, artifact_name=artifact.name, version=bolt.version
            )

            if artifact.execution and artifact.execution.requires.resources:
                artifact_resources.extend(
                    [(artifact_reference, r, environment) for r in artifact.execution.requires.resources]
                )

        if artifact_resources:
            # We need to start the docker compose with only the "depends" profile so we can check resources
            self._call_compose(docker_compose_project, ["--profile", "depend", "up", "--build"])

            for artifact, project_resource_requirement, environment in artifact_resources:
                provided_resource_with_artifact = await self.resolve_resource_requirement(
                    environment, project_resource_requirement
                )
                requirement_model = provided_resource_with_artifact.provided_resource.get_requirements_model(
                    provided_resource_with_artifact.artifact_reference.project_name
                )
                resource_requirement_data = project_resource_requirement.resource_requirement.model_dump()

                resource_requirement = requirement_model.model_validate(resource_requirement_data)

                await self._create_or_update_resource(
                    environment, artifact, provided_resource_with_artifact, resource_requirement
                )

        commands = ["up", "--detach", "--remove-orphans"]

        self._call_compose(docker_compose_project, commands)

    async def get_execution_parameters(self, bolt: Bolt, environment: Environment) -> ExecutionParameters:
        return self.execution_parameters

    async def interact(self, bolt: Bolt, environment: Environment):
        executable_artifacts = bolt.executable_artifacts
        resource_providers, service_providers = await resolve_artifact_requirements(
            self, environment, bolt, executable_artifacts
        )

        docker_compose_project = self.generate_docker_compose_project_from_bolt(
            environment=environment,
            bolt=bolt,
            artifacts=executable_artifacts,
            execution_parameters=execution_parameters,
            resource_providers=resource_providers,
            service_providers=service_providers,
        )

        # TODO: Move this so it's handled entirely by docker compose
        artifact_resources: list[tuple[ArtifactReference, ResourceRequirement, Environment]] = []
        for artifact in executable_artifacts:
            artifact_reference = ArtifactReference(
                project_name=bolt.project, artifact_name=artifact.name, version=bolt.version
            )

            if artifact.execution and artifact.execution.requires.resources:
                artifact_resources.extend(
                    [(artifact_reference, r, environment) for r in artifact.execution.requires.resources]
                )

        if artifact_resources:
            # We need to start the docker compose with only the "depends" profile so we can check resources
            self._call_compose(docker_compose_project, ["--profile", "depend", "up", "--build"])

            for artifact, project_resource_requirement, environment in artifact_resources:
                provided_resource_with_artifact = await self.resolve_resource_requirement(
                    environment, project_resource_requirement
                )
                requirement_model = provided_resource_with_artifact.provided_resource.get_requirements_model(
                    provided_resource_with_artifact.artifact_reference.project_name
                )
                resource_requirement_data = project_resource_requirement.resource_requirement.model_dump()

                resource_requirement = requirement_model.model_validate(resource_requirement_data)

                await self._create_or_update_resource(
                    environment, artifact, provided_resource_with_artifact, resource_requirement
                )

        commands = ["up", "--build", "--watch", "--remove-orphans"]

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

    async def list_artifact_types(self, environments: Sequence[Environment]) -> list[ArtifactType]:
        return [ArtifactType(name="docker_image", title="Docker Image")]

    async def list_executable_artifacts(
        self,
        environments: Sequence[Environment],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
    ) -> list[ArtifactReference]:
        return BoltInspector.list_executable_artifacts(
            self._bolts, project_names=project_names, artifact_names=artifact_names
        )

    async def list_bolts(
        self, environments: Sequence[Environment], *, project_names: Sequence[str] | None = None
    ) -> list[Bolt]:
        return BoltInspector.list_bolts(self._bolts, project_names=project_names)

    async def list_projects(
        self, environments: Sequence[Environment], *, project_names: Sequence[str] | None = None
    ) -> list[Project]:
        return BoltInspector.list_projects(self._bolts, project_names=project_names)

    async def list_provided_resources(
        self,
        environments: Sequence[Environment],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        resource_names: Sequence[str] | None = None,
    ) -> list[ProvidedResourceWithArtifactReference]:
        """List Provided Resources with a providing ArtifactReference in the specified Environment."""

        return BoltInspector.list_provided_resources(
            self._bolts, project_names=project_names, artifact_names=artifact_names, resource_names=resource_names
        )

    async def list_provided_services(
        self,
        environments: Sequence[Environment],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        service_names: Sequence[str] | None = None,
        service_types: Sequence[ServiceType] | None = None,
    ) -> list[ProvidedServiceWithArtifactReference]:
        """List Provided Services with a providing ArtifactReference in the specified Environment."""

        return BoltInspector.list_provided_services(
            self._bolts, project_names=project_names, artifact_names=artifact_names, service_names=service_names
        )

    async def list_resources(
        self,
        environments: Sequence[Environment],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        resource_names: Sequence[str] | None = None,
        resource_statuses: Sequence[ResourceStatus] | None = None,
    ) -> list[tuple[ArtifactReference, ProvidedResourceReference, ResourceStatus]]:
        """List Resources in specified Environment."""
        return BoltInspector.list_resources(
            self._bolts,
            project_names=project_names,
            artifact_names=artifact_names,
            resource_names=resource_names,
            resource_statuses=resource_statuses,
        )

    async def list_services(
        self,
        environments: Sequence[Environment],
        *,
        project_names: Sequence[str] | None = None,
        artifact_names: Sequence[str] | None = None,
        service_names: Sequence[str] | None = None,
        service_types: Sequence[ServiceType] | None = None,
    ) -> list[tuple[ArtifactReference, ProvidedServiceReference, ServiceType]]:
        return BoltInspector.list_services(
            self._bolts,
            project_names=project_names,
            artifact_names=artifact_names,
            service_names=service_names,
            service_types=service_types,
        )

    async def resolve_artifact_reference(
        self, environment: Environment, artifact_reference: ArtifactReference
    ) -> tuple[Bolt, Artifact]:
        return BoltInspector.resolve_artifact_reference(self._bolts, artifact_reference)

    async def resolve_resource_requirement(
        self, environment: Environment, resource_requirement: ResourceRequirement
    ) -> ProvidedResourceWithArtifactReference:
        # Get the project_name of the requirement points to and compare our resources
        requirement_project_name = resource_requirement.project_name
        requirement_resource_name = resource_requirement.resource_name

        provided_resources = await self.list_provided_resources(
            [environment], project_names=[requirement_project_name], resource_names=[requirement_resource_name]
        )
        for resource_provider_artifact_reference in provided_resources:
            return resource_provider_artifact_reference

        raise ProvidedResourceNotFound(
            ProvidedResourceReference(project_name=requirement_project_name, resource_name=requirement_resource_name)
        )

    async def resolve_service_requirement(
        self, environment: Environment, service_requirement: ServiceRequirement
    ) -> ProvidedServiceWithArtifactReference:
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
        for service_provider_artifact_reference in provided_services:
            return service_provider_artifact_reference

        raise ProvidedServiceNotFound(
            ProvidedServiceReference(
                project_name=requirement_project_name,
                artifact_name=requirement_artifact_name,
                service_name=requirement_service_name,
            )
        )

    async def teardown(self, bolt: Bolt, environment: Environment):
        executable_artifacts = bolt.executable_artifacts
        resource_providers, service_providers = await resolve_artifact_requirements(
            self, environment, bolt, executable_artifacts
        )

        execution_parameters = await self.get_execution_parameters(bolt, environment)
        docker_compose_project = self.generate_docker_compose_project_from_bolt(
            environment=environment,
            bolt=bolt,
            artifacts=executable_artifacts,
            execution_parameters=execution_parameters,
            resource_providers=resource_providers,
            service_providers=service_providers,
        )

        self._call_compose(docker_compose_project, ["down"])

    async def transport_resource_provider(
        self, environment: Environment, provided_resource_with_artifact: ProvidedResourceWithArtifactReference
    ) -> ResourceProviderTransport:
        resource = provided_resource_with_artifact.provided_resource

        if resource.transport:
            artifact_reference = provided_resource_with_artifact.artifact_reference
            bolt, artifact = await self.resolve_artifact_reference(environment, artifact_reference)

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
