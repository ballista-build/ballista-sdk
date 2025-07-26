from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Collection
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from ballista.adapters.types import EnvironmentExecutionAdapter
from ballista.types import (
    ArtifactType,
    Bolt,
    Environment,
    EnvironmentArtifactExecutionParameters,
    ExecutableArtifact,
    Resource,
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
    deploy: dict[str, Any] | None = None
    develop: dict[str, Any] | None = None
    environment: dict[str, Any] | None = None
    healthcheck: dict[str, Any] | None = None
    image: str | None = None
    networks: list[str] = []
    ports: list[dict[str, Any]] = []
    secrets: list[str] | None = None
    volumes: list[DockerComposeServiceVolume] = []


class DockerComposeProjectVolume(BaseModel):
    driver: str
    name: str


class DockerComposeProject(BaseModel):
    configs: dict[str, Any] | None = None
    name: str
    networks: dict[str, dict[str, Any]]
    secrets: dict[str, Any] | None = None
    services: dict[str, DockerComposeService]
    volumes: dict[str, DockerComposeProjectVolume] = {}


def _generate_docker_compose_project_from_bolt(
    bolt: Bolt,
    artifacts: Collection[ExecutableArtifact],
    adapter: DockerComposeExecutionEnvironmentAdapter,
    environment: Environment,
    execution_parameters: EnvironmentArtifactExecutionParameters,
) -> DockerComposeProject:
    """Generate a docker compose project."""
    if len(artifacts) == 0:
        raise ValueError("No artifacts to generate with.")

    project = DockerComposeProject(name=bolt.project_id, networks={}, services={}, volumes={})

    for artifact in artifacts:
        project.services[artifact.id] = _generate_docker_compose_service_from_artifact(
            bolt=bolt,
            artifact=artifact,
            adapter=adapter,
            environment=environment,
            execution_parameters=execution_parameters,
        )

        project.volumes = {
            volume.id: DockerComposeProjectVolume(driver="local", name=volume.id)
            for volume in artifact.execution.volumes
            if volume.persistent
        }

    return project


def _generate_docker_compose_service_from_artifact(
    bolt: Bolt,
    artifact: ExecutableArtifact,
    adapter: DockerComposeExecutionEnvironmentAdapter,
    environment: Environment,
    execution_parameters: EnvironmentArtifactExecutionParameters,
) -> DockerComposeService:
    """Generate a docker compose Service definition for an ExecutableArtifact."""

    service = DockerComposeService()

    if execution_resources := execution_parameters.resources:
        resource_max = {}
        resource_min = {}
        if max_cpu := execution_resources.max_cpu:
            resource_max["cpus"] = max_cpu
        if max_memory := execution_resources.max_memory:
            resource_max["memory"] = f"{max_memory}g"
        if min_cpu := execution_resources.min_cpu:
            resource_min["cpus"] = min_cpu
        if min_memory := execution_resources.min_memory:
            resource_min["memory"] = f"{min_memory}g"

        service.deploy = {"resources": {"limits": resource_max, "reservations": resource_min}}

    env = {}
    configs = []
    secrets = []

    has_service_configs = bool(artifact.execution.configs)
    has_service_secrets = bool(artifact.execution.secrets)

    # Platform Resources
    # if resource_dependencies := artifact.execution.resources:
    #     platform_resources = adapter.list_platform_resources(environment=environment)

    #     for dependency in resource_dependencies:
    #         # Get resource handler
    #         handler: Resource | None = None
    #         for platform_resource in platform_resources:
    #             if platform_resource.id == dependency.resource_id:
    #                 handler = platform_resource
    #                 break

    #         if handler is None:
    #             raise ValueError(f'No resource for "{dependency.resource_id}".')

    #         prefix = (dependency.config.get("prefix") or handler.prefix) + "_"
    #         ref_name = f"{handler.id}-shared"

    #         has_shared_configs = False
    #         for config in handler.configs:
    #             if config.shared:
    #                 has_shared_configs = True
    #             else:
    #                 has_service_configs = True

    #         if has_shared_configs:
    #             configs.append(ref_name)

    #         has_shared_secrets = False
    #         for secret in handler.secrets:
    #             if secret.shared:
    #                 has_shared_secrets = True
    #             else:
    #                 has_service_secrets = True

    #         if has_shared_secrets:
    #             secrets.append(ref_name)
    #
    # Secrets
    #
    # Configs

    if has_service_configs:
        configs.append(artifact.id)

    if has_service_secrets:
        secrets.append(artifact.id)

    # Services
    services = {}
    if execution_services := artifact.execution.services:
        for execution_service in execution_services:
            key = f"{execution_service.id.upper()}_SERVICE"
            services[execution_service.id] = execution_service
            service.ports.append({"name": execution_service.id, "target": execution_service.port})
            env[f"{key}_PORT"] = str(execution_service.port)

    # Healthchecks; processed after services as they can depend on them.
    if healthchecks := artifact.execution.healthchecks:
        # Docker Compose only supports a single healthcheck
        probe = healthchecks.ready or healthchecks.alive or healthchecks.started

        if probe:
            # TODO: Implement this
            # service.healthcheck = _generate_healthcheck(probe, services)
            pass

    if build := artifact.build:
        context = "."
        dockerfile = build.dockerfile or "Dockerfile"
        if (pieces := dockerfile.rsplit("/", 1)) and len(pieces) > 1:
            context, dockerfile = pieces

        service.build = {"context": context, "dockerfile": dockerfile, "target": build.dockerfile_target}
    else:
        service.image = artifact.type.config.get("image", artifact.id)

    # Volumes
    if volumes := artifact.execution.volumes:
        for volume in volumes:
            execution_volume = execution_parameters.volumes.get(volume.id)

            if volume.persistent:
                volume_options = None
                if execution_volume and execution_volume.path:
                    volume_options = {"subpath": execution_volume.path}

                service.volumes.append(
                    DockerComposeServiceVolume(
                        source=volume.id, target=volume.path, type="volume", volume=volume_options
                    )
                )
            else:
                tmpfs_options = {"size": f"{volume.capacity}G"}

                service.volumes.append(
                    DockerComposeServiceVolume(target=volume.path, tmpfs=tmpfs_options, type="tmpfs")
                )

    if env:
        service.environment = env

    return service


def _generate_healthcheck(probe, services) -> dict:
    return {}


class DockerComposeExecutionEnvironmentAdapter(EnvironmentExecutionAdapter):
    def add_platform_resource(self, platform_resource: Resource):
        pass

    def _call_compose(self, docker_compose_project: DockerComposeProject, commands: Collection[str]):
        """Call docker compose."""
        # Create a temporary file filled with docker compose YAML and use that to call docker compose commands
        with tempfile.NamedTemporaryFile() as f:
            compose_yaml = yaml.dump(docker_compose_project.model_dump(exclude_none=True))

            if compose_yaml:
                f.write(compose_yaml)
                f.flush()

            args = ["docker", "compose", "--project-directory", os.getcwd(), "--file", f.name, *commands]
            subprocess.run(args)

    def deploy(
        self,
        bolt: Bolt,
        artifacts: Collection[ExecutableArtifact],
        environment: Environment,
        execution_parameters: EnvironmentArtifactExecutionParameters,
    ):
        docker_compose_project = _generate_docker_compose_project_from_bolt(
            bolt=bolt,
            artifacts=artifacts,
            adapter=self,
            environment=environment,
            execution_parameters=execution_parameters,
        )
        self._call_compose(docker_compose_project, ["up", "--build", "--watch", "--remove-orphans"])

    def fulfill_platform_resource_dependency(self, environment: Environment, artifact: ExecutableArtifact):
        pass

    def list_artifact_types(self, environment: Environment) -> list[ArtifactType]:
        return []

    def list_platform_resources(self, environment: Environment) -> list[Resource]:
        return []

    def list_services(self, environment: Environment) -> list[ExecutableArtifact]:
        return []
