from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

from pydantic import BaseModel

from ballista_sdk.adapters import InfrastructureAdapter
from ballista_sdk.api.v1 import (
    ArtifactExecutionParameters,
    ArtifactReference,
    Bolt,
    Environment,
    ExecutableArtifact,
    ExecutionParameters,
    HealthcheckProbe,
    ProvidedService,
    ResourceProviderReference,
    ResourceSetting,
    Setting,
)


class DockerComposeServiceVolume(BaseModel):
    source: str | None = None
    target: str
    tmpfs: dict | None = None
    type: Literal["bind", "volume", "tmpfs", "npipe"]
    volume: dict | None = None


class DockerComposeService(BaseModel):
    build: dict[str, Any] = {}
    configs: list[str] = []
    container_name: str | None = None
    depends_on: dict[str, dict[str, str]] = {}
    deploy: dict[str, Any] = {}
    develop: dict[str, Any] = {}
    environment: dict[str, Any] = {}
    env_file: list[dict] = []
    healthcheck: dict[str, Any] = {}
    image: str | None = None
    networks: dict[str, dict] = {}
    ports: list[dict[str, Any]] = []
    profiles: list[str] = []
    secrets: list[str] = []
    volumes: list[DockerComposeServiceVolume] = []


class DockerComposeProjectVolume(BaseModel):
    driver: str
    name: str
    """Human-readable volume name. Not the volume identifier."""


class DockerComposeProject(BaseModel):
    configs: dict[str, Any] = {}
    name: str
    networks: dict[str, dict[str, Any]]
    secrets: dict[str, Any] = {}
    services: dict[str, DockerComposeService]
    volumes: dict[str, DockerComposeProjectVolume] = {}


def _generate_envfile_filename(ref_name: str, sensitive: bool) -> str:
    return ref_name + ("-secrets" if sensitive else "-configs") + ".env"


def generate_artifact_setting_envfile_filename(artifact_reference: ArtifactReference, sensitive: bool) -> str:
    return _generate_envfile_filename(
        f"{artifact_reference.project_name}-{artifact_reference.artifact_name}", sensitive
    )


def generate_resource_setting_envfile_filename(
    resource_provider_reference: ResourceProviderReference, sensitive: bool
) -> str:
    return _generate_envfile_filename(
        f"{resource_provider_reference.project_name}-resources-{resource_provider_reference.resource_name}", sensitive
    )


