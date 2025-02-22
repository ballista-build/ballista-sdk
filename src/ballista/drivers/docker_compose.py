from ..types import BallistaProject, BallistaArtifact


def _generate_docker_service(artifact: BallistaArtifact) -> dict:
    context = "."
    dockerfile = artifact.dockerfile or "Dockerfile"
    if (pieces := dockerfile.rsplit("/", 1)) and len(pieces) > 1:
        context, dockerfile = pieces

    deploy = {}

    # Local Resources
    local_resources = (
        artifact.execution.local_resources if artifact.execution and artifact.execution.local_resources else None
    )
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


def _generate_docker_compose(project: BallistaProject) -> dict:
    services = {f"{project.name}-{a.name}": _generate_docker_service(a) for a in project.artifacts if a.type.docker}

    # Add dependencies

    return {"services": services, "networks": {"platform": {}, "services": {}}}


class DockerComposeBallistaEnvironment:
    def start(self, project: BallistaProject):
        compose = _generate_docker_compose(project)

        # TODO: Run docker compose up --watch

        print(compose)

    def shutdown(self, project: BallistaProject):
        pass
