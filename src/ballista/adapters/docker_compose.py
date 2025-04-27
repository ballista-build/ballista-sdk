from typing import Any, Collection

from pydantic import BaseModel

from ballista.adapters.types import ExecutionEnvironment, ExecutionEnvironmentAdapter
from ballista.types import ArtifactType, Bolt, ExecutableArtifact, PlatformResource


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
    def add_platform_resource(self, platform_resource: PlatformResource):
        pass

    @staticmethod
    def _translate_artifact_to_docker_compose_service(bolt: Bolt, artifact: ExecutableArtifact) -> DockerComposeService:
        build = {}
        image = None

        if artifact.dockerfile:
            context = "."
            dockerfile = artifact.dockerfile or "Dockerfile"
            if (pieces := dockerfile.rsplit("/", 1)) and len(pieces) > 1:
                context, dockerfile = pieces

            build = {"context": context, "dockerfile": dockerfile, "target": artifact.dockerfile_stage}
        else:
            image = f"{artifact.id}:{bolt.version}"

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

    def deploy(
        self,
        bolt: Bolt,
        artifacts: Collection[ExecutableArtifact],
        environment: ExecutionEnvironment,
    ):
        docker_compose_services = {a.id: self._translate_artifact_to_docker_compose_service(bolt, a) for a in artifacts}
        docker_compose_project = DockerComposeProject(name="test", networks={}, services=docker_compose_services)
        print(docker_compose_project)

    def fulfill_platform_resource_dependency(self, environment: ExecutionEnvironment, artifact: ExecutableArtifact):
        pass

    def list_artifact_types(self, environment: ExecutionEnvironment) -> list[ArtifactType]:
        return []

    def list_platform_resources(self, environment: ExecutionEnvironment) -> list[PlatformResource]:
        return []

    def list_services(self, environment: ExecutionEnvironment) -> list[ExecutableArtifact]:
        return []

    def _make_yaml(self, environment: ExecutionEnvironment, artifact: ExecutableArtifact) -> dict:
        d = {}

        return d

    def start(self):
        pass

    def shutdown(self):
        pass
