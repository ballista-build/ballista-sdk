from typing import TypedDict

from ..types import BallistaArtifact, BallistaArtifactExecution, BallistaBolt


class DockerComposeService(TypedDict):
    build: dict
    deploy: dict
    develop: dict
    networks: list[str]
    ports: list[int]


class DockerComposeProject(TypedDict):
    networks: dict[str, dict]
    services: dict[str, DockerComposeService]


def _generate_docker_service(artifact: BallistaArtifact, execution: BallistaArtifactExecution) -> DockerComposeService:
    context = "."
    dockerfile = artifact.dockerfile or "Dockerfile"
    if (pieces := dockerfile.rsplit("/", 1)) and len(pieces) > 1:
        context, dockerfile = pieces

    deploy = {}

    local_resources = execution.local_resources

    if local_resources:
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

    # TODO: Way to create the proper watch values

    return {
        "build": {"context": context, "dockerfile": dockerfile, "target": artifact.dockerfile_stage},
        "deploy": deploy,
        "develop": {"watch": {}},
        "ports": [],
        "networks": ["platform", "services"],
    }


def _generate_docker_compose(bolt: BallistaBolt) -> DockerComposeProject:
    services = {
        f"{bolt.project}-{a.name}": _generate_docker_service(a, a.execution) for a in bolt.artifacts if a.execution
    }

    # Add dependencies

    return {"services": services, "networks": {"platform": {}, "services": {}}}


class DockerComposeBallistaEnvironment:
    def start(self, bolt: BallistaBolt):
        compose = _generate_docker_compose(bolt)

        # TODO: Run docker compose up --watch

        print(compose)

    def shutdown(self, bolt: BallistaBolt):
        pass
