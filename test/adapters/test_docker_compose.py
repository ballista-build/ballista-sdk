import contextlib

import pytest

from ballista.adapters.docker_compose import (
    DockerComposeExecutionEnvironmentAdapter,
    DockerComposeProject,
    DockerComposeProjectVolume,
    DockerComposeService,
    DockerComposeServiceVolume,
    _generate_docker_compose_project_from_bolt,
)
from ballista.types import Bolt, Environment, EnvironmentArtifactExecutionParameters


@pytest.fixture
def docker_compose_adapter():
    adapter = DockerComposeExecutionEnvironmentAdapter()
    # TODO: Load available resources into the adapter
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
                        depends_on=["postgres-server"],
                        deploy={
                            "resources": {
                                "limits": {"memory": "1.0g"},
                                "reservations": {"cpus": "0.25", "memory": "0.1g"},
                            }
                        },
                        environment={"HTTP_SERVICE_PORT": "80"},
                        env_file=[
                            {"format": "raw", "path": "postgres-shared-configs.env", "required": True},
                            {"format": "raw", "path": "simple-api-configs.env", "required": False},
                            {"format": "raw", "path": "simple-api-secrets.env", "required": True},
                        ],
                        healthcheck={"test": ["CMD-SHELL", "curl -f http://localhost/healthz:80"]},
                        image="hello-world:latest",
                        networks=[],
                        ports=[{"name": "http", "target": 80}],
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
                        environment={"POSTGRES_SERVICE_PORT": "5432"},
                        env_file=[{"format": "raw", "path": "postgres-server-secrets.env", "required": True}],
                        healthcheck={"test": ["CMD-SHELL", "pg_isready -U $POSTGRES_USER"]},
                        image="postgres:17.5",
                        ports=[{"name": "postgres", "target": 5432}],
                        volumes=[
                            DockerComposeServiceVolume(
                                source="postgres-server-data",
                                target="/var/lib/postgresql/data",
                                type="volume",
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
    environment_artifact_execution_parameters: EnvironmentArtifactExecutionParameters,
):
    executable_artifacts = [a for a in bolt.artifacts if a.execution]
    assert (
        docker_compose_project.model_dump()
        == _generate_docker_compose_project_from_bolt(
            project_id=bolt.project_id,
            version=bolt.version,
            artifacts=executable_artifacts,
            adapter=docker_compose_adapter,
            environment=environment,
            execution_parameters=environment_artifact_execution_parameters,
        ).model_dump()
    )


def test_generate_requires_artifacts(
    bolt: Bolt,
    docker_compose_adapter: DockerComposeExecutionEnvironmentAdapter,
    environment: Environment,
    environment_artifact_execution_parameters: EnvironmentArtifactExecutionParameters,
):
    executable_artifacts = [a for a in bolt.artifacts if a.execution]

    context = pytest.raises(ValueError) if len(executable_artifacts) == 0 else contextlib.nullcontext()

    with context:
        _generate_docker_compose_project_from_bolt(
            project_id=bolt.project_id,
            version=bolt.version,
            artifacts=executable_artifacts,
            adapter=docker_compose_adapter,
            environment=environment,
            execution_parameters=environment_artifact_execution_parameters,
        )
