import pytest

from ballista_sdk.adapters import InfrastructureAdapter
from ballista_sdk.adapters.docker_compose import DockerComposeInfrastructureAdapter
from ballista_sdk.adapters.kubernetes import KubernetesAPIInfrastructureAdapter
from ballista_sdk.api.v1 import Bolt


@pytest.fixture(scope="session")
def docker_compose_adapter(fake_bolts: list[Bolt]) -> InfrastructureAdapter:
    return DockerComposeInfrastructureAdapter(_bolts=fake_bolts)


@pytest.fixture(scope="session")
def kubernetes_api_adapter(fake_bolts: list[Bolt]) -> InfrastructureAdapter:
    # TODO: This needs Kubernetes running somewhere and we should have a way to boot strap the needed resources.
    return KubernetesAPIInfrastructureAdapter()


@pytest.fixture(
    params=[
        pytest.param("docker_compose", marks=[pytest.mark.unit]),
        pytest.param("kubernetes_api", marks=[pytest.mark.integration]),
    ]
)
def infrastructure_adapter(
    request, docker_compose_adapter: InfrastructureAdapter, kubernetes_api_adapter: InfrastructureAdapter
):
    if request.param == "docker_compose":
        return docker_compose_adapter
    else:
        return kubernetes_api_adapter


@pytest.fixture(scope="session")
def fake_bolts(
    postgres_bolt: Bolt,
) -> list[Bolt]:
    """Creates mock ExecutableArtifact definitions for postgres and redis."""

    return [postgres_bolt]
