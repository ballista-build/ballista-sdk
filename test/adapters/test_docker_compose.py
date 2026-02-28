import pytest

from ballista_sdk.adapters.docker_compose import DockerComposeInfrastructureAdapter
from ballista_sdk.adapters.docker_compose.generation import (
    DockerComposeProject,
    DockerComposeProjectVolume,
    DockerComposeService,
    DockerComposeServiceVolume,
)
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
            "project-postgres": {"internal": True, "name": "project-postgres"},
            "project-simple": {"internal": True, "name": "project-simple"},
            "env-test": {"internal": True, "name": "env-test"},
            "external-test.ballista.build": {"name": "external-test.ballista.build"},
        },
        services={
            "simple-api": DockerComposeService(
                container_name="simple-api",
                depends_on={"postgres-server": {"condition": "service_healthy"}},
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
            "postgres-server": DockerComposeService(
                container_name="postgres-server",
                deploy={
                    "resources": {
                        "limits": {"memory": "1.0g"},
                        "reservations": {"cpus": "0.25", "memory": "0.1g"},
                    }
                },
                environment={"POSTGRES_SERVICE_HOST": "test.ballista.build", "POSTGRES_SERVICE_PORT": "5432"},
                env_file=[{"format": "raw", "path": "postgres-server-secrets.env", "required": True}],
                healthcheck={
                    "start_interval": "1s",
                    "start_period": "60s",
                    "test": ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER"],
                },
                image="postgres:18.1",
                networks={
                    "project-postgres": {},
                    "env-test": {},
                    "external-test.ballista.build": {"aliases": ["test.ballista.build"]},
                },
                ports=[{"name": "postgres", "published": "5432", "target": 5432}],
                volumes=[
                    DockerComposeServiceVolume(
                        source="postgres-server-data",
                        target="/var/lib/postgresql/data",
                        type="volume",
                        volume={"subpath": "/custom/path"},
                    )
                ],
            ),
        },
        volumes={
            "simple-api-volume_a": DockerComposeProjectVolume(driver="local", name="Volume-A"),
            "postgres-server-data": DockerComposeProjectVolume(driver="local", name="PostgreSQL-Data"),
        },
    )


@pytest.fixture
def resource_provider_docker_compose_project():
    return DockerComposeProject(
        name="resource_provider",
        networks={
            "project-resource_provider": {"internal": True, "name": "project-resource_provider"},
            "env-test": {"internal": True, "name": "env-test"},
        },
        services={
            "resource_provider-server": DockerComposeService(
                container_name="resource_provider-server",
                deploy={
                    "resources": {
                        "limits": {"memory": "1.0g"},
                        "reservations": {"cpus": "0.25", "memory": "0.1g"},
                    }
                },
                image="hello-world:latest",
                networks={
                    "project-resource_provider": {},
                    "env-test": {},
                },
            )
        },
        volumes={},
    )


@pytest.fixture(scope="session")
def bolt(
    bolt_yaml: dict[str, dict | str],
    environment: Environment,
    docker_compose_adapter: DockerComposeInfrastructureAdapter,
) -> Bolt:
    factory = BoltV1Factory(environment, docker_compose_adapter)

    bolt = factory.get_bolt(bolt_yaml)
    if bolt:
        return bolt

    raise Exception("WTF")


@pytest.mark.unit
def test_generate_docker_compose(
    request,
    bolt: Bolt,
    docker_compose_adapter: DockerComposeInfrastructureAdapter,
    environment: Environment,
    execution_parameters: ExecutionParameters,
):
    bolt_name = request.node.callspec.params.get("bolt_yaml")
    docker_compose_project = request.getfixturevalue(f"{bolt_name}_docker_compose_project")

    assert (
        docker_compose_adapter.generate_docker_compose_project_from_bolt(
            environment=environment,
            bolt=bolt,
            artifacts=bolt.executable_artifacts,
            execution_parameters=execution_parameters,
        ).model_dump()
        == docker_compose_project.model_dump()
    )
