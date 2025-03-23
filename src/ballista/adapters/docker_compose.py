from typing import Any

from pydantic import BaseModel, Field

from ballista.adapters.types import ExecutionEnvironment, ExecutionEnvironmentAdapter
from ballista.types import BallistaArtifact, BallistaArtifactType, BallistaExecutableArtifact, BallistaPlatformResource


class DockerComposeService(BaseModel):
    build: dict[str, Any]
    deploy: dict[str, Any]
    develop: dict[str, Any]
    image: str | None = None
    networks: list[str]
    ports: list[str | dict[str, Any]]


class DockerComposeProject(BaseModel):
    name: str
    networks: dict[str, dict[str, Any]]
    services: dict[str, DockerComposeService]


class DockerComposeExecutionEnvironmentAdapter(ExecutionEnvironmentAdapter):
    def add_platform_resource(self, platform_resource: BallistaPlatformResource):
        pass

    @staticmethod
    def _translate_artifact_to_docker_compose_service(artifact: BallistaExecutableArtifact) -> DockerComposeService:
        build = {}
        image = None

        if artifact.dockerfile:
            context = "."
            dockerfile = artifact.dockerfile or "Dockerfile"
            if (pieces := dockerfile.rsplit("/", 1)) and len(pieces) > 1:
                context, dockerfile = pieces

            build = {"context": context, "dockerfile": dockerfile, "target": artifact.dockerfile_stage}

        deploy = {}

        if local_resources := artifact.execution.local_resources:
            resource_max = {}
            resource_min = {}
            if max_cpu_cores := local_resources.max_cpu_cores:
                resource_max["cpus"] = max_cpu_cores
            if max_memory_mb := local_resources.max_memory_mb:
                resource_max["memory"] = max_memory_mb
            if min_cpu_cores := local_resources.min_cpu_cores:
                resource_min["cpus"] = min_cpu_cores
            if min_memory_mb := local_resources.min_memory_mb:
                resource_min["memory"] = min_memory_mb

            deploy["resources"] = {"limits": resource_max, "reservations": resource_min}

        if platform_resources := artifact.execution.platform_resources:
            pass

        return DockerComposeService(
            build=build,
            deploy=deploy,
            develop={},
            image=image,
            ports=[],
            networks=["platform", "services"],
        )

    def deploy_artifact(self, environment: ExecutionEnvironment, artifact: BallistaExecutableArtifact):
        print(self._translate_artifact_to_docker_compose_service(artifact))

    def fulfill_platform_resource_dependency(
        self, environment: ExecutionEnvironment, artifact: BallistaExecutableArtifact
    ):
        pass

    def list_artifact_types(self, environment: ExecutionEnvironment) -> list[BallistaArtifactType]:
        return []

    def list_platform_resources(self, environment: ExecutionEnvironment) -> list[BallistaPlatformResource]:
        return []

    def list_services(self, environment: ExecutionEnvironment) -> list[BallistaExecutableArtifact]:
        return []

    def _make_yaml(self, environment: ExecutionEnvironment, artifact: BallistaExecutableArtifact) -> dict:
        d = {}

        return d

    def start(self):
        pass

    def shutdown(self):
        pass
