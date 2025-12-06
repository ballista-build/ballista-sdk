from __future__ import annotations

import os
import subprocess
import tempfile
from collections import deque
from collections.abc import Collection
from typing import Any, ClassVar, Literal

import yaml
from pydantic import BaseModel

from ballista_sdk.adapters.exceptions import UnknownArtifact, UnknownResourceRequirement
from ballista_sdk.adapters.settings import ExecutableArtifactSetting, SettingsAdapter, SettingValue
from ballista_sdk.api.v1 import (
    Artifact,
    ArtifactExecutionParameters,
    ArtifactReference,
    ArtifactType,
    Bolt,
    Environment,
    ExecutableArtifact,
    ExecutionParameters,
    HealthcheckProbe,
    Project,
    ProjectResourceRequirement,
    ResourceProviderArtifactReference,
    ServiceRequirement,
)


class DockerComposeServiceVolume(BaseModel):
    source: str | None = None
    target: str
    tmpfs: dict | None = None
    type: Literal["bind", "volume", "tmpfs", "npipe"]
    volume: dict | None = None


class DockerComposeService(BaseModel):
    build: dict[str, Any] | None = None
    configs: list[str] | None = None
    container_name: str | None = None
    depends_on: dict[str, dict[str, str]] | None = None
    deploy: dict[str, Any] | None = None
    develop: dict[str, Any] | None = None
    environment: dict[str, Any] | None = None
    env_file: list[dict] | None = None
    healthcheck: dict[str, Any] | None = None
    image: str | None = None
    networks: list[str] = []
    ports: list[dict[str, Any]] = []
    secrets: list[str] | None = None
    volumes: list[DockerComposeServiceVolume] = []


class DockerComposeProjectVolume(BaseModel):
    driver: str
    name: str
    """Human-readable volume name. Not the volume identifier."""


class DockerComposeProject(BaseModel):
    configs: dict[str, Any] | None = None
    name: str
    networks: dict[str, dict[str, Any]]
    secrets: dict[str, Any] | None = None
    services: dict[str, DockerComposeService]
    volumes: dict[str, DockerComposeProjectVolume] = {}


def _generate_docker_compose_project_from_bolt(
    adapter: DockerComposeInfrastructureAdapter,
    environment: Environment,
    bolt: Bolt,
    artifacts: Collection[ExecutableArtifact],
    execution_parameters: ExecutionParameters,
) -> DockerComposeProject:
    """Generate a docker compose project."""

    if len(artifacts) == 0:
        raise ValueError("No ExecutableArtifactes to generate for.")

    compose_project = DockerComposeProject(name=bolt.project, networks={}, services={}, volumes={})

    resource_service_names: dict[str, str] = {}

    artifact_deque = deque([(bolt, artifact) for artifact in artifacts])

    # Translate our artifacts into docker compose services
    while artifact_deque:
        artifact_bolt, artifact = artifact_deque.popleft()
        artifact_ref_name = _get_artifact_ref_name(artifact_bolt, artifact)

        if artifact.execution.resources:
            requeue = False
            for resource_requirement in artifact.execution.resources:
                if resource_requirement.resource not in resource_service_names:
                    resource_with_provider_artifact = adapter.resolve_resource_requirement(
                        resource_requirement, environment
                    )
                    provider_artifact_bolt, provider_artifact = adapter.get_artifact_from_reference(
                        resource_with_provider_artifact.artifact, environment
                    )
                    if provider_artifact.execution:
                        requeue = True

                        if provider_artifact not in artifact_deque:
                            artifact_deque.appendleft((provider_artifact_bolt, provider_artifact))

                    else:
                        # TODO: Virtual service stuff!
                        pass

            if requeue:
                artifact_deque.append((artifact_bolt, artifact))
                continue

        # We can generate this artifact!
        compose_service = _generate_docker_compose_service_from_artifact(
            adapter=adapter,
            environment=environment,
            bolt=artifact_bolt,
            artifact=artifact,
            execution_parameters=execution_parameters.params_for_artifact(
                environment=environment, bolt=bolt, artifact=artifact
            ),
        )

        if artifact.execution.resources:
            compose_service.depends_on = {
                resource_service_names[resource_requirement.resource]: {"condition": "service_healthy"}
                for resource_requirement in artifact.execution.resources
            }

        compose_project.services[artifact_ref_name] = compose_service

        compose_project.volumes.update(
            {
                f"{artifact_ref_name}-{volume.name}": DockerComposeProjectVolume(
                    driver="local",
                    name=volume.title.replace(" ", "-") if volume.title else volume.name.replace(" ", "-"),
                )
                for volume in artifact.execution.volumes
                if volume.persistent
            }
        )

        if artifact.provides:
            resource_service_names.update({resource.name: artifact_ref_name for resource in artifact.provides})

    return compose_project


