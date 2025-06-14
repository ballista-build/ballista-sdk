import pytest

from ballista.adapters.kubernetes import KubernetesExecutionEnvironmentAdapter
from ballista.adapters.types import EnvironmentExecutionAdapter
from ballista.types import Bolt, Environment, EnvironmentArtifactExecutionParameters


@pytest.fixture
def environment_execution_adapter(scope="session"):
    return KubernetesExecutionEnvironmentAdapter()


@pytest.mark.skip(reason="No design on how to actually use deployments yet")
@pytest.mark.parametrize("bolt", ["simple"], indirect=["bolt"])
def test_deployment(
    bolt: Bolt,
    environment_execution_adapter: EnvironmentExecutionAdapter,
    environment: Environment,
    environment_artifact_execution_parameters: EnvironmentArtifactExecutionParameters,
):
    executable_artifacts = [a for a in bolt.artifacts if a.execution]
    environment_execution_adapter.deploy(
        bolt=bolt,
        environment=environment,
        artifacts=executable_artifacts,
        execution_parameters=environment_artifact_execution_parameters,
    )
