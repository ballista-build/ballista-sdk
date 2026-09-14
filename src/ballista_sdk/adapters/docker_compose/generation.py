from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from ballista_sdk.adapters.primitives import (
    ArtifactReference,
    ProvidedResourceReference,
    ProvidedServiceReference,
    ResolvedProvidedResource,
    ResolvedProvidedService,
)
from ballista_sdk.api.v1 import (
    Artifact,
    ArtifactExecution,
    ArtifactExecutionParameters,
    Bolt,
    Environment,
    ExecutionParameters,
    HealthcheckProbe,
    ProvidedResourceSetting,
    ProvidedService,
    ServiceRequirement,
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
    environment: dict[str, str] = {}
    env_file: list[dict] = []
    extra_hosts: dict[str, str] = {}
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

    def generate_docker_compose_project_from_bolt(
        self,
        environment: Environment,
        bolt: Bolt,
        execution_parameters: ExecutionParameters,
        resource_providers: dict[ProvidedResourceReference, ResolvedProvidedResource],
        service_providers: dict[ProvidedServiceReference, ResolvedProvidedService],
    ) -> DockerComposeProject:
        """Generate a docker compose project."""

        networks = {f"env-{environment.name}": {"internal": True, "name": f"env-{environment.name}"}}
        compose_project = DockerComposeProject(name=bolt.project, networks=networks, services={}, volumes={})

        for artifact in bolt.artifacts:
            if not (artifact_execution := artifact.execution):
                continue

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
                artifact_execution=artifact_execution,
                artifact_execution_parameters=artifact_execution_parameters,
                resource_providers=resource_providers,
                service_providers=service_providers,
            )

            for service in artifact_execution.provides.services:
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
                for volume in artifact_execution.requires.volumes
                if volume.persistent
            }

        return compose_project

    def generate_docker_compose_service_from_artifact(
        self,
        environment: Environment,
        bolt: Bolt,
        artifact: Artifact,
        artifact_execution: ArtifactExecution,
        artifact_execution_parameters: ArtifactExecutionParameters,
        resource_providers: dict[ProvidedResourceReference, ResolvedProvidedResource],
        service_providers: dict[ProvidedServiceReference, ResolvedProvidedService],
    ) -> DockerComposeService:
        """Generate a docker compose Service definition for an ExecutableArtifact."""

        artifact_ref_name = _get_artifact_ref_name(bolt, artifact)
        artifact_reference = ArtifactReference(bolt.project, artifact.name, bolt.version)

        compose_service = DockerComposeService(
            container_name=artifact_ref_name, networks={f"project-{bolt.project}": {}, f"env-{environment.name}": {}}
        )

        # Virtual Provided Services
        extra_hosts = {vps.service.name: vps.ipv4_address for vps in bolt.provides.services}
        if extra_hosts:
            compose_service.extra_hosts = extra_hosts

        if compute_parameters := artifact_execution_parameters.compute:
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

        # TODO: Hoist these out so they can be provider services
        # Resource Requirements
        resource_settings = []
        resource_service_requirements = []
        depends_keys = set()
        for resource_requirement in artifact_execution.requires.resources:
            provided_resource_reference = ProvidedResourceReference(
                project_name=resource_requirement.project_name, resource_name=resource_requirement.resource_name
            )
            provided_resource, provider_artifact_reference = resource_providers[provided_resource_reference]

            resource_settings.extend(provided_resource.configs)
            resource_settings.extend(provided_resource.secrets)

            requirement_prefix = resource_requirement.prefix or provided_resource.prefix
            resource_requirement_requirement = resource_requirement.resource_requirement
            aliased_data = resource_requirement_requirement.__pydantic_extra__ or {}

            # Re-alias the linked services
            resource_service_requirements.extend(
                [
                    ServiceRequirement.model_validate(
                        {
                            service_requirement.project_name: {
                                service_requirement.artifact_name: {
                                    service_requirement.service_name: {
                                        "host-alias": aliased_data.get("host-alias", f"{requirement_prefix}_HOST"),
                                        "port-alias": aliased_data.get("port-alias", f"{requirement_prefix}_PORT"),
                                        "secure-alias": aliased_data.get(
                                            "secure-alias", f"{requirement_prefix}_SECURE"
                                        ),
                                    }
                                }
                            }
                        }
                    )
                    for service_requirement in provided_resource.linked.services
                ]
            )

            depends_keys.add(f"{provider_artifact_reference.project_name}-{provider_artifact_reference.artifact_name}")

        [
            self.add_artifact_setting(compose_service, artifact_reference, s)
            for s in artifact_execution.requires.configs + artifact_execution.requires.secrets + resource_settings
        ]

        # Required Services
        for service_requirement in artifact_execution.requires.services + resource_service_requirements:
            provided_service_reference = ProvidedServiceReference(
                service_requirement.project_name, service_requirement.artifact_name, service_requirement.service_name
            )
            provided_service, provider_artifact_reference, provided_service_host = service_providers[
                provided_service_reference
            ]
            port_service = provided_service.grpc or provided_service.http or provided_service.tcp
            if not port_service:
                # WTF is it?
                continue

            service_env_name = f"{provider_artifact_reference.project_name}-{provider_artifact_reference.artifact_name}-{provided_service.name}".upper().replace(
                "-", "_"
            )
            service_requirement_requirement = service_requirement.service_requirement
            host_key = service_requirement_requirement.get("host-alias", f"{service_env_name}_HOST")
            port_key = service_requirement_requirement.get("port-alias", f"{service_env_name}_PORT")
            secure_key = service_requirement_requirement.get("secure-alias", f"{service_env_name}_SECURE")

            env.update(
                {
                    host_key: provided_service_host,
                    port_key: str(port_service),
                    secure_key: "true" if provided_service.secure else "false",
                }
            )

            depends_keys.add(f"{provider_artifact_reference.project_name}-{provider_artifact_reference.artifact_name}")

        compose_service.depends_on = {key: {"condition": "service_healthy"} for key in depends_keys}

        # Provided Services
        services_provided = {}
        compose_service.ports = ports = []
        for service in artifact_execution.provides.services:
            port_service = service.grpc or service.http or service.tcp
            if port_service is None:
                # WTF is it, then? Needs a better abstraction.
                continue

            services_provided[service.name] = service

            key = service.name.upper().replace("-", "_") + "_SERVICE"
            host = "localhost"
            path = "/"
            secure = service.secure
            env[f"{key}_PORT"] = str(port_service)

            external_service_parameters = artifact_execution_parameters.external_services.get(service.name)
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
                        "target": str(port_service),
                    }
                )

            env[f"{key}_HOST"] = host
            env[f"{key}_SECURE"] = "true" if secure else "false"
            if service.http:
                env[f"{key}_PATH"] = path

        # Healthchecks; processed after services as they can depend on them.
        if healthchecks := artifact_execution.provides.healthchecks:
            # Docker Compose only supports a single healthcheck
            if probe := (healthchecks.ready or healthchecks.alive or healthchecks.started):
                compose_service.healthcheck = _generate_healthcheck(probe, services_provided)

        # Building
        if build := artifact.build:
            compose_service.build = {"dockerfile": build.dockerfile or "Dockerfile"}
            if build.dockerfile_target:
                compose_service.build["target"] = build.dockerfile_target

            # TODO: Implement better development specs
            compose_service.develop = {"watch": [{"action": "rebuild", "path": "."}]}
        else:
            compose_service.image = artifact.type.docker_image.image or artifact.name

        # Volumes
        for volume in artifact_execution.requires.volumes:
            execution_volume_parameters = artifact_execution_parameters.volumes.get(volume.name)

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


def _get_artifact_ref_name(bolt: Bolt, artifact: Artifact) -> str:
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
