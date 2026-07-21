import pytest

from ballista_sdk.adapters.docker_compose import DockerComposeInfrastructureAdapter
from ballista_sdk.adapters.docker_compose.generation import (
    DockerComposeProject,
    DockerComposeProjectVolume,
    DockerComposeService,
    DockerComposeServiceVolume,
)
from ballista_sdk.adapters.infrastructure import resolve_artifact_requirements
from ballista_sdk.api.v1 import (
    Bolt,
    Environment,
    ExecutionParameters,
)
from ballista_sdk.bolts.v1 import BoltV1Factory


@pytest.fixture
def simple_docker_compose_project():
    return DockerComposeProject(
        name="simple",
        networks={
            "project-simple": {"internal": True, "name": "project-simple"},
            "env-test": {"internal": True, "name": "env-test"},
            "external-test.ballista.build": {"name": "external-test.ballista.build"},
        },
        services={
            "simple-api": DockerComposeService(
                container_name="simple-api",
                depends_on={"postgres-resource-providers": {"condition": "service_healthy"}},
                deploy={
                    "resources": {
                        "limits": {"memory": "1.0g"},
                        "reservations": {"cpus": "0.25", "memory": "0.1g"},
                    }
                },
                environment={
                    "HTTP_SERVICE_HOST": "test.ballista.build",
                    "HTTP_SERVICE_PATH": "/",
                    "HTTP_SERVICE_PORT": "80",
                },
                env_file=[
                    {"format": "raw", "path": "simple-api-configs.env", "required": False},
                    {"format": "raw", "path": "simple-api-secrets.env", "required": True},
                    {"format": "raw", "path": "postgres-resources-database-configs.env", "required": True},
                ],
                healthcheck={
                    "start_interval": "1s",
                    "start_period": "60s",
                    "test": ["CMD-SHELL", "curl -f http://localhost:80/healthz"],
                },
                image="hello-world:latest",
                networks={
                    "project-simple": {},
                    "env-test": {},
                    "external-test.ballista.build": {"aliases": ["test.ballista.build"]},
                },
                ports=[{"name": "http", "published": "80", "target": 80}],
                volumes=[
                    DockerComposeServiceVolume(
                        source="simple-api-volume_a",
                        target="/var/volume_a",
                        type="volume",
                        volume={"subpath": "/custom/path"},
                    ),
                ],
            ),
        },
        volumes={"simple-api-volume_a": DockerComposeProjectVolume(driver="local", name="Volume-A")},
    )


@pytest.fixture
def project_docker_compose_project():
    return DockerComposeProject(
        name="project",
        networks={
            "project-project": {"internal": True, "name": "project-project"},
            "env-test": {"internal": True, "name": "env-test"},
            "external-test.ballista.build": {"name": "external-test.ballista.build"},
        },
        services={
            "project-resource-providers": DockerComposeService(
                container_name="project-resource-providers",
                deploy={
                    "resources": {
                        "limits": {"memory": "1.0g"},
                        "reservations": {"cpus": "0.25", "memory": "0.1g"},
                    }
                },
                environment={
                    "RESOURCE_PROVIDERS_SERVICE_HOST": "test.ballista.build",
                    "RESOURCE_PROVIDERS_SERVICE_PATH": "/",
                    "RESOURCE_PROVIDERS_SERVICE_PORT": "80",
                },
                image="hello-world:latest",
                networks={
                    "project-project": {},
                    "env-test": {},
                    "external-test.ballista.build": {"aliases": ["test.ballista.build"]},
                },
                ports=[{"name": "resource-providers", "published": "80", "target": 80}],
            )
        },
        volumes={},
    )


@pytest.fixture(scope="session")
def bolt(
    bolt_yaml: dict[str, dict | str],
) -> Bolt:
    factory = BoltV1Factory()

    bolt = factory.get_bolt(bolt_yaml)
    if bolt:
        return bolt

    raise Exception("WTF")


@pytest.mark.unit
async def test_generate_docker_compose(
    request,
    bolt: Bolt,
    docker_compose_adapter: DockerComposeInfrastructureAdapter,
    environment: Environment,
    execution_parameters: ExecutionParameters,
):
    bolt_name = request.node.callspec.params.get("bolt_yaml")
    docker_compose_project = request.getfixturevalue(f"{bolt_name}_docker_compose_project")

    resource_providers, service_providers = await resolve_artifact_requirements(
        docker_compose_adapter, environment, bolt, bolt.executable_artifacts
    )

    generated_docker_compose_project = docker_compose_adapter.generate_docker_compose_project_from_bolt(
        environment=environment,
        bolt=bolt,
        artifacts=bolt.executable_artifacts,
        execution_parameters=execution_parameters,
        resource_providers=resource_providers,
        service_providers=service_providers,
    )

    assert generated_docker_compose_project.model_dump() == docker_compose_project.model_dump()