def _get_artifact_ref_name(bolt: Bolt, artifact: ExecutableArtifact) -> str:
    return f"{bolt.project}-{artifact.name}"


def _generate_docker_compose_service_from_artifact(
    adapter: DockerComposeInfrastructureAdapter,
    environment: Environment,
    bolt: Bolt,
    artifact: ExecutableArtifact,
    execution_parameters: ArtifactExecutionParameters,
) -> DockerComposeService:
    """Generate a docker compose Service definition for an ExecutableArtifact."""

    execution = artifact.execution
    artifact_ref_name = _get_artifact_ref_name(bolt, artifact)

    compose_service = DockerComposeService(container_name=artifact_ref_name)

    if compute_parameters := execution_parameters.compute:
        resource_max = {}
        resource_min = {}
        if max_cpu := compute_parameters.max_cpu:
            resource_max["cpus"] = str(max_cpu)
        if max_memory := compute_parameters.max_memory:
            resource_max["memory"] = f"{max_memory}g"
        if min_cpu := compute_parameters.min_cpu:
            resource_min["cpus"] = str(min_cpu)
        if min_memory := compute_parameters.min_memory:
            resource_min["memory"] = f"{min_memory}g"

        if resource_max or resource_min:
            compose_service.deploy = {"resources": {"limits": resource_max, "reservations": resource_min}}

    env = {}
    env_files = []

    has_artifact_configs = len(execution.configs) > 0
    has_artifact_secrets = len(execution.secrets) > 0

    # Resources
    if resource_requirements := execution.resources:
        for resource_requirement in resource_requirements:
            resource, artifact_reference = adapter.resolve_resource_requirement(resource_requirement, environment)

            ref_name = f"{artifact_reference.project}-{resource.name}-shared"

            has_shared_configs = False
            for config in resource.configs:
                if config.shared:
                    has_shared_configs = True
                else:
                    has_artifact_configs = True

            if has_shared_configs:
                env_files.append({"format": "raw", "path": f"{ref_name}-configs.env", "required": True})

            has_shared_secrets = False
            for secret in resource.secrets:
                if secret.shared:
                    has_shared_secrets = True
                else:
                    has_artifact_secrets = True

            if has_shared_secrets:
                env_files.append({"format": "raw", "path": f"{ref_name}-secrets.env", "required": True})

    if has_artifact_configs:
        # Service configs are NOT required
        env_files.append({"format": "raw", "path": f"{artifact_ref_name}-configs.env", "required": False})

    if has_artifact_secrets:
        env_files.append({"format": "raw", "path": f"{artifact_ref_name}-secrets.env", "required": True})

    # Services
    services_added = {}
    for service in execution.services:
        port_service = service.grpc or service.http or service.tcp
        if port_service is None:
            # WTF is it, then? Needs a better abstraction.
            continue

        services_added[service.name] = service

        key = f"{service.name.upper()}_SERVICE"
        host = "localhost"
        path = "/"
        env[f"{key}_PORT"] = str(port_service)

        external_service_parameters = execution_parameters.external_services.get(service.name)
        if external_service_parameters and external_service_parameters.host is not None:
            host = external_service_parameters.host
            if external_service_parameters.path:
                path = external_service_parameters.path

            compose_service.ports.append(
                {
                    "name": service.name,
                    "published": str(external_service_parameters.port or port_service),
                    "target": port_service,
                }
            )

        env[f"{key}_HOST"] = host
        if service.http:
            env[f"{key}_PATH"] = path

    # Healthchecks; processed after services as they can depend on them.
    if healthchecks := execution.healthchecks:
        # Docker Compose only supports a single healthcheck
        if probe := healthchecks.ready or healthchecks.alive or healthchecks.started:
            compose_service.healthcheck = _generate_healthcheck(probe, services_added)

    # Building
    if build := artifact.build:
        context = "."
        dockerfile = build.dockerfile or "Dockerfile"
        if (pieces := dockerfile.rsplit("/", 1)) and len(pieces) > 1:
            context, dockerfile = pieces

        compose_service.build = {"context": context, "dockerfile": dockerfile, "target": build.dockerfile_target}

        # TODO: Implement better development specs
        compose_service.develop = {"watch": [{"action": "rebuild", "path": context}]}
    else:
        compose_service.image = artifact.type.docker_image.image or artifact.name

    # Volumes
    if volumes := execution.volumes:
        for volume in volumes:
            execution_volume_parameters = execution_parameters.volumes.get(volume.name)

            if volume.persistent:
                volume_options = None
                if execution_volume_parameters and execution_volume_parameters.path:
                    volume_options = {"subpath": execution_volume_parameters.path}

                compose_service.volumes.append(
                    DockerComposeServiceVolume(
                        source=f"{artifact_ref_name}-{volume.name}",
                        target=volume.path,
                        type="volume",
                        volume=volume_options,
                    )
                )
            else:
                tmpfs_options = {"size": f"{volume.capacity}G"}

                compose_service.volumes.append(
                    DockerComposeServiceVolume(target=volume.path, tmpfs=tmpfs_options, type="tmpfs")
                )

    if env:
        compose_service.environment = env
    if env_files:
        compose_service.env_file = env_files

    return compose_service


