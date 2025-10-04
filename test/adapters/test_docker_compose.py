import contextlib

import pytest

from ballista_sdk.adapters.docker_compose import (
    DockerComposeExecutionEnvironmentAdapter,
    DockerComposeProject,
    DockerComposeProjectVolume,
    DockerComposeService,
    DockerComposeServiceVolume,
    _generate_docker_compose_project_from_bolt,
)
from ballista_sdk.types import Bolt, Environment, ExecutionParameters, SpecificArtifact


@pytest.fixture
def docker_compose_adapter(fake_executable_artifacts: list[SpecificArtifact]):
    adapter = DockerComposeExecutionEnvironmentAdapter(fake_executable_artifacts)

    return adapter


@pytest.mark.parametrize(
    "bolt,docker_compose_project",
    [
        (
            "simple",
            DockerComposeProject(
                name="simple",
                networks={},
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
                            {"format": "raw", "path": "postgres-database-shared-configs.env", "required": True},
                            {"format": "raw", "path": "simple-api-configs.env", "required": False},
                            {"format": "raw", "path": "simple-api-secrets.env", "required": True},
                        ],
                        healthcheck={
                            "start_interval": "1s",
                            "start_period": "60s",
                            "test": ["CMD-SHELL", "curl -f http://localhost:80/healthz"],
                        },
                        image="hello-world:latest",
                        networks=[],
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
                        image="postgres:17.5",
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
            ),
        )
    ],
    ids=["simple"],
    indirect=["bolt"],
)
def test_generate_docker_compose(
    bolt: Bolt,
    docker_compose_project: DockerComposeProject,
    docker_compose_adapter: DockerComposeExecutionEnvironmentAdapter,
    environment: Environment,
    execution_parameters: ExecutionParameters,
):
    assert (
        docker_compose_project.model_dump()
        == _generate_docker_compose_project_from_bolt(
            project_id=bolt.project_id,
            version=bolt.version,
            artifacts=bolt.executable_artifacts,
            adapter=docker_compose_adapter,
            environment=environment,
            execution_parameters=execution_parameters,
        ).model_dump()
    )


def test_generate_requires_artifacts(
    bolt: Bolt,
    docker_compose_adapter: DockerComposeExecutionEnvironmentAdapter,
    environment: Environment,
    execution_parameters: ExecutionParameters,
):
    context = pytest.raises(ValueError) if len(bolt.executable_artifacts) == 0 else contextlib.nullcontext()

    with context:
        _generate_docker_compose_project_from_bolt(
            project_id=bolt.project_id,
            version=bolt.version,
            artifacts=bolt.executable_artifacts,
            adapter=docker_compose_adapter,
            environment=environment,
            execution_parameters=execution_parameters,
        )
