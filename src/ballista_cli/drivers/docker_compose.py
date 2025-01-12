from ..types import BallistaProject, BallistaArtifact


def _generate_docker_service(artifact: BallistaArtifact) -> dict:
    context = "."
    dockerfile = artifact.dockerfile or "Dockerfile"
    if (pieces := dockerfile.rsplit("/", 1)) and len(pieces) > 1:
        context, dockerfile = pieces

    # TODO: Way to create the proper watch values

    return {
        "build": {"context": context, "dockerfile": dockerfile, "target": artifact.dockerfile_stage},
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
