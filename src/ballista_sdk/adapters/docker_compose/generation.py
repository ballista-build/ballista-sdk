from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from ballista_sdk.adapters.primitives import (
    ArtifactReference,
    ProvidedResourceReference,
    ProvidedResourceWithArtifactReference,
    ProvidedServiceReference,
    ProvidedServiceWithArtifactReference,
)
from ballista_sdk.api.v1 import (
    ArtifactExecutionParameters,
    Bolt,
    Environment,
    ExecutableArtifact,
    ExecutionParameters,
    HealthcheckProbe,
    ProvidedService,
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
    provider: dict[str, Any] = {}
    ports: list[dict[str, Any]] = []
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
    provided_resource_reference: ProvidedResourceReference, sensitive: bool
) -> str:
    return _generate_envfile_filename(
        f"{provided_resource_reference.project_name}-resources-{provided_resource_reference.resource_name}", sensitive
    )


@dataclass
class DockerComposeInfrastructureGenerator:
    """Generates docker compose projects."""

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
        provided_resource_reference: ProvidedResourceReference,
        resource_setting: ResourceSetting,
        prefix: str,
        instance: list[str],
    ):
        if resource_setting.shared:
            self._add_envfile(
                service,
                generate_resource_setting_envfile_filename(provided_resource_reference, resource_setting.sensitive),
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
        resource_providers: dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference],
        service_providers: dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference],
    ) -> DockerComposeProject:
        """Generate a docker compose project."""

        if len(artifacts) == 0:
            raise ValueError("No ExecutableArtifactes to generate for.")

        networks = {f"env-{environment.name}": {"internal": True, "name": f"env-{environment.name}"}}
        compose_project = DockerComposeProject(name=bolt.project, networks=networks, services={}, volumes={})

        for artifact in artifacts:
            artifact_ref_name = f"{bolt.project}-{artifact.name}"

            project_network_name = f"project-{bolt.project}"
            if project_network_name not in networks:
                compose_project.networks[project_network_name] = {"internal": True, "name": project_network_name}

            # We can generate this artifact!
            artifact_execution_parameters = execution_parameters.params_for_artifact(
                environment=environment, bolt=bolt, artifact=artifact
            )
            compose_service = self.generate_docker_compose_service_from_artifact(
                environment=environment,
                bolt=bolt,
                artifact=artifact,
                execution_parameters=artifact_execution_parameters,
                resource_providers=resource_providers,
                service_providers=service_providers,
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

        return compose_project

    def generate_docker_compose_service_from_artifact(
        self,
        environment: Environment,
        bolt: Bolt,
        artifact: ExecutableArtifact,
        execution_parameters: ArtifactExecutionParameters,
        resource_providers: dict[ProvidedResourceReference, ProvidedResourceWithArtifactReference],
        service_providers: dict[ProvidedServiceReference, ProvidedServiceWithArtifactReference],
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

        # Artifact configs
        settings = execution.requires.configs + execution.requires.secrets

        [self.add_artifact_setting(compose_service, artifact_reference, setting) for setting in settings]

        # TODO: Hoist these out so they can be provider services
        # Resource Requirements
        depends_keys = set()
        for resource_requirement in execution.requires.resources:
            provided_resource_reference = ProvidedResourceReference(
                project_name=resource_requirement.project_name, resource_name=resource_requirement.resource_name
            )
            provided_resource, provider_artifact_reference = resource_providers[provided_resource_reference]

            depends_keys.add(f"{provider_artifact_reference.project_name}-{provider_artifact_reference.artifact_name}")

            resource_requirement_requirement = resource_requirement.resource_requirement
            requirement_instance = [
                getattr(resource_requirement_requirement, f) for f in provided_resource.instance_id_fields
            ]

            [
                self.add_resource_setting(
                    compose_service,
                    artifact_reference,
                    provided_resource_reference,
                    setting,
                    provided_resource.prefix,
                    requirement_instance,
                )
                for setting in provided_resource.configs + provided_resource.secrets
            ]

        # TODO: Hoist these out so they can be provider services
        # Service Requirements
        for service_requirement in execution.requires.services:
            provided_service_reference = ProvidedServiceReference(
                project_name=service_requirement.project_name,
                artifact_name=service_requirement.artifact_name,
                service_name=service_requirement.service_name,
            )
            provided_service, provider_artifact_reference = service_providers[provided_service_reference]

            depends_keys.add(f"{provider_artifact_reference.project_name}-{provider_artifact_reference.artifact_name}")

            service_dns_name = provided_service.name.lower().replace("_", "-")
            service_env_name = provided_service.name.upper().replace("-", "_")

            env.update(
                {
                    f"{service_env_name}_HOST": service_dns_name,
                    f"{service_env_name}_PORT": provided_service.grpc or provided_service.http or provided_service.tcp,
                }
            )

            # TODO: Add to env

        compose_service.depends_on = {key: {"condition": "service_healthy"} for key in depends_keys}

        # Provided Services
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
            secure = service.secure
            env[f"{key}_PORT"] = str(port_service)

            external_service_parameters = execution_parameters.external_services.get(service.name)
            if external_service_parameters and external_service_parameters.host is not None:
                host = external_service_parameters.host

                if external_service_parameters.path:
                    path = external_service_parameters.path
                if external_service_parameters.secure:
                    # Only set when true; no insecure downgrading.
                    secure = external_service_parameters.secure

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
            env[f"{key}_SECURE"] = "true" if secure else "false"
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

    port = port_probe.port
    service = None

    if port_probe.service:
        service = services.get(port_probe.service)
        if service is None:
            raise ValueError(f'Unknown referenced service "{port_probe.service}".')

    if probe.grpc:
        if service:
            if service.grpc is None:
                raise ValueError("Must reference a grpc service for a grpc probe.")
            port = service.grpc

        if not port:
            raise ValueError("GPRC probe bad.")

        # TODO: GRPC probe
        return options | {}

    if probe.http:
        path = probe.http.path or "/healthz"

        if service:
            if service.http is None:
                raise ValueError("Must reference an http service for an http probe.")

            port = service.http

        if not port:
            raise ValueError("HTTP probe bad.")

        return options | {"test": ["CMD-SHELL", f"curl -f http://localhost:{port}{path}"]}

    if probe.tcp:
        if service:
            if service.tcp is None:
                raise ValueError("Must reference a tcp service for a tcp probe.")

            port = service.tcp

        if not port:
            raise ValueError("TCP probe bad.")

        # TODO: TCP probe
        return options | {}

    return {}
