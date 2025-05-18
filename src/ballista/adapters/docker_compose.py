import os
import subprocess
import tempfile
from collections.abc import Collection, Sequence
from typing import Any

import yaml
from pydantic import BaseModel

from ballista.adapters.types import ExecutionEnvironmentAdapter
from ballista.types import ArtifactType, Bolt, ExecutableArtifact, ExecutionEnvironment, PlatformResource


class DockerComposeService(BaseModel):
    build: dict[str, Any] | None = None
    deploy: dict[str, Any]
    develop: dict[str, Any] | None = None
    image: str | None = None
    networks: list[str]
    ports: list[str | dict[str, Any]]


class DockerComposeProject(BaseModel):
    name: str
    networks: dict[str, dict[str, Any]]
    services: dict[str, DockerComposeService]


def _generate_docker_compose_project_from_bolt(
    bolt: Bolt, artifacts: Collection[ExecutableArtifact], environment: ExecutionEnvironment
) -> DockerComposeProject:
    """Generate a docker compose project."""
    if len(artifacts) == 0:
        raise ValueError("No artifacts to generate with.")

    services = {
        artifact.id: _generate_docker_compose_service_from_artifact(bolt, artifact, environment)
        for artifact in artifacts
    }
    return DockerComposeProject(name="test", networks={}, services=services)


def _generate_docker_compose_service_from_artifact(
    bolt: Bolt, artifact: ExecutableArtifact, environment: ExecutionEnvironment
) -> DockerComposeService:
    """Generate a docker compose Service definition for an ExecutableArtifact."""
    ports = []

    deploy = {}
    if local_resources := artifact.execution.local_resources:
        resource_max = {}
        resource_min = {}
        if max_cpu := local_resources.max_cpu:
            resource_max["cpus"] = max_cpu
        if max_memory := local_resources.max_memory:
            resource_max["memory"] = f"{max_memory}g"
        if min_cpu := local_resources.min_cpu:
            resource_min["cpus"] = min_cpu
        if min_memory := local_resources.min_memory:
            resource_min["memory"] = f"{min_memory}g"

        deploy["resources"] = {"limits": resource_max, "reservations": resource_min}

    service = DockerComposeService(deploy=deploy, networks=[], ports=ports)

    if build := artifact.build:
        context = "."
        dockerfile = build.dockerfile or "Dockerfile"
        if (pieces := dockerfile.rsplit("/", 1)) and len(pieces) > 1:
            context, dockerfile = pieces

        service.build = {"context": context, "dockerfile": dockerfile, "target": build.dockerfile_target}
    else:
        service.image = artifact.type.config.get("name", artifact.id)

    return service


class DockerComposeExecutionEnvironmentAdapter(ExecutionEnvironmentAdapter):
    def add_platform_resource(self, platform_resource: PlatformResource):
        pass

    def _call_compose(self, docker_compose_project: DockerComposeProject, commands: Sequence[str]):
        """Call docker compose."""
        # Create a temporary file filled with docker compose YAML and use that to call docker compose commands
        with tempfile.NamedTemporaryFile() as f:
            compose_yaml = yaml.dump(docker_compose_project.model_dump(exclude_none=True))
            f.write(compose_yaml.encode())
            f.flush()

            args = ["docker", "compose", "--project-directory", os.getcwd(), "--file", f.name, *commands]
            subprocess.run(args)

    def deploy(
        self,
        bolt: Bolt,
        artifacts: Collection[ExecutableArtifact],
        environment: ExecutionEnvironment,
    ):
        docker_compose_project = _generate_docker_compose_project_from_bolt(
            bolt=bolt, artifacts=artifacts, environment=environment
        )
        self._call_compose(docker_compose_project, ["up", "--build", "--watch", "--remove-orphans"])

    def fulfill_platform_resource_dependency(self, environment: ExecutionEnvironment, artifact: ExecutableArtifact):
        pass

    def list_artifact_types(self, environment: ExecutionEnvironment) -> list[ArtifactType]:
        return []

    def list_platform_resources(self, environment: ExecutionEnvironment) -> list[PlatformResource]:
        return []

    def list_services(self, environment: ExecutionEnvironment) -> list[ExecutableArtifact]:
        return []