def _generate_compose_volume():
    pass


def _generate_healthcheck(probe: HealthcheckProbe, services: dict[str, ServiceRequirement]) -> dict:
    options = {
        "start_interval": "1s",
        "start_period": "60s",
    }

    if probe.exec:
        # Escape dollar signs so docker compose doesn't interpolate them.
        commands = [c.replace("$", "$$") for c in probe.exec.commands]
        return options | {"test": ["CMD-SHELL" if probe.exec.shell else "CMD", *commands]}

    port_probe = probe.grpc or probe.http or probe.tcp
    if port_probe is None:
        return {}

    # Retrieve services referenced by port-based probes.
    service = None
    if port_probe.service:
        service = services.get(port_probe.service)
        if service is None:
            raise ValueError(f'Unknown referenced service "{port_probe.service}".')

    if probe.grpc:
        port = probe.grpc.port or 50051

        if service:
            if service.grpc is None:
                raise ValueError("Must reference a grpc service for a grpc probe.")

            port = service.grpc

        # TODO: GRPC probe
        return options | {}

    if probe.http:
        path = probe.http.path or "/healthz"
        port = probe.http.port or 80

        if service:
            if service.http is None:
                raise ValueError("Must reference an http service for an http probe.")

            port = service.http

        return options | {"test": ["CMD-SHELL", f"curl -f http://localhost:{port}{path}"]}

    if probe.tcp:
        port = probe.tcp.port

        if service:
            if service.tcp is None:
                raise ValueError("Must reference a tcp service for a tcp probe.")

            port = service.tcp

        if not port:
            raise ValueError("TCP probe needs a port.")

        # TODO: TCP probe
        return options | {}

    return {}