@dataclass
class BaseDockerComposeInfrastructureAdapter(InfrastructureAdapter):
    def _add_envfile(self, service: DockerComposeService, filename: str, required: bool):
        """Add a list of BoundSettings to the Docker Compose Service being generated."""

        env = {"format": "raw", "path": filename, "required": required}

        if env not in service.env_file:
            service.env_file = service.env_file + [env]

    def add_artifact_setting(
        self, service: DockerComposeService, artifact_reference: ArtifactReference, setting: Setting
    ):
        self._add_envfile(
            service,
            generate_artifact_setting_envfile_filename(artifact_reference, setting.sensitive),
            setting.sensitive,
        )

    def add_resource_setting(
        self,
        service: DockerComposeService,
        artifact_reference: ArtifactReference,
        resource_provider_reference: ResourceProviderReference,
        resource_setting: ResourceSetting,
        prefix: str,
        instance: list[str],
    ):
        if resource_setting.shared:
            self._add_envfile(
                service,
                generate_resource_setting_envfile_filename(resource_provider_reference, resource_setting.sensitive),
                True,
            )

        else:
            self.add_artifact_setting(service, artifact_reference, resource_setting)

    def generate_docker_compose_project_from_bolt(
        self,
        environment: Environment,
        bolt: Bolt,
        artifacts: Sequence[ExecutableArtifact],
        execution_parameters: ExecutionParameters,
    ) -> DockerComposeProject:
        """Generate a docker compose project."""

        if len(artifacts) == 0:
            raise ValueError("No ExecutableArtifactes to generate for.")

        networks = {f"env-{environment.name}": {"internal": True, "name": f"env-{environment.name}"}}
        compose_project = DockerComposeProject(name=bolt.project, networks=networks, services={}, volumes={})

        resource_service_names: dict[tuple[str, str], str] = {}

        artifact_deque = deque([(bolt, artifact, ["top"]) for artifact in artifacts])

        # Translate our artifacts into docker compose services
        while artifact_deque:
            artifact_bolt, artifact, profiles = artifact_deque.popleft()
            artifact_ref_name = _get_artifact_ref_name(artifact_bolt, artifact)

            requeue = False
            # TODO: This loop and process needs to be rethought.
            # Because artifacts may have resource dependencies on providers in this chain, they need to initialize in a specific order.
            if artifact.execution.requires.resources:
                for resource_requirement in artifact.execution.requires.resources:
                    if (
                        resource_requirement.project_name,
                        resource_requirement.resource_name,
                    ) not in resource_service_names:
                        resource_with_provider_artifact = self.resolve_resource_requirement(
                            environment, resource_requirement
                        )

                        if artifact_reference := resource_with_provider_artifact.artifact_reference:
                            # Resource is provided by an artifact that is executable
                            provider_artifact_bolt, provider_artifact = self.resolve_artifact_reference(
                                environment, artifact_reference
                            )

                            if provider_artifact not in artifact_deque:
                                requeue = True
                                artifact_deque.appendleft(
                                    (
                                        provider_artifact_bolt,
                                        cast(ExecutableArtifact, provider_artifact),
                                        ["depend", "resource"],
                                    )
                                )

            if artifact.execution.requires.services:
                for service_requirement in artifact.execution.requires.services:
                    if (
                        service_requirement.project_name,
                        service_requirement.service_name,
                    ) not in resource_service_names:
                        service_with_provider_artifact = self.resolve_service_requirement(
                            environment, service_requirement
                        )

                        if artifact_reference := service_with_provider_artifact.artifact_reference:
                            provider_artifact_bolt, provider_artifact = self.resolve_artifact_reference(
                                environment, artifact_reference
                            )

                            if provider_artifact not in artifact_deque:
                                requeue = True
                                artifact_deque.appendleft(
                                    (
                                        provider_artifact_bolt,
                                        cast(ExecutableArtifact, provider_artifact),
                                        ["depend", "service"],
                                    )
                                )

            if requeue:
                artifact_deque.append((artifact_bolt, artifact, profiles))
                continue

            project_network_name = f"project-{artifact_bolt.project}"
            if project_network_name not in networks:
                compose_project.networks[project_network_name] = {"internal": True, "name": project_network_name}

            # We can generate this artifact!
            artifact_execution_parameters = execution_parameters.params_for_artifact(
                environment=environment, bolt=artifact_bolt, artifact=artifact
            )
            compose_service = self.generate_docker_compose_service_from_artifact(
                environment=environment,
                bolt=artifact_bolt,
                artifact=artifact,
                execution_parameters=artifact_execution_parameters,
                profiles=profiles,
            )

            if artifact.execution.requires.resources:
                compose_service.depends_on.update(
                    {
                        resource_service_names[
                            (resource_requirement.project_name, resource_requirement.resource_name)
                        ]: {"condition": "service_healthy"}
                        for resource_requirement in artifact.execution.requires.resources
                    }
                )

            if artifact.execution.requires.services:
                compose_service.depends_on.update(
                    {
                        resource_service_names[(service_requirement.project_name, service_requirement.service_name)]: {
                            "condition": "service_healthy"
                        }
                        for service_requirement in artifact.execution.requires.services
                    }
                )

            if artifact.execution.provides.services:
                for service in artifact.execution.provides.services:
                    external_service_parameters = artifact_execution_parameters.external_services.get(service.name)
                    if external_service_parameters and external_service_parameters.host is not None:
                        network_name = f"external-{external_service_parameters.host}"

                        if network_name not in compose_project.networks:
                            compose_project.networks = compose_project.networks | {network_name: {"name": network_name}}

            compose_project.services[artifact_ref_name] = compose_service

            compose_project.volumes = compose_project.volumes | {
                f"{artifact_ref_name}-{volume.name}": DockerComposeProjectVolume(
                    driver="local",
                    name=volume.title.replace(" ", "-") if volume.title else volume.name.replace(" ", "-"),
                )
                for volume in artifact.execution.requires.volumes
                if volume.persistent
            }

            if artifact.execution.provides.resources:
                resource_service_names.update(
                    {
                        (artifact_bolt.project, resource.name): artifact_ref_name
                        for resource in artifact.execution.provides.resources
                    }
                )
            if artifact.execution.provides.services:
                resource_service_names.update(
                    {
                        (artifact_bolt.project, service.name): artifact_ref_name
                        for service in artifact.execution.provides.services
                    }
                )

        return compose_project

    def generate_docker_compose_service_from_artifact(
        self,
        environment: Environment,
        bolt: Bolt,
        artifact: ExecutableArtifact,
        execution_parameters: ArtifactExecutionParameters,
        profiles: list[str],
    ) -> DockerComposeService:
        """Generate a docker compose Service definition for an ExecutableArtifact."""

        execution = artifact.execution
        artifact_ref_name = _get_artifact_ref_name(bolt, artifact)
        artifact_reference = ArtifactReference(bolt.project, artifact.name, bolt.version)

        compose_service = DockerComposeService(
            container_name=artifact_ref_name,
            networks={f"project-{bolt.project}": {}, f"env-{environment.name}": {}},
            profiles=profiles,
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

        # Artifact configs
        settings = execution.requires.configs + execution.requires.secrets

        [self.add_artifact_setting(compose_service, artifact_reference, setting) for setting in settings]

        # Resources
        for resource_requirement_project in execution.requires.resources:
            provided_resource, resource_project, _, _ = self.resolve_resource_requirement(
                environment, resource_requirement_project
            )

            resource_requirement = resource_requirement_project.resource_requirement
            resource_provider_reference = ResourceProviderReference(resource_project, provided_resource.name)
            requirement_prefix = resource_requirement_project.prefix or provided_resource.prefix
            requirement_instance = [getattr(resource_requirement, f) for f in provided_resource.instance_id_fields]

            [
                self.add_resource_setting(
                    compose_service,
                    artifact_reference,
                    resource_provider_reference,
                    setting,
                    requirement_prefix,
                    requirement_instance,
                )
                for setting in provided_resource.configs + provided_resource.secrets
            ]

        # Services
        services_added = {}
        compose_service.ports = ports = []
        for service in execution.provides.services:
            port_service = service.grpc or service.http or service.tcp
            if port_service is None:
                # WTF is it, then? Needs a better abstraction.
                continue

            services_added[service.name] = service

            key = service.name.upper().replace("-", "_") + "_SERVICE"
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

                ports.append(
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
        if healthchecks := execution.provides.healthchecks:
            # Docker Compose only supports a single healthcheck
            if probe := (healthchecks.ready or healthchecks.alive or healthchecks.started):
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
        for volume in execution.requires.volumes:
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


def _get_artifact_ref_name(bolt: Bolt, artifact: ExecutableArtifact) -> str:
    return f"{bolt.project}-{artifact.name}"


def _generate_healthcheck(probe: HealthcheckProbe, services: dict[str, ProvidedService]) -> dict:
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
    service = services.get(port_probe.service)
    if service is None:
        raise ValueError(f'Unknown referenced service "{port_probe.service}".')

    if probe.grpc:
        if service.grpc is None:
            raise ValueError("Must reference a grpc service for a grpc probe.")

        port = service.grpc

        # TODO: GRPC probe
        return options | {}

    if probe.http:
        path = probe.http.path or "/healthz"

        if service.http is None:
            raise ValueError("Must reference an http service for an http probe.")

        port = service.http

        return options | {"test": ["CMD-SHELL", f"curl -f http://localhost:{port}{path}"]}

    if probe.tcp:
        if service.tcp is None:
            raise ValueError("Must reference a tcp service for a tcp probe.")

        port = service.tcp

        # TODO: TCP probe
        return options | {}

    return {}
