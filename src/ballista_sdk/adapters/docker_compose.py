from __future__ import annotations

import os
import subprocess
import tempfile
from collections import deque
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

import yaml
from pydantic import BaseModel

from ballista_sdk.adapters.exceptions import UnknownArtifact, UnknownResourceRequirement
from ballista_sdk.adapters.settings import (
    BoundSetting,
    Setting,
    SettingsAdapter,
    SettingValue,
)
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
    ResourceProviderReference,
    ResourceReference,
    ResourceSetting,
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
    networks: dict[str, dict] = {}
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

    networks = {f"env-{environment.name}": {"internal": True, "name": f"env-{environment.name}"}}
    compose_project = DockerComposeProject(name=bolt.project, networks=networks, services={}, volumes={})

    resource_service_names: dict[str, str] = {}

    artifact_deque = deque([(bolt, artifact) for artifact in artifacts])

    # Translate our artifacts into docker compose services
    while artifact_deque:
        artifact_bolt, artifact = artifact_deque.popleft()
        artifact_ref_name = _get_artifact_ref_name(artifact_bolt, artifact)

        if artifact.execution.resources:
            requeue = False
            for resource_requirement in artifact.execution.resources:
                if resource_requirement.resource_name not in resource_service_names:
                    resource_with_provider_artifact = adapter.resolve_resource_requirement(
                        resource_requirement, environment
                    )

                    if artifact_reference := resource_with_provider_artifact.artifact_reference:
                        # Resource is provided by an artifact that is executable
                        provider_artifact_bolt, provider_artifact = adapter.get_artifact_from_reference(
                            artifact_reference, environment
                        )

                        requeue = True

                        if provider_artifact not in artifact_deque:
                            artifact_deque.appendleft((provider_artifact_bolt, provider_artifact))

                    else:
                        # TODO: Virtual service stuff!
                        pass

            if requeue:
                artifact_deque.append((artifact_bolt, artifact))
                continue

        project_network_name = f"project-{artifact_bolt.project}"
        if project_network_name not in networks:
            compose_project.networks[project_network_name] = {"internal": True, "name": project_network_name}

        # We can generate this artifact!
        artifact_execution_parameters = execution_parameters.params_for_artifact(
            environment=environment, bolt=artifact_bolt, artifact=artifact
        )
        compose_service = _generate_docker_compose_service_from_artifact(
            adapter=adapter,
            environment=environment,
            bolt=artifact_bolt,
            artifact=artifact,
            execution_parameters=artifact_execution_parameters,
        )

        if artifact.execution.resources:
            compose_service.depends_on = {
                resource_service_names[resource_requirement.resource_name]: {"condition": "service_healthy"}
                for resource_requirement in artifact.execution.resources
            }

        if artifact.execution.services:
            for service in artifact.execution.services:
                external_service_parameters = artifact_execution_parameters.external_services.get(service.name)
                if external_service_parameters and external_service_parameters.host is not None:
                    network_name = f"external-{external_service_parameters.host}"

                    if network_name not in compose_project.networks:
                        compose_project.networks[network_name] = {"name": network_name}

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
    artifact_reference = ArtifactReference(bolt.project, artifact.name, bolt.version)

    compose_service = DockerComposeService(
        container_name=artifact_ref_name, networks={f"project-{bolt.project}": {}, f"env-{environment.name}": {}}
    )

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

    configs_adapter = adapter.configs_adapter
    secrets_adapter = adapter.secrets_adapter

    # Artifact configs
    [configs_adapter.add_artifact_setting(compose_service, artifact_reference, c) for c in execution.configs]
    # Artifact secrets
    [secrets_adapter.add_artifact_setting(compose_service, artifact_reference, s) for s in execution.secrets]

    # Resources
    for resource_requirement in execution.resources:
        resource, resource_project, _, _ = adapter.resolve_resource_requirement(resource_requirement, environment)
        resource_reference = ResourceReference(resource_project, resource.name)
        requirement_prefix = resource_requirement.prefix or resource.prefix
        requirement_instance = [getattr(resource_requirement.requirement, f) for f in resource.instance_id_fields]

        [
            configs_adapter.add_resource_setting(
                compose_service, artifact_reference, resource_reference, c, requirement_prefix, requirement_instance
            )
            for c in resource.configs
        ]
        [
            secrets_adapter.add_resource_setting(
                compose_service, artifact_reference, resource_reference, s, requirement_prefix, requirement_instance
            )
            for s in resource.secrets
        ]

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

            network_name = f"external-{host}"
            if network_name not in compose_service.networks:
                compose_service.networks[network_name] = {"aliases": [host]}

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
    for volume in execution.volumes:
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

    return compose_service


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


