import pytest

from ballista.adapters.kubernetes import KubernetesExecutionEnvironmentAdapter
from ballista.adapters.types import ExecutionEnvironment, ExecutionEnvironmentAdapter
from ballista.types import Bolt


@pytest.fixture
def execution_environment_adapter(scope="session"):
    return KubernetesExecutionEnvironmentAdapter()


@pytest.mark.parametrize("bolt", ["simple"], indirect=["bolt"])
def test_deployment(
    bolt: Bolt, execution_environment_adapter: ExecutionEnvironmentAdapter, execution_environment: ExecutionEnvironment
):
    execution_environment_adapter.deploy(
        bolt=bolt, environment=execution_environment, artifacts=bolt.executable_artifacts
    )
