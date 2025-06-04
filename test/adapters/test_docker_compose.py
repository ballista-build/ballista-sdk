import contextlib

import pytest

from ballista.adapters.docker_compose import (
    DockerComposeProject,
    DockerComposeService,
    _generate_docker_compose_project_from_bolt,
)
from ballista.types import Bolt, Environment, EnvironmentArtifactExecutionParameters


@pytest.mark.parametrize(
    "bolt,docker_compose_project",
    [
        (
            "simple",
            DockerComposeProject(
                name="test",
                networks={},
                services={
                    "api": DockerComposeService(
                        deploy={
                            "resources": {
                                "limits": {"memory": "1.0g"},
                                "reservations": {"cpus": 0.25, "memory": "0.1g"},
                            }
                        },
                        image="hello-world:latest",
                        networks=[],
                        ports=[],
                    )
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
    environment: Environment,
    environment_artifact_execution_parameters: EnvironmentArtifactExecutionParameters,
):
    executable_artifacts = [a for a in bolt.artifacts if a.execution]
    assert (
        docker_compose_project.model_dump()
        == _generate_docker_compose_project_from_bolt(
            artifacts=executable_artifacts,
            bolt=bolt,
            environment=environment,
            execution_parameters=environment_artifact_execution_parameters,
        ).model_dump()
    )


def test_generate_requires_artifacts(
    bolt: Bolt,
    environment: Environment,
    environment_artifact_execution_parameters: EnvironmentArtifactExecutionParameters,
):
    executable_artifacts = [a for a in bolt.artifacts if a.execution]

    context = pytest.raises(ValueError) if len(executable_artifacts) == 0 else contextlib.nullcontext()

    with context:
        _generate_docker_compose_project_from_bolt(
            bolt,
            artifacts=executable_artifacts,
            environment=environment,
            execution_parameters=environment_artifact_execution_parameters,
        )