class DockerComposeSettingsAdapter(SettingsAdapter):
    verify_before_deploy: ClassVar[bool] = True

    # TODO: This would be a great place for t-strings
    def _get_envfile_filename(self, ref_name: str, sensitive: bool) -> str:
        return ref_name + ("-secrets" if sensitive else "-configs") + ".env"

    def _get_artifact_setting_envfile(self, artifact_reference: ArtifactReference, sensitive: bool) -> str:
        return self._get_envfile_filename(
            f"{artifact_reference.project_name}-{artifact_reference.artifact_name}", sensitive
        )

    def _get_resource_setting_envfile(self, resource_reference: ResourceReference, sensitive: bool) -> str:
        return self._get_envfile_filename(
            f"{resource_reference.project_name}-resources-{resource_reference.resource_name}", sensitive
        )

    def _add_envfile(self, service: DockerComposeService, filename: str, required: bool):
        """Add a list of BoundSettings to the Docker Compose Service being generated."""

        env = {"format": "raw", "path": filename, "required": required}

        if service.env_file is None:
            service.env_file = [env]
        elif env not in service.env_file:
            service.env_file.append(env)

    def add_artifact_setting(
        self, service: DockerComposeService, artifact_reference: ArtifactReference, setting: Setting
    ):
        self._add_envfile(
            service,
            self._get_artifact_setting_envfile(artifact_reference, setting.sensitive),
            setting.sensitive,
        )

    def add_resource_setting(
        self,
        service: DockerComposeService,
        artifact_reference: ArtifactReference,
        resource_reference: ResourceReference,
        resource_setting: ResourceSetting,
        prefix: str,
        instance: list[str],
    ):
        if resource_setting.shared:
            self._add_envfile(
                service, self._get_resource_setting_envfile(resource_reference, resource_setting.sensitive), True
            )

        else:
            self.add_artifact_setting(service, artifact_reference, resource_setting)

    def _get_bound_setting_env_filename(self, environment: Environment, bound_setting: BoundSetting) -> str:
        if bound_setting.artifact:
            return self._get_artifact_setting_envfile(bound_setting.artifact, bound_setting.setting.sensitive)
        elif bound_setting.resource:
            return self._get_resource_setting_envfile(bound_setting.resource, bound_setting.setting.sensitive)
        else:
            raise ValueError("BoundSetting needs an artifact or resource reference.")

    def delete(self, environment: Environment, bound_setting: BoundSetting):
        filename = self._get_bound_setting_env_filename(environment, bound_setting)
        raise Exception()

    def exists(self, environment: Environment, bound_setting: BoundSetting) -> bool:
        filename = self._get_bound_setting_env_filename(environment, bound_setting)

        key = f""

        return os.path.exists(filename)

    def read(self, environment: Environment, bound_setting: BoundSetting) -> SettingValue:
        filename = self._get_bound_setting_env_filename(environment, bound_setting)

        raise Exception()

    def write(self, environment: Environment, bound_setting: BoundSetting, value: SettingValue):
        filename = self._get_bound_setting_env_filename(environment, bound_setting)
        raise Exception()

    def _exists(self, filename: str) -> bool:
        return False

    def _write_value(self):
        pass


@dataclass
class DockerComposeInfrastructureAdapter:
    name: ClassVar[str] = "docker-compose"

    _bolts: list[Bolt] = field(default_factory=list)
    configs_adapter: DockerComposeSettingsAdapter = field(default_factory=DockerComposeSettingsAdapter)
    # TODO: Make these the same instance
    secrets_adapter: DockerComposeSettingsAdapter = field(default_factory=DockerComposeSettingsAdapter)

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
        print(docker_compose_project.model_dump_json())
        self._call_compose(docker_compose_project, commands)

    def get_artifact_from_reference(
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

    def list_artifact_types(self, environment: Environment) -> list[ArtifactType]:
        return [ArtifactType(name="docker_image", title="Docker Image")]

    def list_executable_artifacts(self, environment: Environment) -> list[ArtifactReference]:
        references = []

        for bolt in self._bolts:
            references.extend(
                [ArtifactReference(bolt.project, artifact.name, bolt.version) for artifact in bolt.executable_artifacts]
            )

        return references

    def list_projects(self) -> list[Project]:
        return []

    def list_project_bolts(self, project: Project) -> list[Bolt]:
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

    def resolve_resource_requirement(
        self, resource_requirement: ProjectResourceRequirement, environment: Environment
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

        raise UnknownResourceRequirement(requirement_project_name, requirement_resource_name)

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
