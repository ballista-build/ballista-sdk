from __future__ import annotations

import os
import subprocess
import tempfile
from collections import deque
from collections.abc import Collection
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from ballista.adapters.types import EnvironmentExecutionAdapter, fake_artifact_types, fake_executable_artifacts
from ballista.types import (
    Artifact,
    ArtifactExecutionProbe,
    ArtifactExecutionResourceDependency,
    ArtifactExecutionService,
    ArtifactType,
    Bolt,
    Environment,
    EnvironmentArtifactExecutionParameters,
    ExecutableArtifact,
    ExecutableArtifactReference,
    Resource,
    ResourceWithArtifactProvider,
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
    depends_on: list[str] | None = None
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


class DockerComposeProject(BaseModel):
    configs: dict[str, Any] | None = None
    name: str
    networks: dict[str, dict[str, Any]]
    secrets: dict[str, Any] | None = None
    services: dict[str, DockerComposeService]
    volumes: dict[str, DockerComposeProjectVolume] = {}


def _generate_docker_compose_project_from_bolt(
    project_id: str,
    version: str,
    artifacts: Collection[ExecutableArtifact],
    adapter: DockerComposeExecutionEnvironmentAdapter,
    environment: Environment,
    execution_parameters: EnvironmentArtifactExecutionParameters,
) -> DockerComposeProject:
    """Generate a docker compose project."""

    if len(artifacts) == 0:
        raise ValueError("No artifacts to generate with.")

    project = DockerComposeProject(name=project_id, networks={}, services={}, volumes={})

    resource_service_names: dict[str, str] = {}

    artifact_deque = deque([(artifact, version, project_id) for artifact in artifacts])

    # Translate our artifacts into docker compose services
    while artifact_deque:
        item = artifact_deque.popleft()
        artifact, artifact_version, artifact_project_id = item
        artifact_ref_name = _get_artifact_ref_name(artifact_project_id, artifact)

        if artifact.execution.resources:
            requeue = False
            for resource_dependency in artifact.execution.resources:
                if resource_dependency.resource_id not in resource_service_names:
                    _, artifact_ref = adapter.resolve_resource_dependency(resource_dependency, environment)
                    if artifact_ref[0].execution:
                        requeue = True

                        if artifact_ref not in artifact_deque:
                            artifact_deque.appendleft(artifact_ref)

                    else:
                        # TODO: Virtual service stuff!
                        pass

            if requeue:
                artifact_deque.append(item)
                continue

        # We can generate this artifact!
        compose_service = _generate_docker_compose_service_from_artifact(
            project_id=artifact_project_id,
            artifact=artifact,
            version=artifact_version,
            adapter=adapter,
            environment=environment,
            execution_parameters=execution_parameters,
        )

        if artifact.execution.resources:
            compose_service.depends_on = [resource_service_names[rd.resource_id] for rd in artifact.execution.resources]

        project.services[artifact_ref_name] = compose_service

        project.volumes.update(
            {
                f"{artifact_ref_name}-{volume.id}": DockerComposeProjectVolume(
                    driver="local", name=volume.name.replace(" ", "-")
                )
                for volume in artifact.execution.volumes
                if volume.persistent
            }
        )

        if artifact.resource:
            resource_service_names[artifact.resource.id] = artifact_ref_name

    return project


def _get_artifact_ref_name(project_id: str, artifact: Artifact) -> str:
    return f"{project_id}-{artifact.id}"


def _generate_docker_compose_service_from_artifact(
    project_id: str,
    artifact: ExecutableArtifact,
    version: str,
    adapter: DockerComposeExecutionEnvironmentAdapter,
    environment: Environment,
    execution_parameters: EnvironmentArtifactExecutionParameters,
) -> DockerComposeService:
    """Generate a docker compose Service definition for an ExecutableArtifact."""

    execution = artifact.execution
    artifact_ref_name = _get_artifact_ref_name(project_id, artifact)

    compose_service = DockerComposeService(container_name=artifact_ref_name)

    if execution_resources := execution_parameters.resources:
        resource_max = {}
        resource_min = {}
        if max_cpu := execution_resources.max_cpu:
            resource_max["cpus"] = str(max_cpu)
        if max_memory := execution_resources.max_memory:
            resource_max["memory"] = f"{max_memory}g"
        if min_cpu := execution_resources.min_cpu:
            resource_min["cpus"] = str(min_cpu)
        if min_memory := execution_resources.min_memory:
            resource_min["memory"] = f"{min_memory}g"

        compose_service.deploy = {"resources": {"limits": resource_max, "reservations": resource_min}}

    env = {}
    env_files = []

    has_service_configs = bool(execution.configs)
    has_service_secrets = bool(execution.secrets)

    # Resource dependencies
    if resource_dependencies := execution.resources:
        for dependency in resource_dependencies:
            resource, _ = adapter.resolve_resource_dependency(dependency, environment)

            ref_name = f"{resource.id}-shared"

            has_shared_configs = False
            for config in resource.configs:
                if config.shared:
                    has_shared_configs = True
                else:
                    has_service_configs = True

            if has_shared_configs:
                env_files.append({"format": "raw", "path": f"{ref_name}-configs.env", "required": True})

            has_shared_secrets = False
            for secret in resource.secrets:
                if secret.shared:
                    has_shared_secrets = True
                else:
                    has_service_secrets = True

            if has_shared_secrets:
                env_files.append({"format": "raw", "path": f"{ref_name}-secrets.env", "required": True})

    if has_service_configs:
        # Service configs are NOT required
        env_files.append({"format": "raw", "path": f"{artifact_ref_name}-configs.env", "required": False})

    if has_service_secrets:
        env_files.append({"format": "raw", "path": f"{artifact_ref_name}-secrets.env", "required": True})

    # Services
    services_added = {}
    for service in execution.services:
        key = f"{service.id.upper()}_SERVICE"
        services_added[service.id] = service

        service_port = _get_service_port(service)
        env[f"{key}_PORT"] = str(service_port)

        service_execution_parameters = execution_parameters.services.get(service.id)
        if service_execution_parameters is not None:
            port = service_execution_parameters.port or service_port

            compose_service.ports.append(
                {
                    "name": service.id,
                    "published": str(port),
                    "target": service_port,
                }
            )

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
        compose_service.image = artifact.type.config.get("image", artifact.id)

    # Volumes
    if volumes := execution.volumes:
        for volume in volumes:
            execution_volume = execution_parameters.volumes.get(volume.id)

            if volume.persistent:
                volume_options = None
                if execution_volume and execution_volume.path:
                    volume_options = {"subpath": execution_volume.path}

                compose_service.volumes.append(
                    DockerComposeServiceVolume(
                        source=f"{artifact_ref_name}-{volume.id}",
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


def _generate_healthcheck(probe: ArtifactExecutionProbe, services: dict[str, ArtifactExecutionService]) -> dict:
    if probe.exec:
        return {"test": ["CMD-SHELL" if probe.exec.shell else "CMD", *probe.exec.commands]}
    if probe.grpc:
        pass
    if probe.http:
        path = probe.http.path or "/healthz"
        port = probe.http.port or 80

        if service_id := probe.http.service_id:
            if service := services.get(service_id):
                if service.http:
                    port = service.http.port
                else:
                    # Must be an HTTP service
                    raise ValueError("Cannot reference that service")
            else:
                raise ValueError(f'Unknown service "{service_id}".')

        return {"test": ["CMD-SHELL", f"curl -f http://localhost{path}:{port}"]}
    if probe.tcp:
        pass
    return {}


def _get_service_port(service: ArtifactExecutionService) -> int:
    if service.grpc:
        return service.grpc.port
    elif service.http:
        return service.http.port
    elif service.tcp:
        return service.tcp.port

    raise ValueError("WTF")


def _generate_env_files():
    pass


class DockerComposeExecutionEnvironmentAdapter(EnvironmentExecutionAdapter):
    def add_platform_resource(self, platform_resource: Resource):
        pass

    def _call_compose(self, docker_compose_project: DockerComposeProject, commands: Collection[str]):
        """Call docker compose."""
        # Create a temporary file filled with docker compose YAML and use that to call docker compose commands
        with tempfile.NamedTemporaryFile() as f:
            d = docker_compose_project.model_dump(exclude_none=True)
            compose_yaml: bytes | None = yaml.dump(d, encoding="utf-8")

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
        # Generate .env files
        _generate_env_files()

        docker_compose_project = _generate_docker_compose_project_from_bolt(
            project_id=bolt.project_id,
            version=bolt.version,
            artifacts=artifacts,
            adapter=self,
            environment=environment,
            execution_parameters=execution_parameters,
        )

        if True:
            commands = ["up", "--watch", "--remove-orphans"]
        else:
            commands = ["up", "--remove-orphans"]
        self._call_compose(docker_compose_project, commands)
        # self._call_compose(docker_compose_project, ["down", "--remove-orphans"])

    def list_artifact_types(self, environment: Environment) -> list[ArtifactType]:
        return fake_artifact_types()

    def list_resources(self, environment: Environment) -> list[ResourceWithArtifactProvider]:
        """List available Resources with a providing ArtifactReference in the specified Environment."""

        return [(ref[0].resource, ref) for ref in fake_executable_artifacts() if ref[0].resource]

    def list_executable_artifacts(self, environment: Environment) -> list[ExecutableArtifactReference]:
        return []

    def resolve_resource_dependency(
        self, resource_dependency: ArtifactExecutionResourceDependency, environment: Environment
    ) -> ResourceWithArtifactProvider:
        for item in self.list_resources(environment):
            if item[0].id == resource_dependency.resource_id:
                return item

        raise Exception("Unknown resource")

    def teardown(
        self,
        bolt: Bolt,
        artifacts: Collection[ExecutableArtifact],
        environment: Environment,
        execution_parameters: EnvironmentArtifactExecutionParameters,
    ):
        docker_compose_project = _generate_docker_compose_project_from_bolt(
            project_id=bolt.project_id,
            version=bolt.version,
            artifacts=artifacts,
            adapter=self,
            environment=environment,
            execution_parameters=execution_parameters,
        )

        self._call_compose(docker_compose_project, ["down"])