class DockerComposeInfrastructureAdapter:
    name: ClassVar[str] = "docker-compose"
    _bolts: list[Bolt]

    def __init__(self, bolts: list[Bolt] = []):
        self._bolts = bolts
        self.configs_adapter = DockerComposeConfigsAdapter()
        self.secrets_adapter = DockerComposeSecretsAdapater()

    def _call_compose(self, docker_compose_project: DockerComposeProject, commands: Collection[str]):
        """Call docker compose."""
        # Create a temporary file filled with docker compose YAML and use that to call docker compose commands
        with tempfile.NamedTemporaryFile() as f:
            docker_compose_dict = docker_compose_project.model_dump(exclude_none=True)
            yaml.dump(docker_compose_dict, stream=f, encoding="utf-8")

            args = ["docker", "compose", "--project-directory", os.getcwd(), "--file", f.name, *commands]
            subprocess.run(args)

    def deploy(
        self,
        bolt: Bolt,
        artifacts: Collection[ExecutableArtifact],
        environment: Environment,
        execution_parameters: ExecutionParameters,
    ):
        docker_compose_project = _generate_docker_compose_project_from_bolt(
            adapter=self,
            environment=environment,
            bolt=bolt,
            artifacts=artifacts,
            execution_parameters=execution_parameters,
        )

        if True:
            commands = ["up", "--build", "--watch", "--remove-orphans"]
        else:
            commands = ["up", "--remove-orphans"]
        self._call_compose(docker_compose_project, commands)

    def get_artifact_from_reference(
        self, artifact_reference: ArtifactReference, environment: Environment
    ) -> tuple[Bolt, Artifact]:
        for bolt in self._bolts:
            for artifact in bolt.artifacts:
                if (
                    artifact_reference.artifact == artifact.name
                    and artifact_reference.version == bolt.version
                    and artifact_reference.project == bolt.project
                ):
                    return bolt, artifact

        raise UnknownArtifact(artifact_reference)

    def list_artifact_types(self, environment: Environment) -> list[ArtifactType]:
        return [ArtifactType(name="docker_image", title="Docker Image")]

    def list_executable_artifacts(self, environment: Environment) -> list[ArtifactReference]:
        references = []

        for bolt in self._bolts:
            references.extend(
                [ArtifactReference(artifact.name, bolt.version, bolt.project) for artifact in bolt.executable_artifacts]
            )

        return references

    def list_projects(self) -> list[Project]:
        return []

    def list_resources(self, environment: Environment) -> list[ResourceProviderArtifactReference]:
        """List available Resources with a providing ArtifactReference in the specified Environment."""

        references = []
        for bolt in self._bolts:
            references.extend(
                [
                    ResourceProviderArtifactReference(
                        resource, ArtifactReference(artifact.name, bolt.version, bolt.project)
                    )
                    for artifact in bolt.executable_artifacts
                    for resource in artifact.provides
                ]
            )

        return references

    def resolve_resource_requirement(
        self, resource_requirement: ProjectResourceRequirement, environment: Environment
    ) -> ResourceProviderArtifactReference:
        for resource_provider_artifact_reference in self.list_resources(environment=environment):
            if (
                resource_provider_artifact_reference.artifact.project == resource_requirement.project
                and resource_provider_artifact_reference.resource.name == resource_requirement.resource
            ):
                return resource_provider_artifact_reference

        raise UnknownResourceRequirement(resource_requirement.project, resource_requirement.resource)

    def teardown(
        self,
        bolt: Bolt,
        artifacts: Collection[ExecutableArtifact],
        environment: Environment,
        execution_parameters: ExecutionParameters,
    ):
        docker_compose_project = _generate_docker_compose_project_from_bolt(
            adapter=self,
            environment=environment,
            bolt=bolt,
            artifacts=artifacts,
            execution_parameters=execution_parameters,
        )

        self._call_compose(docker_compose_project, ["down"])


class DockerComposeSettingsAdapter(SettingsAdapter):
    def delete(self, setting: ExecutableArtifactSetting):
        raise Exception()

    def exists(self, setting: ExecutableArtifactSetting) -> bool:
        return False

    def read(self, setting: ExecutableArtifactSetting) -> SettingValue:
        raise Exception()

    def write(self, setting: ExecutableArtifactSetting, value: SettingValue):
        raise Exception()

    def _write_value(self):
        pass


class DockerComposeConfigsAdapter(DockerComposeSettingsAdapter):
    pass


class DockerComposeSecretsAdapater(DockerComposeSettingsAdapter):
    pass
